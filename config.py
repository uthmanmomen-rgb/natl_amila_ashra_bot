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
    report_hour: int
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
    report_hour = int(os.environ.get("REPORT_HOUR", "9"))
    test_mode = _env_bool("TEST_MODE")

    return Settings(
        bot_token=token,
        poll_chat_id=int(poll_chat_id),
        admin_user_id=int(admin_user_id),
        poll_hour=poll_hour,
        report_hour=report_hour,
        test_mode=test_mode,
    )
