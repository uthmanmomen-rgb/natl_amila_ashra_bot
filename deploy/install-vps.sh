#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/telegram_poll_bot"
REPO_URL="${REPO_URL:-}"  # optional: git clone URL

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/install-vps.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git

id -u bot &>/dev/null || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin bot
mkdir -p "$APP_DIR"
chown bot:bot "$APP_DIR"

if [[ -n "$REPO_URL" ]]; then
  sudo -u bot git clone "$REPO_URL" "$APP_DIR"
else
  echo "Copy project files to $APP_DIR (rsync/scp), then re-run this script."
fi

sudo -u bot python3 -m venv "$APP_DIR/.venv"
sudo -u bot "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "Create $APP_DIR/.env from .env.example before starting the service."
fi

cp "$APP_DIR/deploy/telegram-poll-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable telegram-poll-bot

echo "Done. Edit $APP_DIR/.env, set TEST_MODE=false, then:"
echo "  systemctl start telegram-poll-bot"
echo "  journalctl -u telegram-poll-bot -f"
