import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

POLL_QUESTION = (
    "How many prayers have you offered at the mosque or salat center today?"
)
POLL_OPTIONS = [
    "1 prayer",
    "2 prayers",
    "3 prayers",
    "4 prayers",
    "5 prayers",
    "Sick / Traveling",
]
POLL_DAYS = 10


@dataclass(frozen=True)
class Settings:
    bot_token: str
    poll_chat_id: int
    admin_user_id: int
    poll_hour: int
    poll_minute: int
    report_hour: int
    report_minute: int
    test_mode: bool


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    poll_chat_id = os.environ.get("POLL_CHAT_ID", "").strip()
    admin_user_id = os.environ.get("ADMIN_USER_ID", "").strip()
    if not poll_chat_id or not admin_user_id:
        raise ValueError("POLL_CHAT_ID and ADMIN_USER_ID are required")

    poll_hour = int(os.environ.get("POLL_HOUR", "8"))
    poll_minute = int(os.environ.get("POLL_MINUTE", "0"))
    report_hour = int(os.environ.get("REPORT_HOUR", "9"))
    report_minute = int(os.environ.get("REPORT_MINUTE", "0"))
    test_mode = _env_bool("TEST_MODE")

    for name, value in (
        ("POLL_HOUR", poll_hour),
        ("REPORT_HOUR", report_hour),
    ):
        if not 0 <= value <= 23:
            raise ValueError(f"{name} must be between 0 and 23")
    for name, value in (
        ("POLL_MINUTE", poll_minute),
        ("REPORT_MINUTE", report_minute),
    ):
        if not 0 <= value <= 59:
            raise ValueError(f"{name} must be between 0 and 59")

    return Settings(
        bot_token=token,
        poll_chat_id=int(poll_chat_id),
        admin_user_id=int(admin_user_id),
        poll_hour=poll_hour,
        poll_minute=poll_minute,
        report_hour=report_hour,
        report_minute=report_minute,
        test_mode=test_mode,
    )
