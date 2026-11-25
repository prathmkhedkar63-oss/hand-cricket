import time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from database.json_manager import db
from backend.authentication.auth import verify_token
from bot.services.stats_service import StatsService

router = APIRouter(prefix="/api/players", tags=["Players"])

class BanRequest(BaseModel):
    reason: str

@router.get("")
async def get_players(
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    auth: dict = Depends(verify_token)
):
    users = await db.load("users")
    stats = await db.load("statistics")
    
    player_list = []
    for uid, u in users.items():
        user_stats = stats.get(uid, {})
        entry = {**u, "stats": user_stats}
        if search:
            q = search.lower().lstrip("@")
            if q in u.get("username", "").lower() or q in str(uid):
                player_list.append(entry)
        else:
            player_list.append(entry)

    total = len(player_list)
    start = (page - 1) * limit
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "players": player_list[start:start + limit]
    }

@router.get("/{user_id}")
async def get_player_details(user_id: int, auth: dict = Depends(verify_token)):
    user = await db.get("users", str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")
    stats = await db.get("statistics", str(user_id), {})
    matches = await db.load("matches")
    participants = await db.load("participants")

    user_matches = [m for m in matches.values() if m.get("player1_id") == user_id or m.get("player2_id") == user_id]
    joined_tournaments = [p["tournament_id"] for p in participants if p.get("user_id") == user_id]

    return {
        "user": user,
        "statistics": stats,
        "recent_matches": user_matches[-10:],
        "tournaments": joined_tournaments
    }

@router.post("/{user_id}/ban")
async def ban_player(user_id: int, req: BanRequest, auth: dict = Depends(verify_token)):
    users = await db.load("users")
    uid_str = str(user_id)
    if uid_str not in users:
        raise HTTPException(status_code=404, detail="Player not found")

    users[uid_str]["is_banned"] = True
    users[uid_str]["ban_reason"] = req.reason
    await db.save("users", users)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "ban_player",
        "target": uid_str,
        "reason": req.reason,
        "timestamp": time.time()
    })
    return {"message": f"Player {user_id} banned successfully."}

@router.post("/{user_id}/unban")
async def unban_player(user_id: int, auth: dict = Depends(verify_token)):
    users = await db.load("users")
    uid_str = str(user_id)
    if uid_str not in users:
        raise HTTPException(status_code=404, detail="Player not found")

    users[uid_str]["is_banned"] = False
    users[uid_str]["ban_reason"] = None
    await db.save("users", users)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "unban_player",
        "target": uid_str,
        "timestamp": time.time()
    })
    return {"message": f"Player {user_id} unbanned."}

@router.post("/{user_id}/reset-stats")
async def reset_player_stats(user_id: int, auth: dict = Depends(verify_token)):
    stats = await db.load("statistics")
    uid_str = str(user_id)
    if uid_str not in stats:
        raise HTTPException(status_code=404, detail="Player stats not found")

    user = await db.get("users", uid_str, {})
    stats[uid_str] = StatsService._create_empty_stats(user_id, user.get("username", f"player_{user_id}"), time.time())
    await db.save("statistics", stats)
    await StatsService.refresh_leaderboards()

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "reset_player_stats",
        "target": uid_str,
        "timestamp": time.time()
    })
    return {"message": f"Player {user_id} stats reset to zero."}
