#!/usr/bin/env python3
from __future__ import annotations

"""Print Telegram chat IDs from recent bot updates.

Usage:
  1. Add your bot to the group (or open a DM with it).
  2. Send any message in that chat (e.g. "hello").
  3. Run:  python get_chat_id.py

You can also pass the token directly:
  python get_chat_id.py --token YOUR_BOT_TOKEN
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


def fetch_updates(token: str, offset: int | None = None) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    if offset is not None:
        url += f"?offset={offset}"
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not payload.get("ok"):
        raise RuntimeError(payload)
    return payload["result"]


def chat_label(chat: dict) -> str:
    chat_type = chat.get("type", "unknown")
    if chat_type == "private":
        name = chat.get("first_name") or chat.get("username") or "unknown"
        return f"DM with {name}"
    if chat_type in ("group", "supergroup"):
        return chat.get("title") or "unnamed group"
    if chat_type == "channel":
        return chat.get("title") or "unnamed channel"
    return chat.get("title") or chat_type


def print_chats(updates: list[dict]) -> bool:
    seen: set[int] = set()
    found = False
    for update in updates:
        message = update.get("message") or update.get("channel_post")
        if not message:
            continue
        chat = message["chat"]
        chat_id = chat["id"]
        if chat_id in seen:
            continue
        seen.add(chat_id)
        found = True
        print(f"  Chat ID: {chat_id}")
        print(f"  Name:    {chat_label(chat)}")
        print(f"  Type:    {chat.get('type')}")
        print()

    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Find Telegram chat IDs for your bot")
    parser.add_argument("--token", help="Bot token (or set TELEGRAM_BOT_TOKEN in .env)")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll for up to 60 seconds waiting for a new message",
    )
    args = parser.parse_args()

    load_dotenv()
    token = (args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    if not token or token == "your_bot_token_from_botfather":
        print("Error: set TELEGRAM_BOT_TOKEN in .env or pass --token", file=sys.stderr)
        sys.exit(1)

    print("Looking up recent chats from bot updates...\n")

    updates = fetch_updates(token)
    if print_chats(updates):
        return

    print("No messages found yet.\n")
    print("Do this first:")
    print("  1. Add the bot to your group (or send it a DM).")
    print("  2. Send any message in that chat.")
    print("  3. Run this script again.\n")

    if args.wait:
        print("Waiting up to 60s — send a message in the group now...\n")
        deadline = time.time() + 60
        offset = None
        while time.time() < deadline:
            batch = fetch_updates(token, offset=offset)
            if batch and print_chats(batch):
                return
            if batch:
                offset = batch[-1]["update_id"] + 1
            time.sleep(2)
        print("Timed out. Send a message in the group and run again.")


if __name__ == "__main__":
    main()
