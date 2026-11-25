from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="👥 Manage Players", callback_data="admin:players"),
            InlineKeyboardButton(text="🛡️ Manage Hosts", callback_data="admin:hosts")
        ],
        [
            InlineKeyboardButton(text="🏆 Tournaments", callback_data="admin:tournaments"),
            InlineKeyboardButton(text="⚔️ Live Matches", callback_data="admin:matches")
        ],
        [
            InlineKeyboardButton(text="⚙️ System Settings", callback_data="admin:settings"),
            InlineKeyboardButton(text="📈 System Stats", callback_data="admin:systemstats")
        ],
        [
            InlineKeyboardButton(text="💾 Create DB Backup", callback_data="admin:backup"),
            InlineKeyboardButton(text="📜 Audit Logs", callback_data="admin:audit")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
