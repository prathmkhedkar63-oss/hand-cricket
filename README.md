---
title: Hand Cricket Bot
emoji: 🏏
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# 🏏 Advanced Telegram Hand Cricket Bot & Tournament Management System

A production-ready, esports-grade Telegram Hand Cricket Bot built with **Python 3.12+**, **Aiogram 3.x**, **FastAPI**, an **Atomic JSON File Database**, and a modern dark **React 18 + TypeScript + Tailwind CSS Admin Dashboard**.

---

## ⚡ Core Architecture & Highlights

1. **Unique Live Gameplay Engine**:
   - **Private DM Bowling**: The current bowler receives a direct private message from the bot with inline buttons `0 | 1 | 2 | 3 | 4 | 5 | 6` (or can type `0` to `6`). The bowler's selection is encrypted and securely held in memory/JSON without being revealed to the group or batsman.
   - **Telegram Group Batting**: After the delivery is bowled, the bot prompts the active batsman in the tournament group with inline buttons `0 | 1 | 2 | 3 | 4 | 5 | 6` (or typing `0` to `6`). Unauthorized clicks by spectators are strictly rejected with an instant alert.
   - **Instant Resolution & Live Scoreboard**: Upon the batsman's shot, the bot reveals both numbers in the group, announces runs or **OUT!**, updates the persistent `ball_history.json`, updates player statistics, and edits the live group scoreboard in real-time.

2. **Two Independent Tournament Modes**:
   - **Mode 1: Solo Player Tournament (100% Automated)**
     - Completely automated by the bot without needing any host or referee.
     - **Fixed 120-Second (2-minute) Countdown**: Once initiated, an exact 120-second countdown runs with progress updates at `60s`, `30s`, `10s`, `5s`, `4s`, `3s`, `2s`, `1s`.
     - **Restart Recovery**: The countdown target timestamp is persisted in `tournaments.json`. If the bot restarts during the countdown, it automatically recovers and resumes the remaining countdown seamlessly.
     - **Auto-Bracket & Byes**: Pairs players automatically into single-elimination fixtures. If the player count is odd, it handles byes automatically.
     - **Auto-Progression**: Automatically advances winners, starts subsequent matches, launches round 2/semis/finals, and crowns the tournament Champion!
   - **Mode 2: Host-Managed Tournament**
     - Manual host control with **no automatic start timer**.
     - Authorized hosts can organize registered players into **Team A** and **Team B**, set custom batting/bowling orders, manually pair matches, pause, resume, reset, resolve disputes, and declare winners.

3. **Atomic JSON Database Engine**:
   - Uses Python's native JSON library with dedicated `/data` folder.
   - **Zero external SQL or NoSQL database dependencies** (no SQLite, MongoDB, PostgreSQL, or Redis).
   - **15 dedicated JSON files**:
     * `users.json`, `statistics.json`, `tournaments.json`, `participants.json`, `teams.json`
     * `matches.json`, `innings.json`, `ball_history.json`, `hosts.json`, `admins.json`
     * `leaderboard.json`, `notifications.json`, `reports.json`, `audit_logs.json`, `settings.json`
   - **Concurrency Safety**: File-level threading and asynchronous locks (`FileLocker`).
   - **Atomic Writes**: Writes to temporary files and performs atomic `os.replace` to prevent partial or corrupted writes.
   - **Automated Backups & Self-Healing Recovery**: Rotational backups stored in `/data/backups`. Automatic recovery upon detecting malformed JSON.

4. **Web Admin Dashboard (React + TypeScript + Tailwind CSS)**:
   - Esports-style dark interface.
   - **Overview**: Real-time cards and telemetry for players, active matches, tournaments, and hosts.
   - **Player Management**: Search players, inspect profiles, review match history, ban/unban, and reset statistics.
   - **Tournament Management**: Create solo or host tournaments, view participants, manage team rosters, assign hosts, and archive tournaments.
   - **Host Management**: Authorize hosts, assign specific tournaments, and monitor activity.
   - **Match Telemetry**: Ball-by-ball inspection showing secret bowler numbers vs batsman numbers, match cancellation, and admin result overrides with permanent audit logging.
   - **System Rules**: Configure overs (max balls), countdown duration, wickets limit, and public matchmaking.
   - **Audit Logs**: Tamper-evident trail of all administrative interventions.

---

## 📁 Project Structure

```
hand_cricket_bot/
├── .env.example              # Environment variables template
├── Dockerfile                # Multi-stage production container build
├── docker-compose.yml        # Docker Compose with App and Nginx
├── nginx.conf                # Production reverse proxy configuration
├── requirements.txt          # Python 3.12+ dependencies
├── README.md                 # System documentation
├── config/
│   ├── __init__.py
│   └── settings.py           # Pydantic environment configuration
├── data/                     # Dedicated JSON file database
│   ├── users.json
│   ├── statistics.json
│   ├── tournaments.json
│   ├── participants.json
│   ├── teams.json
│   ├── matches.json
│   ├── innings.json
│   ├── ball_history.json
│   ├── hosts.json
│   ├── admins.json
│   ├── leaderboard.json
│   ├── notifications.json
│   ├── reports.json
│   ├── audit_logs.json
│   └── settings.json
├── database/
│   ├── __init__.py
│   ├── file_locker.py        # Asynchronous and threading concurrency locks
│   ├── validators.py         # Schema and input validation
│   ├── backup.py             # Backup creation, rotation, and recovery
│   └── json_manager.py       # Atomic read/write operations
├── game_engine/
│   ├── __init__.py
│   ├── models.py             # Pydantic models for Match, BallEvent, Innings
│   ├── engine.py             # Hand cricket game logic, scoring, and outs
│   └── scoreboard.py         # Scoreboard formatters and ball announcements
├── bot/
│   ├── __init__.py
│   ├── bot_instance.py       # Aiogram Bot & Dispatcher factory
│   ├── middlewares/
│   │   ├── auth_middleware.py        # Registration check & ban verification
│   │   └── rate_limit_middleware.py  # Anti-spam protection
│   ├── keyboards/
│   │   ├── game_keyboards.py         # 0-6 bowling (DM) and batting (group)
│   │   ├── host_keyboards.py         # 20-button Host Control Panel
│   │   └── admin_keyboards.py        # Superadmin inline management
│   ├── handlers/
│   │   ├── player_handlers.py        # /start, /profile, /stats, /leaderboard
│   │   ├── game_handlers.py          # Live dual-channel gameplay handlers
│   │   ├── host_handlers.py          # /host and host callback controls
│   │   └── admin_handlers.py         # /admin, /startsolo, /systemstats
│   └── services/
│       ├── stats_service.py          # Player career statistics & leaderboards
│       ├── tournament_service.py     # Brackets, byes, and fixtures
│       ├── solo_tournament_service.py# 120s countdown and auto-advancement
│       ├── host_tournament_service.py# Host authorizations and team rosters
│       ├── game_service.py           # Live match coordinator
│       └── notification_service.py   # Tournament broadcasts & alerts
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI application with static mount
│   ├── authentication/
│   │   └── auth.py           # JWT token issuance & authentication
│   └── api/
│       ├── players.py        # Player search, profiles, bans, resets
│       ├── tournaments.py    # Tournament creation, rosters, teams
│       ├── matches.py        # Live matches, ball history, overrides
│       ├── hosts.py          # Host assignment & management
│       └── settings.py       # System settings, audit logs, backups
├── admin_panel/              # React 18 + TypeScript + Tailwind CSS
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── App.tsx
│   │   ├── types/index.ts
│   │   ├── services/api.ts
│   │   ├── components/Sidebar.tsx
│   │   ├── components/Header.tsx
│   │   └── pages/            # Overview, Players, Tournaments, Matches, etc.
│   └── dist/                 # Production pre-built static bundle
├── tests/
│   ├── test_game_engine.py   # Game engine rules, scoring, and wickets
│   ├── test_json_manager.py  # Atomic writes, CRUD, and backups
│   ├── test_tournament.py    # Bracket generation, fixtures, and byes
│   ├── test_security.py      # Authorization, anti-cheat, and invalid moves
│   └── test_api.py           # FastAPI endpoints and JWT verification
└── scripts/
    └── run_all.py            # Unified async runner for Bot & FastAPI API
```

---

## 🎮 Telegram Bot Commands

### Player Commands
| Command | Description |
|---|---|
| `/start` | In groups: displays **[Start Solo]**, **[Start Tournament]**, **[Cancel]** buttons. In DM: welcome menu |
| `/start_solo [name]` | Immediately creates and starts a 120s automated Solo tournament |
| `/start_tournament [name]` | Immediately creates a Host tournament with `[I AM THE HOST]` claim button |
| `/help` | Complete categorized command list & guide |
| `/profile` | Shows user profile, Telegram ID, registration date, career win rate |
| `/stats` | Career statistics (matches, runs, average, highest score, streaks) |
| `/history` | Recent match history and results |
| `/leaderboard` | Global leaderboards: Most Wins, Total Runs, High Score, Win %, Streaks |
| `/tournaments` | Lists active tournaments with one-click registration buttons |
| `/mytournaments`| Displays all tournaments joined by the user |
| `/rules` | Complete rules of hand cricket |

### Host Team Commands
| Command | Description |
|---|---|
| `[ 🛡️ I AM THE HOST ]` | Claim official Host role for the tournament |
| `/add_a <@users>` | Add player(s) to Team A (supports multiple mentions or message reply) |
| `/add_b <@users>` | Add player(s) to Team B (supports multiple mentions or message reply) |
| `/cap_a <@user>` | Set Captain for Team A (supports mention or message reply) |
| `/cap_b <@user>` | Set Captain for Team B (supports mention or message reply) |
| `/overs <1-10>` | Set overs limit per innings (e.g. `/overs 2` or `/overs 5`) |
| `/teams` | View current Team A vs Team B rosters, captains, and host info |
| `/start_match [@p1 @p2]` | Launch match between Team A and Team B (captains or chosen players) |
| `/host` | Opens the full 20-button Host Control Panel |
| `/hosttournaments`| Displays tournaments assigned to the host |
| `/hostplayers [id]` | View players registered in the host's tournaments |
| `/hostmatches` | View live and completed matches |
| `/hostannounce <id> <msg>`| Broadcast an official announcement to the tournament group |

### SuperAdmin Commands
| Command | Description |
|---|---|
| `/admin` | Opens SuperAdmin system dashboard |
| `/createtournament [solo\|host] [name]` | Creates a new tournament in current group |
| `/setgroup <id>` | Bind any tournament to the current Telegram group |
| `/startsolo [id]` | Starts the automated 120-second countdown for a Solo Tournament |
| `/cancelsolo [id]` | Cancels an ongoing solo tournament countdown |
| `/players` | View registered player profiles and status |
| `/hosts` | View authorized host privileges |
| `/matches` | View live and historical matches |
| `/systemstats` | Real-time system telemetry (registered players, balls bowled, etc.) |

---

## 🛠️ Local Installation & Setup

### Prerequisites
- Python 3.12+
- Node.js 18+ (already bundled/built in `admin_panel/dist`)

### Step 1: Clone & Configure Environment
```bash
git clone <repository_url>
cd jplbot
cp .env.example .env
```

Edit `.env` with your real Telegram Bot credentials:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz_EXAMPLE
BOT_USERNAME=HandCricketOfficialBot
SUPER_ADMIN_ID=123456789
DEFAULT_GROUP_ID=-1001234567890
ADMIN_USERNAME=admin
ADMIN_PASSWORD=adminpassword123
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run Test Suite
```bash
pytest tests/ -v
```

### Step 4: Launch the Bot & Admin API Concurrently
```bash
python scripts/run_all.py
```
- Telegram Bot starts polling immediately.
- FastAPI backend starts on `http://0.0.0.0:8000`.
- Admin Web Dashboard is directly accessible at `http://localhost:8000/`.

---

## 🐳 Docker & Docker Compose Deployment

Run the entire stack (FastAPI, Telegram Bot, React Admin Dashboard, and Nginx Reverse Proxy) with a single command:

```bash
docker compose up -d --build
```

- Access the Admin Dashboard at: `http://<your-server-ip>/`
- API documentation (Swagger) at: `http://<your-server-ip>/docs`
- Stop the stack: `docker compose down`

---

## 🌐 Production VPS Deployment Guide (Ubuntu / Debian)

### 1. Provision Server
SSH into your VPS and install Docker & Docker Compose:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. Configure Firewall
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Deploy Application
```bash
git clone <repository_url> /opt/hand_cricket_bot
cd /opt/hand_cricket_bot
cp .env.example .env
nano .env  # Enter your production bot token, admin password, and group ID
docker compose up -d --build
```

### 4. Enable SSL with Certbot (Optional / Recommended)
Install Certbot on the host:
```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d yourdomain.com
```
Update `nginx.conf` to mount certificates from `/etc/letsencrypt/live/yourdomain.com/` and listen on port 443 with SSL enabled.

### 5. Automated Backup Cron Job
The bot automatically maintains rolling backups in `./data/backups`. You can also configure a daily offsite backup cron:
```bash
# In crontab -e
0 3 * * * tar -czf /var/backups/cricket_db_$(date +\%F).tar.gz /opt/hand_cricket_bot/data
```

---

## 🛡️ Anti-Cheat & Security Guarantee

1. **Callback Validation**:
   - The bot never trusts callback data payload alone. It validates the user's authentic numeric `from_user.id` against `match.current_bowler_id` or `match.current_batsman_id`. Spectators attempting to tap inline buttons are instantly rejected.
2. **Hidden Bowling Selection**:
   - The bowler's number is recorded in memory/JSON as a pending delivery and is never sent to the group or revealed until the batsman has committed their shot.
3. **Turn Order Integrity**:
   - A batsman cannot submit a move before the bowler delivers. A bowler cannot submit two deliveries in the same turn.
4. **Data Isolation**:
   - Hosts only possess permissions to manage tournaments specifically assigned to their user ID. SuperAdmin functions are protected via cryptographic JWT tokens and Telegram ID checks.
#   h a n d - c r i c k e t  
 #   h a n d - c r i c k e t  
 