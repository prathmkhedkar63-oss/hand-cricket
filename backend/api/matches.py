import time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database.json_manager import db
from backend.authentication.auth import verify_token
from game_engine.models import MatchStatus

router = APIRouter(prefix="/api/matches", tags=["Matches"])

class OverrideMatchRequest(BaseModel):
    winner_id: int
    winner_username: str
    reason: str

@router.get("")
async def get_matches(status: Optional[str] = None, tournament_id: Optional[str] = None, auth: dict = Depends(verify_token)):
    matches = await db.load("matches")
    result = list(matches.values())
    if status:
        result = [m for m in result if m.get("status") == status]
    if tournament_id:
        result = [m for m in result if m.get("tournament_id") == tournament_id]
    return sorted(result, key=lambda x: x.get("created_at", 0), reverse=True)

@router.get("/{match_id}")
async def get_match_detail(match_id: str, auth: dict = Depends(verify_token)):
    matches = await db.load("matches")
    match = matches.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Ball by ball history
    balls = await db.load("ball_history")
    match_balls = [b for b in balls if b.get("match_id") == match_id]
    return {
        "match": match,
        "ball_history": match_balls
    }

@router.post("/{match_id}/cancel")
async def cancel_match(match_id: str, auth: dict = Depends(verify_token)):
    matches = await db.load("matches")
    if match_id not in matches:
        raise HTTPException(status_code=404, detail="Match not found")

    matches[match_id]["status"] = MatchStatus.ABANDONED.value
    matches[match_id]["result_text"] = "Match cancelled by Admin."
    await db.save("matches", matches)

    from bot.services.game_service import GameService
    GameService.active_matches.pop(match_id, None)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "cancel_match",
        "target": match_id,
        "timestamp": time.time()
    })
    return {"message": "Match cancelled."}

@router.post("/{match_id}/override")
async def override_match(match_id: str, req: OverrideMatchRequest, auth: dict = Depends(verify_token)):
    matches = await db.load("matches")
    if match_id not in matches:
        raise HTTPException(status_code=404, detail="Match not found")

    match_dict = matches[match_id]
    match_dict["status"] = MatchStatus.COMPLETED.value
    match_dict["winner_id"] = req.winner_id
    match_dict["winner_username"] = req.winner_username
    match_dict["result_text"] = f"Admin override: Won by @{req.winner_username} ({req.reason})"
    await db.save("matches", matches)

    from bot.services.game_service import GameService
    GameService.active_matches.pop(match_id, None)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "override_match_result",
        "target": match_id,
        "reason": req.reason,
        "details": f"Winner overridden to @{req.winner_username}",
        "timestamp": time.time()
    })
    return {"message": "Match result overridden successfully."}
