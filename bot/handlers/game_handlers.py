from aiogram import Router, F, Bot
from aiogram.types import Message
from bot.services.game_service import GameService
from game_engine.models import MatchStatus

router = Router(name="game_handlers")

# 1. PRIVATE CHAT TYPED INPUT (Bowling in DM, or Batting in a DM /challenge_bot match)
@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def on_private_typed_input(message: Message, bot: Bot):
    user_id = message.from_user.id
    raw = message.text.strip()

    # Ensure active_matches is hydrated if bot restarted mid-match
    if not GameService.active_matches:
        await GameService.recover_active_matches()

    # Check if user is active bowler OR active DM batsman in a /challenge_bot match
    bowl_match = None
    dm_bat_match = None
    for match in GameService.active_matches.values():
        if match.status != MatchStatus.IN_PROGRESS:
            continue
        if match.current_bowler_id == user_id and match.pending_bowler_number is None:
            bowl_match = match
            break
        if match.group_chat_id == user_id and match.current_batsman_id == user_id and match.pending_bowler_number is not None:
            dm_bat_match = match
            break

    target_match = bowl_match or dm_bat_match
    if not target_match:
        return

    # Validate numeric input
    if not raw.isdigit():
        role_label = "bowl" if bowl_match else "bat"
        await message.reply(
            f"⚠️ Invalid input! Please type a valid number between {target_match.min_number} and {target_match.max_number} to {role_label}."
        )
        return

    number = int(raw)
    if number < target_match.min_number or number > target_match.max_number:
        await message.reply(
            f"⚠️ Out of range! Numbers must be between {target_match.min_number} and {target_match.max_number}."
        )
        return

    if bowl_match:
        from game_engine.bot_ai import BotPsychologyEngine
        is_vs_bot = (bowl_match.current_batsman_id == BotPsychologyEngine.BOT_USER_ID)
        await GameService.react_positive(message)
        if is_vs_bot:
            await message.reply(
                f"🔒 <b>BALL DELIVERED: {number}</b>\n🤖 @HandCricketAI is playing its shot...",
                parse_mode="HTML"
            )
        success, msg = await GameService.handle_bowler_delivery(bowl_match.match_id, user_id, number, bot)
        if success and not is_vs_bot:
            await message.reply(
                f"🔒 <b>BALL DELIVERED!</b>\n\nYour secret delivery: <b>{number}</b>\n\nWaiting for @{bowl_match.current_batsman_username} to bat!",
                parse_mode="HTML"
            )
        elif not success:
            await message.reply(f"⚠️ {msg}")
    else:
        success, msg = await GameService.handle_batsman_shot(dm_bat_match.match_id, user_id, number, bot)
        if success:
            await GameService.react_positive(message)
        else:
            await message.reply(f"⚠️ {msg}")

# 2. GROUP CHAT TYPED INPUT (Batsman typing in group)
@router.message(F.chat.type.in_({"group", "supergroup"}), F.text, ~F.text.startswith("/"))
async def on_group_typed_input(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    raw = message.text.strip()

    # Ensure active_matches is hydrated if bot restarted mid-match
    if not GameService.active_matches:
        await GameService.recover_active_matches()

    # Find active match in this group where user is the active batsman waiting to play
    target_match = None
    for match in GameService.active_matches.values():
        if (
            match.status == MatchStatus.IN_PROGRESS
            and match.group_chat_id == chat_id
            and match.current_batsman_id == user_id
            and match.pending_bowler_number is not None
        ):
            target_match = match
            break

    if not target_match:
        # Helpful nudge if the active bowler accidentally typed a number in the group instead of Bot DM
        if raw.isdigit() and 0 <= int(raw) <= 6:
            for match in GameService.active_matches.values():
                if (
                    match.status == MatchStatus.IN_PROGRESS
                    and match.group_chat_id == chat_id
                    and match.current_bowler_id == user_id
                    and match.pending_bowler_number is None
                ):
                    from bot.keyboards.game_keyboards import get_go_to_dm_keyboard
                    await message.reply(
                        "🎯 You are bowling! Please type your number privately in Bot DM:",
                        reply_markup=get_go_to_dm_keyboard(GameService._get_bot_username(bot))
                    )
                    break
        return

    # Validate numeric input when active batsman's turn is expected
    if not raw.isdigit():
        await message.reply(
            f"⚠️ Invalid input! Please type a number between {target_match.min_number} and {target_match.max_number} to play your shot."
        )
        return

    number = int(raw)
    if number < target_match.min_number or number > target_match.max_number:
        await message.reply(
            f"⚠️ Out of range! Batting numbers must be between {target_match.min_number} and {target_match.max_number}."
        )
        return

    success, msg = await GameService.handle_batsman_shot(target_match.match_id, user_id, number, bot)
    if success:
        await GameService.react_positive(message)
    else:
        await message.reply(f"⚠️ {msg}")
