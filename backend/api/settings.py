import asyncio
import html
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
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

class BroadcastRequest(BaseModel):
    message: str
    target: Literal["all", "groups", "dms"] = "all"

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
async def get_system_overview(request: Request, auth: dict = Depends(verify_token)):
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

    using_pg = db.using_external_db
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
        "monthly_activity": monthly_matches,
        "storage_mode": "postgresql" if using_pg else "json",
        "storage_label": "Supabase PostgreSQL (15 Tables)" if using_pg else "Atomic JSON (15 Files Synced)",
        "bot_mode": "webhook" if getattr(request.app.state, "webhook_enabled", False) else "polling",
    }

@router.post("/broadcast")
async def broadcast_message(req: BroadcastRequest, request: Request, auth: dict = Depends(verify_token)):
    text_body = req.message.strip()
    if not text_body:
        raise HTTPException(status_code=400, detail="Broadcast message cannot be empty.")

    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot instance is not attached.")

    users = await db.load("users")
    sys_settings = await db.load("settings")
    dm_ids = set()
    if req.target in ("all", "dms"):
        for uid_str, u in users.items():
            if u.get("is_banned"):
                continue
            cid = u.get("private_chat_id") or u.get("user_id")
            if isinstance(cid, int) and cid > 0:
                dm_ids.add(cid)

    group_ids = set()
    if req.target in ("all", "groups"):
        for gid in sys_settings.get("known_groups", []):
            if isinstance(gid, int) and gid < 0:
                group_ids.add(gid)

    formatted = f"📢 <b>JPL CRICKET BOT</b>\n━━━━━━━━━━━━━━━━━━━━\n{html.escape(text_body)}"
    dm_sent = 0
    group_sent = 0
    failed = 0
    dead_groups = set()

    for chat_id in list(dm_ids) + list(group_ids):
        try:
            await bot.send_message(chat_id=chat_id, text=formatted, parse_mode="HTML")
            if chat_id > 0:
                dm_sent += 1
            else:
                group_sent += 1
        except Exception as e:
            failed += 1
            err = str(e).lower()
            if chat_id < 0 and ("forbidden" in err or "chat not found" in err or "kicked" in err):
                dead_groups.add(chat_id)
        await asyncio.sleep(0.05)

    if dead_groups and isinstance(sys_settings.get("known_groups"), list):
        sys_settings["known_groups"] = [g for g in sys_settings["known_groups"] if g not in dead_groups]
        await db.save("settings", sys_settings)

    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "web_broadcast",
        "target": req.target,
        "details": {"dm_sent": dm_sent, "group_sent": group_sent, "failed": failed},
        "timestamp": time.time()
    })
    return {
        "dm_sent": dm_sent,
        "group_sent": group_sent,
        "failed": failed,
        "total": dm_sent + group_sent
    }

@router.post("/system/backup")
async def trigger_backup(auth: dict = Depends(verify_token)):
    path = await db.create_backup("admin_api")
    return {"message": "Backup created successfully", "path": path}

@router.get("/system/backup/download")
async def download_backup_json(auth: dict = Depends(verify_token)):
    tables: Dict[str, Any] = {}
    for table_name in db.DEFAULT_SCHEMAS:
        tables[table_name] = await db.load(table_name)

    bundle = {
        "exported_at": time.time(),
        "storage": "postgresql" if db.using_external_db else "json",
        "tables": tables,
    }
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    await db.append("audit_logs", {
        "actor": auth.get("sub", "admin"),
        "action": "download_backup",
        "target": "all_tables",
        "timestamp": time.time()
    })
    return Response(
        content=json.dumps(bundle, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="jplbot_backup_{ts}.json"'}
    )
