import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database.json_manager import db
from backend.authentication.auth import verify_token
from bot.services.host_tournament_service import HostTournamentService

router = APIRouter(prefix="/api/hosts", tags=["Hosts"])

class AssignHostBody(BaseModel):
    user_id: int
    username: str
    assigned_tournaments: Optional[List[str]] = None

@router.get("")
async def list_hosts(auth: dict = Depends(verify_token)):
    hosts = await db.load("hosts")
    return list(hosts.values())

@router.post("")
async def create_host(req: AssignHostBody, auth: dict = Depends(verify_token)):
    await HostTournamentService.assign_host(
        user_id=req.user_id,
        username=req.username,
        assigned_tournaments=req.assigned_tournaments or ["*"],
        assigned_by=0
    )
    return {"message": f"Host @{req.username} assigned successfully."}

@router.delete("/{user_id}")
async def revoke_host(user_id: int, auth: dict = Depends(verify_token)):
    hosts = await db.load("hosts")
    uid_str = str(user_id)
    if uid_str in hosts:
        hosts[uid_str]["is_active"] = False
        await db.save("hosts", hosts)
        await db.append("audit_logs", {
            "actor": auth.get("sub", "admin"),
            "action": "revoke_host",
            "target": uid_str,
            "timestamp": time.time()
        })
    return {"message": "Host privileges revoked."}
