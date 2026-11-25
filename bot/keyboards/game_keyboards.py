from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_go_to_dm_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """
    URL button that takes the bowler straight to the bot's private DM.
    """
    clean_username = bot_username.lstrip("@")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Go to Bot DM", url=f"https://t.me/{clean_username}")
        ]
    ])

def get_group_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Start Solo Cup", callback_data="menu:start_solo"),
            InlineKeyboardButton(text="🏟️ Host Tournament", callback_data="menu:start_tourn")
        ],
        [
            InlineKeyboardButton(text="🤖 Challenge Bot", callback_data="hub:challenge_bot"),
            InlineKeyboardButton(text="📖 Rule Book", callback_data="rules:basics")
        ],
        [
            InlineKeyboardButton(text="🏅 Leaderboard", callback_data="lb:wins"),
            InlineKeyboardButton(text="❌ Close", callback_data="menu:cancel")
        ]
    ])

def get_dm_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Play vs Smart Bot", callback_data="hub:challenge_bot"),
            InlineKeyboardButton(text="🏆 Tournaments", callback_data="hub:tournaments")
        ],
        [
            InlineKeyboardButton(text="📖 Rule Book", callback_data="rules:basics"),
            InlineKeyboardButton(text="📊 My Profile & Stats", callback_data="hub:profile")
        ],
        [
            InlineKeyboardButton(text="🏅 Leaderboard", callback_data="lb:wins"),
            InlineKeyboardButton(text="📜 Match History", callback_data="hub:history")
        ],
        [
            InlineKeyboardButton(text="📋 Commands", callback_data="hub:help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="hub:about")
        ]
    ])

def get_rulebook_keyboard(active_page: str = "basics") -> InlineKeyboardMarkup:
    def _lbl(key: str, text: str) -> str:
        return f"• {text} •" if active_page == key else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_lbl("basics", "🏏 Basics"), callback_data="rules:basics"),
            InlineKeyboardButton(text=_lbl("ball", "🎯 Ball Flow"), callback_data="rules:ball")
        ],
        [
            InlineKeyboardButton(text=_lbl("tourn", "🏆 Tournaments"), callback_data="rules:tourn"),
            InlineKeyboardButton(text=_lbl("timers", "⏱️ Timers & Tie"), callback_data="rules:timers")
        ],
        [
            InlineKeyboardButton(text=_lbl("ai", "🤖 Smart Bot"), callback_data="rules:ai"),
            InlineKeyboardButton(text="⬅️ Main Menu", callback_data="hub:main")
        ]
    ])

def get_profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Profile", callback_data="hub:profile"),
            InlineKeyboardButton(text="📈 Stats", callback_data="hub:stats"),
            InlineKeyboardButton(text="📜 History", callback_data="hub:history")
        ],
        [
            InlineKeyboardButton(text="🏅 Leaderboard", callback_data="lb:wins"),
            InlineKeyboardButton(text="⬅️ Main Menu", callback_data="hub:main")
        ]
    ])

def get_leaderboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Wins", callback_data="lb:wins"),
            InlineKeyboardButton(text="🏏 Runs", callback_data="lb:runs")
        ],
        [
            InlineKeyboardButton(text="🌟 High Score", callback_data="lb:high"),
            InlineKeyboardButton(text="🔥 Win %", callback_data="lb:winpct")
        ],
        [
            InlineKeyboardButton(text="⚡ Streak", callback_data="lb:streak"),
            InlineKeyboardButton(text="⬅️ Main Menu", callback_data="hub:main")
        ]
    ])

def get_match_end_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Play vs Bot", callback_data="hub:challenge_bot"),
            InlineKeyboardButton(text="🏅 Leaderboard", callback_data="lb:wins"),
            InlineKeyboardButton(text="📖 Rule Book", callback_data="rules:basics")
        ]
    ])

def get_claim_host_keyboard(tournament_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛡️ I AM THE HOST", callback_data=f"claim_host:{tournament_id}")
        ]
    ])

def get_toss_call_keyboard(toss_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🪙 Heads", callback_data=f"toss_call:{toss_id}:heads"),
            InlineKeyboardButton(text="🪙 Tails", callback_data=f"toss_call:{toss_id}:tails")
        ]
    ])

def get_toss_choice_keyboard(toss_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏏 Bat First", callback_data=f"toss_pick:{toss_id}:bat"),
            InlineKeyboardButton(text="🎯 Bowl First", callback_data=f"toss_pick:{toss_id}:bowl")
        ]
    ])

def get_tournament_register_keyboard(tournament_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏏 Register for Tournament", callback_data=f"treg:{tournament_id}"),
            InlineKeyboardButton(text="🚪 Withdraw", callback_data=f"twid:{tournament_id}")
        ],
        [
            InlineKeyboardButton(text="👥 View Participants", callback_data=f"tpart:{tournament_id}"),
            InlineKeyboardButton(text="⚡ Force Start", callback_data=f"tforce:{tournament_id}")
        ]
    ])
