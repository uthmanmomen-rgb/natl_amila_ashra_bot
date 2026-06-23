#!/usr/bin/env python3
from __future__ import annotations

import logging
from datetime import date, datetime, time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
)

from config import POLL_DAYS, POLL_OPTIONS, POLL_QUESTION, Settings, load_settings
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
        question=POLL_QUESTION,
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


async def send_monthly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    today = date.today()

    if today.day != POLL_DAYS + 1:
        return

    report = format_month_results(today.year, today.month)
    for chunk in split_message(report):
        await context.bot.send_message(chat_id=settings.admin_user_id, text=chunk)


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
    settings: Settings = context.application.bot_data["settings"]
    for chunk in split_message(report):
        await context.bot.send_message(chat_id=settings.admin_user_id, text=chunk)

    if update.effective_chat.id != settings.admin_user_id:
        await update.message.reply_text("Report sent to your DM.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    test_note = (
        "\n\nTest mode is ON — polls work any day. Use /poll force to resend today's poll."
        if settings.test_mode
        else ""
    )
    await update.message.reply_text(
        "Salat poll bot is running.\n\n"
        "Commands:\n"
        "/results — this month's results (sent to your DM)\n"
        "/results YYYY-MM — results for a specific month\n"
        "/poll — send today's poll now (admin)\n"
        "/poll force — resend today's poll (admin, test mode)\n"
        "/report — send this month's report to your DM (admin)"
        f"{test_note}"
    )


async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if update.effective_user.id != settings.admin_user_id:
        await update.message.reply_text("Only the admin can view results.")
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
    if update.effective_user.id != settings.admin_user_id:
        await update.message.reply_text("Only the admin can trigger polls.")
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
    if update.effective_user.id != settings.admin_user_id:
        await update.message.reply_text("Only the admin can request reports.")
        return

    today = date.today()
    report = format_month_results(today.year, today.month)
    await send_report_to_admin(update, context, report)


def schedule_jobs(application: Application, settings: Settings) -> None:
    job_queue = application.job_queue
    job_queue.run_daily(
        send_daily_poll,
        time=time(hour=settings.poll_hour, minute=0),
        name="daily_poll",
    )
    job_queue.run_daily(
        send_monthly_report,
        time=time(hour=settings.report_hour, minute=0),
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
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("poll", poll_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(PollAnswerHandler(poll_answer_handler))

    schedule_jobs(application, settings)

    if is_poll_day(settings) and not poll_exists(date.today()):
        application.job_queue.run_once(send_daily_poll, when=5)

    mode = "TEST MODE" if settings.test_mode else "normal"
    logger.info(
        "Bot started (%s). Poll chat=%s admin=%s",
        mode,
        settings.poll_chat_id,
        settings.admin_user_id,
    )
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
