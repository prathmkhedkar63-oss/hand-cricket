import sys
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from config.settings import settings
from backend.authentication.auth import create_access_token
from backend.api.players import router as players_router
from backend.api.tournaments import router as tournaments_router
from backend.api.matches import router as matches_router
from backend.api.hosts import router as hosts_router
from backend.api.settings import router as settings_router
from database.json_manager import db

app = FastAPI(
    title="Hand Cricket Bot - Admin API",
    version="1.0.0",
    description="Production-grade REST API powering the Hand Cricket Bot & Tournament Management System"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login", tags=["Auth"])
async def login(req: LoginRequest):
    if req.username == settings.ADMIN_USERNAME and req.password == settings.ADMIN_PASSWORD:
        token = create_access_token({"sub": req.username, "role": "superadmin"})
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": req.username
        }
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

# Include Routers
app.include_router(players_router)
app.include_router(tournaments_router)
app.include_router(matches_router)
app.include_router(hosts_router)
app.include_router(settings_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "storage": "postgresql" if db.using_external_db else "json",
        "timestamp": time.time()
    }

# Mount admin panel static files if built
admin_dist_path = Path(__file__).resolve().parent.parent / "admin_panel" / "dist"
if admin_dist_path.exists():
    app.mount("/", StaticFiles(directory=str(admin_dist_path), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)
