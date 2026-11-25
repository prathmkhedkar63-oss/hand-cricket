import time
from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database.json_manager import db
from backend.authentication.auth import verify_token

router = APIRouter(prefix="/api", tags=["Settings & Audit"])

class SystemSettingsUpdate(BaseModel):
    innings_limit: int = 2
    wickets_limit: int = 1
    max_balls: int = 36
    solo_countdown_seconds: int = 120
    matchmaking_enabled: bool = True
    dispute_auto_pause: bool = True

@router.get("/settings")
async def get_settings(auth: dict = Depends(verify_token)):
    return await db.load("settings")

@router.put("/settings")
async def update_settings(req: SystemSettingsUpdate, auth: dict = Depends(verify_token)):
    current = await db.load("settings")
    updated = {**current, **req.model_dump()}
    await db.save("settings", updated)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "update_system_settings",
        "target": "settings",
        "details": req.model_dump(),
        "timestamp": time.time()
    })
    return updated

@router.get("/audit-logs")
async def get_audit_logs(limit: int = 50, auth: dict = Depends(verify_token)):
    logs = await db.load("audit_logs")
    return sorted(logs, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]

@router.get("/overview")
async def get_system_overview(auth: dict = Depends(verify_token)):
    users = await db.load("users")
    matches = await db.load("matches")
    tournaments = await db.load("tournaments")
    hosts = await db.load("hosts")

    active_matches = [m for m in matches.values() if m.get("status") == "in_progress"]
    completed_matches = [m for m in matches.values() if m.get("status") == "completed"]
    active_tournaments = [t for t in tournaments.values() if t.get("status") in ["registration", "countdown", "active"]]

    now = time.time()
    day_ago = now - 86400
    month_ago = now - 2592000

    daily_active_players = len([u for u in users.values() if u.get("registered_at", 0) > day_ago])
    monthly_matches = len([m for m in matches.values() if m.get("created_at", 0) > month_ago])

    return {
        "total_players": len(users),
        "active_players": len(users),
        "total_matches": len(matches),
        "ongoing_matches": len(active_matches),
        "completed_matches": len(completed_matches),
        "total_tournaments": len(tournaments),
        "active_tournaments": len(active_tournaments),
        "total_hosts": len(hosts),
        "daily_activity": daily_active_players,
        "monthly_activity": monthly_matches
    }

@router.post("/system/backup")
async def trigger_backup(auth: dict = Depends(verify_token)):
    path = await db.create_backup("admin_api")
    return {"message": "Backup created successfully", "path": path}
