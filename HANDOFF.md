# Telegram Salat Poll Bot — Handoff

**Project path:** `/Users/umomen/workdir/telegram_poll_bot`  
**Bot:** `@ashra_poll_bot` (created via BotFather)  
**Purpose:** Post a daily prayer-count poll in a Telegram group on days 1–10 of each month, track who voted and what they chose, and send the admin a monthly report with names and results.

---

## What the bot does

1. **Days 1–10 of each month** — at `POLL_HOUR`, posts a non-anonymous poll to the configured group:
   - *"How many prayers have you offered at the mosque or salat center today?"*
   - Options: `1 prayer`, `2 prayers`, `3 prayers`, `4 prayers`, `5 prayers`, `Sick / Traveling`
2. **Vote tracking** — stores each voter's display name and answer in SQLite (`poll_data.db`). Votes update if someone changes their answer.
3. **Day 11** — at `REPORT_HOUR`, automatically DMs the admin the full monthly report.
4. **Admin commands** — poll trigger, on-demand reports, and historical results (admin only).

Uses **long polling** (not webhooks). Only **one instance** of the bot may run per token at a time.

---

## Current configuration (as of handoff)

| Setting | Value | Notes |
|---------|-------|-------|
| Group | **Tarbiyyat Poll test** | `POLL_CHAT_ID=-5301570043` |
| Admin | **Uthman Momen** | `ADMIN_USER_ID=84589745` |
| `POLL_HOUR` | `21` | Local hour (depends on server `TZ`) |
| `REPORT_HOUR` | `22` | Auto-report on day 11 only |
| `TEST_MODE` | `true` | **Set to `false` for production** |

Token lives in `.env` only — never commit it. `.env` is in `.gitignore`.

---

## Project structure

```
telegram_poll_bot/
├── bot.py                 # Main entry point: handlers, scheduling, commands
├── config.py              # Poll text/options, settings from env
├── database.py            # SQLite schema and vote storage
├── reports.py             # Monthly report formatting
├── get_chat_id.py         # Helper to discover chat IDs from bot updates
├── requirements.txt       # Python dependencies
├── .env                   # Secrets (local only, gitignored)
├── .gitignore
├── poll_data.db           # SQLite data (gitignored, created at runtime)
├── Dockerfile             # Container image for Docker / JRMA
├── docker-compose.yml     # Local Docker run with volume for DB
├── HANDOFF.md             # This file
└── deploy/
    ├── prepare-jrma-zip.sh      # Zip project for JustRunMy.App upload
    ├── install-vps.sh           # VPS setup helper (systemd)
    └── telegram-poll-bot.service # systemd unit file
```

---

## Dependencies

```
python-telegram-bot[job-queue]==21.10
python-dotenv==1.0.1
```

- **Python:** tested on 3.9.6 (uses `from __future__ import annotations` for 3.9 compatibility)
- **APScheduler** (via job-queue extra): daily poll and monthly report jobs

---

## Environment variables

Create `.env` in the project root:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
POLL_CHAT_ID=-5301570043
ADMIN_USER_ID=84589745
POLL_HOUR=21
REPORT_HOUR=22
TEST_MODE=false
```

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | BotFather token |
| `POLL_CHAT_ID` | Yes | Group/channel where polls are posted (negative for groups) |
| `ADMIN_USER_ID` | Yes | Your Telegram user ID — reports and admin commands |
| `POLL_HOUR` | No (default `8`) | Hour (0–23) to post daily poll |
| `REPORT_HOUR` | No (default `9`) | Hour (0–23) on day 11 for auto-report |
| `TEST_MODE` | No (default `false`) | `true` = polls work any day of the month |

On cloud hosts, also set `TZ` (e.g. `America/Los_Angeles`) so poll/report hours match your local time.

---

## Commands and permissions

| Command | Who | Behavior |
|---------|-----|----------|
| `/start` | Anyone | Shows help text |
| `/poll` | Admin only | Sends today's poll to the group |
| `/poll force` | Admin only | Resends poll even if one exists today (requires `TEST_MODE=true`) |
| `/report` | Admin only | Sends current month's report **to admin DM** |
| `/results` | Admin only | Same as `/report` |
| `/results 2026-06` | Admin only | Report for a specific month, sent to admin DM |

**DM vs group:**
- `/report` and `/results` always deliver the full report to the admin's **private DM**, even if the command is run in the group. The group only sees: *"Report sent to your DM."*
- Voting happens in the **group poll**, not via DM.

**Non-admin users** can DM the bot and run `/start`, but admin commands return *"Only the admin can..."*.

---

## Scheduling logic

| Event | When | Notes |
|-------|------|-------|
| Daily poll | `POLL_HOUR` on days 1–10 | Skipped if poll already sent that day |
| Startup poll | 5 seconds after boot | Only if today is a poll day and no poll exists yet |
| Auto monthly report | `REPORT_HOUR` on day 11 | DM to admin only |
| Test mode | `TEST_MODE=true` | Polls allowed any day; `/poll force` enabled |

---

## Database (`poll_data.db`)

SQLite file in project root. Created automatically on first run.

**`polls` table**
- `poll_date` (PK) — ISO date, e.g. `2026-06-21`
- `telegram_poll_id` — Telegram's poll ID (links votes)
- `message_id`, `chat_id`, `created_at`

**`votes` table**
- `poll_date` + `user_id` (PK)
- `user_name` — e.g. `Uthman Momen (@UthmanMomen)`
- `option_index`, `option_text`, `updated_at`

Inspect locally:
```bash
sqlite3 poll_data.db "SELECT * FROM polls; SELECT * FROM votes;"
```

---

## Report format

Reports list days 1–10 with per-person answers, then a summary by person.

If votes exist outside days 1–10 (e.g. during test mode), they appear under **"Additional polls (outside days 1–10)"** — this was added after a bug where test votes on day 21 were invisible in reports.

Example section:
```
Day 1 (Jun 01):
  Ahmad (@ahmad): 3 prayers

Additional polls (outside days 1–10):
Jun 21:
  Uthman Momen (@UthmanMomen): 1 prayer

Summary by person:
  Uthman Momen (@UthmanMomen): Jun 21: 1 prayer
```

Long reports are split into chunks under 4000 characters for Telegram limits.

---

## Local development

```bash
cd /Users/umomen/workdir/telegram_poll_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# create/edit .env
python bot.py
```

**Stop any other instance** (local or cloud) before starting — duplicate polling causes missed updates.

### Find chat IDs

```bash
python get_chat_id.py --wait
```

1. Add bot to group (or DM it)
2. Send a message in that chat
3. Copy the `Chat ID` from output

If group messages don't appear: BotFather → `/setprivacy` → your bot → **Disable**, then send another group message.

**While `get_chat_id.py` runs, `bot.py` must be stopped** — both compete for the same updates.

---

## Deployment options

### Recommended: JustRunMy.App

Best fit for this bot — runs Python with polling, no rewrite needed.

```bash
bash deploy/prepare-jrma-zip.sh   # creates telegram_poll_bot.zip
```

1. Sign up at https://justrunmy.app
2. Dashboard → Add App → Zip Upload
3. Set env vars in panel (do **not** upload `.env`)
4. Start command: `python bot.py`
5. No HTTPS port needed (polling bot)
6. Set `TZ` in env vars for correct poll hours
7. Set `TEST_MODE=false` for production

### Docker (local or any host)

```bash
docker compose up -d --build
docker compose logs -f
```

`poll_data.db` is mounted as a volume.

### VPS + systemd

```bash
rsync -av --exclude .venv --exclude poll_data.db \
  ./ user@server:/opt/telegram_poll_bot/
sudo bash /opt/telegram_poll_bot/deploy/install-vps.sh
# edit /opt/telegram_poll_bot/.env
sudo systemctl start telegram-poll-bot
sudo journalctl -u telegram-poll-bot -f
```

Edit `TZ` in `deploy/telegram-poll-bot.service` before enabling.

### Not compatible: TeleBotHost

TeleBotHost uses **TBL** (its own scripting language), not Python. This bot cannot be uploaded there without a full rewrite.

---

## Telegram setup checklist

- [ ] Bot created in BotFather
- [ ] Bot added to group **Tarbiyyat Poll test**
- [ ] Bot can post polls (group permissions / admin if needed)
- [ ] Privacy mode disabled if bot needs to see all group messages (for `get_chat_id.py`; polls work without this)
- [ ] Only one bot instance running (local OR cloud, not both)
- [ ] `TEST_MODE=false` before going live
- [ ] `TZ` set correctly on server

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `TypeError: unsupported operand type(s) for \|` | Python 3.9 — fixed with `from __future__ import annotations` in all `.py` files |
| `get_chat_id.py` finds nothing | Stop `bot.py`, send message in group, retry with `--wait` |
| Report shows no votes | Vote was on day 11+ during test — now shown under "Additional polls"; restart bot after code update |
| Bot not responding | Check only one instance is running; check token in `.env` |
| Poll not posting to group | Verify `POLL_CHAT_ID`, bot permissions in group |
| Wrong poll time | Set `TZ` env var on server; check `POLL_HOUR` |
| "Only the admin can..." | User ID must match `ADMIN_USER_ID` exactly |

---

## Architecture (high level)

```
bot.py
  ├── APScheduler jobs (daily poll, monthly report)
  ├── CommandHandlers (/start, /poll, /report, /results)
  └── PollAnswerHandler → database.save_vote()

database.py → poll_data.db (SQLite)
reports.py  → format_month_results() from DB rows
config.py   → env vars + poll question/options
```

Polling flow:
1. Bot sends poll to `POLL_CHAT_ID`
2. Saves `telegram_poll_id` → `poll_date` mapping
3. User votes → Telegram sends `PollAnswer` update
4. Handler looks up poll by ID, saves vote with user name

---

## Production checklist

Before going live:

1. Set `TEST_MODE=false`
2. Deploy to always-on host (JustRunMy.App, VPS, or Docker)
3. Stop local `python bot.py` on your Mac
4. Set `TZ` to your timezone
5. Confirm `POLL_HOUR` and `REPORT_HOUR` are correct
6. Test: `/poll` in DM → vote in group → `/report` in DM
7. Verify auto-report on day 11 at `REPORT_HOUR`

---

## Possible future enhancements (not implemented)

- Restrict `/start` and DMs to admin only
- Remind users who haven't voted
- Multiple admins
- Export report as CSV
- Webhook mode (not needed for current hosting)
- Recreate `.env.example` file (was removed; template is in this doc)

---

## Session history summary

Built from scratch in Cursor conversation:

1. Created Python Telegram poll bot with SQLite storage
2. Added `get_chat_id.py` helper (Python 3.9 fix)
3. Configured for group **Tarbiyyat Poll test** and admin **Uthman Momen**
4. Added `TEST_MODE` for off-month testing
5. Fixed report to show votes outside days 1–10
6. Added deployment files (Docker, systemd, JRMA zip script)
7. Changed `/report` and `/results` to always DM the admin (never post full report in group)
8. Discussed hosting: TeleBotHost (not suitable), JustRunMy.App (recommended)

---

## Quick reference

```bash
# Run locally
source .venv/bin/activate && python bot.py

# Package for JustRunMy.App
bash deploy/prepare-jrma-zip.sh

# Find chat IDs
python get_chat_id.py --wait

# Check votes
sqlite3 poll_data.db "SELECT * FROM votes;"
```

**Admin test flow:** DM bot → `/poll force` → vote in group → DM bot → `/report`
