import re
from typing import Any, Dict, List, Optional

class ValidationError(Exception):
    pass

class DataValidator:
    """
    Validates records prior to writing to the JSON database.
    """
    REQUIRED_TABLES = [
        "users",
        "statistics",
        "tournaments",
        "participants",
        "teams",
        "matches",
        "innings",
        "ball_history",
        "hosts",
        "admins",
        "leaderboard",
        "notifications",
        "reports",
        "audit_logs",
        "settings",
    ]

    @staticmethod
    def validate_user(data: Dict[str, Any]) -> None:
        if "user_id" not in data or not str(data["user_id"]).isdigit():
            raise ValidationError("Invalid or missing user_id. Must be a numeric Telegram ID.")
        if "username" in data and data["username"]:
            cleaned = data["username"].lstrip("@")
            if not re.match(r"^[a-zA-Z0-9_]{3,32}$", cleaned):
                # We can store raw username or fallback, but check validity
                pass

    @staticmethod
    def validate_match(data: Dict[str, Any]) -> None:
        required_fields = ["match_id", "status", "player1_id", "player2_id"]
        for f in required_fields:
            if f not in data:
                raise ValidationError(f"Missing required match field: {f}")

    @staticmethod
    def validate_tournament(data: Dict[str, Any]) -> None:
        required_fields = ["tournament_id", "name", "mode", "status"]
        for f in required_fields:
            if f not in data:
                raise ValidationError(f"Missing required tournament field: {f}")
        if data["mode"] not in ["solo", "host"]:
            raise ValidationError("Tournament mode must be 'solo' or 'host'.")

    @staticmethod
    def validate_ball(data: Dict[str, Any]) -> None:
        required_fields = ["ball_id", "match_id", "innings_num", "batsman_id", "bowler_id"]
        for f in required_fields:
            if f not in data:
                raise ValidationError(f"Missing required ball field: {f}")
        if "batsman_number" in data and data["batsman_number"] is not None:
            if data["batsman_number"] not in range(7):
                raise ValidationError("Batsman number must be between 0 and 6.")
        if "bowler_number" in data and data["bowler_number"] is not None:
            if data["bowler_number"] not in range(7):
                raise ValidationError("Bowler number must be between 0 and 6.")
