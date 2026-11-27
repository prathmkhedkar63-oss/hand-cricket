import random
import time
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from database.json_manager import db

logger = logging.getLogger("tournament_service")

class TournamentService:
    @staticmethod
    def generate_single_elimination_bracket(players: List[Dict[str, Any]], shuffle: bool = True) -> List[Dict[str, Any]]:
        """
        Generates single elimination pairings.
        If player count is odd or not a power of 2, handles byes automatically.
        """
        player_list = list(players)
        if shuffle:
            random.shuffle(player_list)

        n = len(player_list)
        if n < 2:
            return []

        # Find next power of 2
        next_pow2 = 1 << (n - 1).bit_length()
        num_byes = next_pow2 - n

        fixtures = []
        p_idx = 0

        # Players receiving byes automatically advance to next round
        byes_awarded = []
        for _ in range(num_byes):
            if p_idx < len(player_list):
                byes_awarded.append(player_list[p_idx])
                p_idx += 1

        # Remaining players paired up for round 1
        match_num = 1
        while p_idx < len(player_list) - 1:
            p1 = player_list[p_idx]
            p2 = player_list[p_idx + 1]
            fixtures.append({
                "match_number": match_num,
                "player1": p1,
                "player2": p2,
                "status": "pending",
                "winner": None
            })
            p_idx += 2
            match_num += 1

        # If odd remaining somehow
        if p_idx < len(player_list):
            byes_awarded.append(player_list[p_idx])

        return fixtures, byes_awarded

    @staticmethod
    async def create_tournament(
        tournament_id: str,
        name: str,
        description: str,
        mode: str, # 'solo' or 'host'
        group_chat_id: int,
        creator_id: int,
        host_id: Optional[int] = None,
        max_balls: int = 36,
        format_type: str = "single_elimination"
    ) -> Dict[str, Any]:
        tournaments = await db.load("tournaments")
        now = time.time()

        tournament = {
            "tournament_id": tournament_id,
            "name": name,
            "description": description,
            "mode": mode,
            "status": "registration", # 'registration', 'countdown', 'active', 'completed', 'cancelled'
            "group_chat_id": group_chat_id,
            "creator_id": creator_id,
            "host_id": host_id,
            "format": format_type,
            "max_balls": max_balls,
            "current_round": 1,
            "round_name": "Round 1",
            "countdown_end_time": None,
            "countdown_message_id": None,
            "champion_id": None,
            "champion_username": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None
        }

        tournaments[tournament_id] = tournament
        await db.save("tournaments", tournaments)

        # Audit log
        await db.append("audit_logs", {
            "actor_id": creator_id,
            "action": "create_tournament",
            "target": tournament_id,
            "details": f"Created {mode} tournament '{name}'",
            "timestamp": now
        })

        return tournament

    @staticmethod
    async def register_player(tournament_id: str, user_id: int, username: str) -> Tuple[bool, str]:
        tournaments = await db.load("tournaments")
        tournament = tournaments.get(tournament_id)
        if not tournament:
            return False, "Tournament not found."

        if tournament["status"] not in ["registration", "countdown"]:
            return False, f"Tournament is currently in '{tournament['status']}' state. Registration is closed."

        participants = await db.load("participants")
        # Check duplicate
        for p in participants:
            if p["tournament_id"] == tournament_id and p["user_id"] == user_id:
                return False, "You are already registered for this tournament!"

        clean_user = username.lstrip("@").strip() if isinstance(username, str) and username.lstrip("@").strip() else f"Player {user_id}"
        participants.append({
            "tournament_id": tournament_id,
            "user_id": user_id,
            "username": clean_user,
            "team": None,
            "status": "active",
            "joined_at": time.time()
        })
        await db.save("participants", participants)
        return True, f"Successfully registered {clean_user} for tournament '{tournament['name']}'!"

    @staticmethod
    async def withdraw_player(tournament_id: str, user_id: int) -> Tuple[bool, str]:
        tournaments = await db.load("tournaments")
        tournament = tournaments.get(tournament_id)
        if not tournament:
            return False, "Tournament not found."

        if tournament["status"] not in ["registration", "countdown"]:
            return False, "Cannot withdraw. Tournament has already started or locked."

        participants = await db.load("participants")
        initial_count = len(participants)
        filtered = [p for p in participants if not (p["tournament_id"] == tournament_id and p["user_id"] == user_id)]
        if len(filtered) == initial_count:
            return False, "You were not registered in this tournament."

        await db.save("participants", filtered)
        return True, "Successfully withdrawn from tournament."

    @staticmethod
    async def get_tournament_participants(tournament_id: str) -> List[Dict[str, Any]]:
        participants = await db.load("participants")
        return [p for p in participants if p["tournament_id"] == tournament_id and p.get("status") == "active"]
