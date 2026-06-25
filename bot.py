#!/usr/bin/env python3
from __future__ import annotations

import logging
from datetime import date, datetime, time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PollAnswerHandler,
    filters,
)

from config import POLL_DAYS, POLL_OPTIONS, Settings, load_settings, poll_question
from database import (
    get_poll_by_telegram_id,
    init_db,
    poll_exists,
    save_poll,
    save_vote,
)
from reports import format_month_results, split_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def display_name(user) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part for part in parts if part).strip()
    if user.username:
        suffix = f" (@{user.username})"
        return f"{name}{suffix}" if name else f"@{user.username}"
    return name or f"User {user.id}"


def is_poll_day(settings: Settings, day: date | None = None) -> bool:
    current = day or date.today()
    if settings.test_mode:
        return True
    return 1 <= current.day <= POLL_DAYS


async def send_daily_poll(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    force: bool = False,
) -> bool:
    settings: Settings = context.application.bot_data["settings"]
    today = date.today()

    if not is_poll_day(settings, today):
        return False
    if poll_exists(today) and not force:
        logger.info("Poll already sent for %s", today.isoformat())
        return False

    message = await context.bot.send_poll(
        chat_id=settings.poll_chat_id,
        question=poll_question(today),
        options=POLL_OPTIONS,
        is_anonymous=False,
        allows_multiple_answers=False,
    )

    save_poll(
        poll_date=today,
        telegram_poll_id=message.poll.id,
        message_id=message.message_id,
        chat_id=settings.poll_chat_id,
    )
    logger.info("Sent poll for %s (message_id=%s)", today.isoformat(), message.message_id)
    return True


def is_admin(settings: Settings, user_id: int) -> bool:
    return user_id in settings.admin_user_ids


async def send_report_chunks(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    report: str,
) -> None:
    for chunk in split_message(report):
        await context.bot.send_message(chat_id=user_id, text=chunk)


async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    today = date.today()

    if today.day != POLL_DAYS + 1:
        return

    report = format_month_results(today.year, today.month)
    for admin_id in settings.admin_user_ids:
        await send_report_chunks(context, admin_id, report)


async def poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    answer = update.poll_answer
    if not answer or not answer.option_ids:
        return

    poll_row = get_poll_by_telegram_id(answer.poll_id)
    if not poll_row:
        logger.warning("Unknown poll id: %s", answer.poll_id)
        return

    poll_date = date.fromisoformat(poll_row["poll_date"])
    option_index = answer.option_ids[0]
    if option_index >= len(POLL_OPTIONS):
        logger.warning("Invalid option index %s for poll %s", option_index, answer.poll_id)
        return

    user = answer.user
    save_vote(
        poll_date=poll_date,
        user_id=user.id,
        user_name=display_name(user),
        option_index=option_index,
        option_text=POLL_OPTIONS[option_index],
    )


async def send_report_to_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    report: str,
) -> None:
    recipient_id = update.effective_user.id
    await send_report_chunks(context, recipient_id, report)

    if update.effective_chat.id != recipient_id:
        await update.message.reply_text("Report sent to your DM.")


def build_help_text(settings: Settings, user_id: int) -> str:
    if is_admin(settings, user_id):
        test_note = (
            "\n\nTest mode is ON — polls work any day. Use /poll force to resend today's poll."
            if settings.test_mode
            else ""
        )
        return (
            "Salat poll bot\n\n"
            "Voting happens in the group — answer each day's poll there "
            f"(days 1–{POLL_DAYS} of the month).\n\n"
            "Admin commands (use here in DM):\n"
            "/results — this month's results\n"
            "/results YYYY-MM — results for a specific month\n"
            "/poll — send today's poll to the group\n"
            "/poll force — resend today's poll (test mode only)\n"
            "/report — this month's report"
            f"{test_note}"
        )

    return (
        "Salat poll bot\n\n"
        "Daily prayer polls are posted in the group. Tap the poll there to record "
        f"your answer (days 1–{POLL_DAYS} of each month).\n\n"
        "This bot does not take votes by DM — use the poll in the group.\n\n"
        "Send /start anytime to see this message again."
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text(
        build_help_text(settings, update.effective_user.id)
    )


async def dm_help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or update.effective_chat.type != "private":
        return
    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_text(
        build_help_text(settings, update.effective_user.id)
    )


async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not is_admin(settings, update.effective_user.id):
        await update.message.reply_text("Only admins can view results.")
        return

    if context.args:
        try:
            year_str, month_str = context.args[0].split("-", 1)
            year, month = int(year_str), int(month_str)
            datetime(year, month, 1)
        except (ValueError, IndexError):
            await update.message.reply_text("Use /results or /results 2026-06")
            return
    else:
        today = date.today()
        year, month = today.year, today.month

    report = format_month_results(year, month)
    await send_report_to_admin(update, context, report)


async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not is_admin(settings, update.effective_user.id):
        await update.message.reply_text("Only admins can trigger polls.")
        return

    force = bool(context.args and context.args[0].lower() == "force")
    if force and not settings.test_mode:
        await update.message.reply_text("Use /poll force only when TEST_MODE is enabled.")
        return

    if not is_poll_day(settings):
        await update.message.reply_text(
            f"Polls are only sent on days 1–{POLL_DAYS} of the month. "
            "Set TEST_MODE=true in .env to test anytime."
        )
        return

    sent = await send_daily_poll(context, force=force)
    if sent:
        await update.message.reply_text("Poll sent.")
    else:
        await update.message.reply_text(
            "Poll already sent for today. Use /poll force in test mode to send another."
        )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not is_admin(settings, update.effective_user.id):
        await update.message.reply_text("Only admins can request reports.")
        return

    today = date.today()
    report = format_month_results(today.year, today.month)
    await send_report_to_admin(update, context, report)


def schedule_jobs(application: Application, settings: Settings) -> None:
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_poll,
        time=time(hour=settings.poll_hour, minute=settings.poll_minute),
        name="daily_poll",
    )
    job_queue.run_daily(
        send_monthly_report,
        time=time(hour=settings.report_hour, minute=settings.report_minute),
        name="monthly_report",
    )


def main() -> None:
    settings = load_settings()
    init_db()

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("poll", poll_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, dm_help_handler)
    )
    application.add_handler(PollAnswerHandler(poll_answer_handler))

    schedule_jobs(application, settings)

    mode = "TEST MODE" if settings.test_mode else "normal"
    logger.info(
        "Bot started (%s). Poll chat=%s admins=%s",
        mode,
        settings.poll_chat_id,
        sorted(settings.admin_user_ids),
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
