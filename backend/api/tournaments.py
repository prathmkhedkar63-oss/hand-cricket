import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database.json_manager import db
from backend.authentication.auth import verify_token
from bot.services.tournament_service import TournamentService

router = APIRouter(prefix="/api/tournaments", tags=["Tournaments"])

class CreateTournamentRequest(BaseModel):
    name: str
    description: str
    mode: str  # 'solo' or 'host'
    group_chat_id: int
    host_id: Optional[int] = None
    max_balls: int = 36

class AssignHostRequest(BaseModel):
    host_id: int
    host_username: str

class ManageTeamRequest(BaseModel):
    team_name: str # 'Team A' or 'Team B'
    action: str    # 'add' or 'remove'
    user_id: int
    username: str

@router.get("")
async def get_tournaments(mode: Optional[str] = None, status: Optional[str] = None, auth: dict = Depends(verify_token)):
    tournaments = await db.load("tournaments")
    result = list(tournaments.values())
    if mode:
        result = [t for t in result if t.get("mode") == mode]
    if status:
        result = [t for t in result if t.get("status") == status]
    return sorted(result, key=lambda x: x.get("created_at", 0), reverse=True)

@router.post("")
async def create_tournament(req: CreateTournamentRequest, auth: dict = Depends(verify_token)):
    t_id = f"trn_{uuid.uuid4().hex[:6]}"
    tournament = await TournamentService.create_tournament(
        tournament_id=t_id,
        name=req.name,
        description=req.description,
        mode=req.mode,
        group_chat_id=req.group_chat_id,
        creator_id=0,
        host_id=req.host_id,
        max_balls=req.max_balls
    )
    return tournament

@router.delete("/{tournament_id}")
async def delete_tournament(tournament_id: str, auth: dict = Depends(verify_token)):
    tournaments = await db.load("tournaments")
    if tournament_id not in tournaments:
        raise HTTPException(status_code=404, detail="Tournament not found")

    tournaments[tournament_id]["status"] = "archived"
    await db.save("tournaments", tournaments)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "archive_tournament",
        "target": tournament_id,
        "timestamp": time.time()
    })
    return {"message": "Tournament archived."}

@router.get("/{tournament_id}/participants")
async def get_participants(tournament_id: str, auth: dict = Depends(verify_token)):
    return await TournamentService.get_tournament_participants(tournament_id)

@router.get("/{tournament_id}/teams")
async def get_teams(tournament_id: str, auth: dict = Depends(verify_token)):
    teams = await db.load("teams")
    return teams.get(tournament_id, {"Team A": [], "Team B": []})

@router.post("/{tournament_id}/teams")
async def manage_team_player(tournament_id: str, req: ManageTeamRequest, auth: dict = Depends(verify_token)):
    from bot.services.host_tournament_service import HostTournamentService
    success, msg = await HostTournamentService.manage_teams(tournament_id, req.team_name, req.action, req.user_id, req.username)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}

@router.post("/{tournament_id}/assign-host")
async def assign_tournament_host(tournament_id: str, req: AssignHostRequest, auth: dict = Depends(verify_token)):
    from bot.services.host_tournament_service import HostTournamentService
    await HostTournamentService.assign_host(req.host_id, req.host_username, [tournament_id], assigned_by=0)
    tournaments = await db.load("tournaments")
    if tournament_id in tournaments:
        tournaments[tournament_id]["host_id"] = req.host_id
        await db.save("tournaments", tournaments)
    return {"message": f"Host @{req.host_username} assigned to tournament {tournament_id}."}
