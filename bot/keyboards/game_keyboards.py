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
            InlineKeyboardButton(text="🏏 Start Solo", callback_data="menu:start_solo"),
            InlineKeyboardButton(text="🏆 Start Tournament", callback_data="menu:start_tourn")
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data="menu:cancel")
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
