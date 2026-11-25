from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_host_dashboard_keyboard(tournament_id: str = "") -> InlineKeyboardMarkup:
    """
    Host Telegram Control Panel with all required host buttons.
    """
    tid = tournament_id or "none"
    keyboard = [
        [
            InlineKeyboardButton(text="➕ Create Tournament", callback_data="host:create_tourn"),
            InlineKeyboardButton(text="📋 Select Tournament", callback_data="host:select_tourn")
        ],
        [
            InlineKeyboardButton(text="👤 Add Player", callback_data=f"host:add_player:{tid}"),
            InlineKeyboardButton(text="❌ Remove Player", callback_data=f"host:remove_player:{tid}"),
            InlineKeyboardButton(text="👥 View Players", callback_data=f"host:view_players:{tid}")
        ],
        [
            InlineKeyboardButton(text="🔴 Manage Team A", callback_data=f"host:team_a:{tid}"),
            InlineKeyboardButton(text="🔵 Manage Team B", callback_data=f"host:team_b:{tid}"),
            InlineKeyboardButton(text="📊 View Teams", callback_data=f"host:view_teams:{tid}")
        ],
        [
            InlineKeyboardButton(text="⚔️ Select Match", callback_data=f"host:select_match:{tid}"),
            InlineKeyboardButton(text="🏏 Select Batsman", callback_data=f"host:select_bat:{tid}"),
            InlineKeyboardButton(text="🎯 Select Bowler", callback_data=f"host:select_bowl:{tid}")
        ],
        [
            InlineKeyboardButton(text="🚀 Start Tournament", callback_data=f"host:start_tourn:{tid}"),
            InlineKeyboardButton(text="▶️ Start Match", callback_data=f"host:start_match:{tid}")
        ],
        [
            InlineKeyboardButton(text="⏸️ Pause Match", callback_data=f"host:pause_match:{tid}"),
            InlineKeyboardButton(text="▶️ Resume Match", callback_data=f"host:resume_match:{tid}"),
            InlineKeyboardButton(text="⏹️ End Match", callback_data=f"host:end_match:{tid}")
        ],
        [
            InlineKeyboardButton(text="🔄 Reset Match", callback_data=f"host:reset_match:{tid}"),
            InlineKeyboardButton(text="📊 View Scoreboard", callback_data=f"host:scoreboard:{tid}"),
            InlineKeyboardButton(text="📜 Match History", callback_data=f"host:history:{tid}")
        ],
        [
            InlineKeyboardButton(text="🏆 Declare Winner", callback_data=f"host:dec_winner:{tid}"),
            InlineKeyboardButton(text="⏭️ Next Round", callback_data=f"host:next_round:{tid}"),
            InlineKeyboardButton(text="🏁 Finish Tournament", callback_data=f"host:finish_tourn:{tid}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
