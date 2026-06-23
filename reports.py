from __future__ import annotations

from calendar import month_name
from datetime import date

from config import POLL_DAYS, POLL_OPTIONS
from database import get_month_votes


def format_month_results(year: int, month: int) -> str:
    votes_by_day = get_month_votes(year, month)
    month_label = month_name[month]
    lines = [f"Prayer poll results — {month_label} {year}", ""]

    poll_days = {date(year, month, day_num) for day_num in range(1, POLL_DAYS + 1)}

    for day_num in range(1, POLL_DAYS + 1):
        poll_date = date(year, month, day_num)
        day_votes = votes_by_day.get(poll_date, [])
        lines.append(f"Day {day_num} ({poll_date.strftime('%b %d')}):")

        if not day_votes:
            lines.append("  (no responses)")
        else:
            for vote in day_votes:
                lines.append(f"  {vote['user_name']}: {vote['option_text']}")

        lines.append("")

    extra_dates = sorted(day for day in votes_by_day if day not in poll_days)
    if extra_dates:
        lines.append("Additional polls (outside days 1–10):")
        for poll_date in extra_dates:
            lines.append(f"{poll_date.strftime('%b %d')}:")
            for vote in votes_by_day[poll_date]:
                lines.append(f"  {vote['user_name']}: {vote['option_text']}")
            lines.append("")

    lines.append("Summary by person:")
    person_totals: dict[str, list[str]] = {}
    for poll_date in sorted(votes_by_day):
        for vote in votes_by_day[poll_date]:
            label = (
                f"Day {poll_date.day}"
                if poll_date in poll_days
                else poll_date.strftime("%b %d")
            )
            person_totals.setdefault(vote["user_name"], []).append(
                f"{label}: {vote['option_text']}"
            )

    if not person_totals:
        lines.append("  (no responses this month)")
    else:
        for name in sorted(person_totals, key=str.casefold):
            answers = person_totals[name]
            lines.append(f"  {name}: {', '.join(answers)}")

    lines.append("")
    lines.append(f"Options were: {', '.join(POLL_OPTIONS)}")
    return "\n".join(lines)


def split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit and current:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current.rstrip())
    return chunks
