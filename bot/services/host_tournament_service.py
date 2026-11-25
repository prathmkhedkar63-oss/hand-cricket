import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from database.json_manager import db
from bot.services.tournament_service import TournamentService

logger = logging.getLogger("host_tournament_service")

class HostTournamentService:
    """
    Host-Managed Tournament & Match Controller:
    - Manual host assignment and control
    - Team A and Team B roster organization
    - Manual match pairing, batsman/bowler selection
    - Pause, resume, reset, dispute resolution
    - Manual round advancement and winner declaration
    """

    @staticmethod
    async def is_host_authorized(user_id: int, tournament_id: Optional[str] = None) -> bool:
        """
        Verifies if user is an authorized host.
        If tournament_id is provided, checks if host is assigned to this specific tournament.
        """
        hosts = await db.load("hosts")
        uid_str = str(user_id)
        if uid_str not in hosts:
            return False

        host_info = hosts[uid_str]
        if host_info.get("is_active") is False:
            return False

        if tournament_id:
            assigned = host_info.get("assigned_tournaments", [])
            # If "*" host has all tournaments, or specific tournament_id is in assigned list
            return ("*" in assigned) or (tournament_id in assigned)
        return True

    @staticmethod
    async def assign_host(user_id: int, username: str, assigned_tournaments: Optional[List[str]] = None, assigned_by: int = 0):
        hosts = await db.load("hosts")
        uid_str = str(user_id)
        hosts[uid_str] = {
            "user_id": user_id,
            "username": username.lstrip("@"),
            "assigned_tournaments": assigned_tournaments or ["*"],
            "assigned_by": assigned_by,
            "assigned_at": time.time(),
            "is_active": True
        }
        await db.save("hosts", hosts)
        await db.append("audit_logs", {
            "actor_id": assigned_by,
            "action": "assign_host",
            "target": str(user_id),
            "details": f"Assigned host privileges to @{username}",
            "timestamp": time.time()
        })

    MAX_TEAM_SIZE: int = 11

    @staticmethod
    async def manage_teams(tournament_id: str, team_name: str, action: str, user_id: int, username: str) -> Tuple[bool, str]:
        """
        Organizes Team A and Team B rosters for a tournament (max 11 players per team).
        action: 'add' or 'remove'
        """
        teams_data = await db.load("teams")
        t_teams = teams_data.setdefault(tournament_id, {"Team A": [], "Team B": [], "captains": {}})

        if team_name not in ["Team A", "Team B"]:
            return False, "Team must be either 'Team A' or 'Team B'."

        target_team = t_teams[team_name]
        clean_user = username.lstrip("@")

        if action == "add":
            # Check if already in target team
            if any(p["user_id"] == user_id for p in target_team):
                return False, f"@{clean_user} is already in {team_name}."

            if len(target_team) >= HostTournamentService.MAX_TEAM_SIZE:
                return False, f"{team_name} already has the maximum {HostTournamentService.MAX_TEAM_SIZE} players!"

            # Remove from opposite team if present
            opp_team = "Team B" if team_name == "Team A" else "Team A"
            t_teams[opp_team] = [p for p in t_teams[opp_team] if p["user_id"] != user_id]

            # Add to target team
            target_team.append({"user_id": user_id, "username": clean_user})
            msg = f"Added @{clean_user} to {team_name}."
        elif action == "remove":
            initial_len = len(target_team)
            t_teams[team_name] = [p for p in target_team if p["user_id"] != user_id]
            if len(t_teams[team_name]) == initial_len:
                return False, f"@{clean_user} was not in {team_name}."
            # Clear captain if removed player was captain
            cap = t_teams.get("captains", {}).get(team_name)
            if cap and cap.get("user_id") == user_id:
                del t_teams["captains"][team_name]
            msg = f"Removed @{clean_user} from {team_name}."
        else:
            return False, f"Unknown team action: {action}"

        await db.save("teams", teams_data)
        return True, msg

    @staticmethod
    async def swap_player(tournament_id: str, slot_number: int, new_user_id: int, new_username: str) -> Tuple[bool, str]:
        """
        Substitutes an existing player by their 1-based roster number with a new player.
        """
        teams_data = await db.load("teams")
        t_teams = teams_data.setdefault(tournament_id, {"Team A": [], "Team B": [], "captains": {}})
        team_a = t_teams.get("Team A", [])
        team_b = t_teams.get("Team B", [])
        total = len(team_a) + len(team_b)

        if slot_number < 1 or slot_number > total:
            return False, f"Invalid player number #{slot_number}. Valid range: 1 to {total}."

        clean_new = new_username.lstrip("@")
        if any(p["user_id"] == new_user_id for p in team_a + team_b):
            return False, f"@{clean_new} is already in a team!"

        if slot_number <= len(team_a):
            team_name = "Team A"
            idx = slot_number - 1
            old_player = team_a[idx]
            team_a[idx] = {"user_id": new_user_id, "username": clean_new}
        else:
            team_name = "Team B"
            idx = slot_number - len(team_a) - 1
            old_player = team_b[idx]
            team_b[idx] = {"user_id": new_user_id, "username": clean_new}

        # Update captain if old player was captain
        cap = t_teams.get("captains", {}).get(team_name)
        if cap and cap.get("user_id") == old_player["user_id"]:
            t_teams["captains"][team_name] = {"user_id": new_user_id, "username": clean_new}

        await db.save("teams", teams_data)
        return True, f"Swapped #{slot_number} (@{old_player['username']}) ➡️ @{clean_new} in {team_name}!"

    @staticmethod
    async def set_captain(tournament_id: str, team_name: str, user_id: int, username: str) -> Tuple[bool, str]:
        teams_data = await db.load("teams")
        t_teams = teams_data.setdefault(tournament_id, {"Team A": [], "Team B": [], "captains": {}})
        if "captains" not in t_teams:
            t_teams["captains"] = {}

        if team_name not in ["Team A", "Team B"]:
            return False, "Team must be either 'Team A' or 'Team B'."

        clean_user = username.lstrip("@")
        # Ensure player is in the team roster
        target_team = t_teams[team_name]
        if not any(p["user_id"] == user_id for p in target_team):
            # Auto add if not present
            target_team.append({"user_id": user_id, "username": clean_user})

        t_teams["captains"][team_name] = {"user_id": user_id, "username": clean_user}
        await db.save("teams", teams_data)
        return True, f"Set @{clean_user} as Captain of {team_name}!"

    @staticmethod
    async def get_teams(tournament_id: str) -> Dict[str, Any]:
        teams_data = await db.load("teams")
        return teams_data.get(tournament_id, {"Team A": [], "Team B": [], "captains": {}})
