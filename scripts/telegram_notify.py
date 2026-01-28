#!/usr/bin/env python3
"""
Send a Telegram message using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from a .env file.
Usage:
  python3 scripts/telegram_notify.py --env /path/to/.env --text "message"
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request


def read_env_kv(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and k not in out:
                    out[k] = v
    except FileNotFoundError:
        return out
    return out


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="Path to .env")
    ap.add_argument("--text", required=True, help="Message text")
    args = ap.parse_args()

    env = read_env_kv(args.env)
    token = env.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID", file=sys.stderr)
        return 2

    try:
        send_message(token, chat_id, args.text)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""
Send a Telegram message using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from a .env file.
Usage:
  python3 scripts/telegram_notify.py --env /path/to/.env --text "message"
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request


def read_env_kv(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and k not in out:
                    out[k] = v
    except FileNotFoundError:
        return out
    return out


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="Path to .env")
    ap.add_argument("--text", required=True, help="Message text")
    args = ap.parse_args()

    env = read_env_kv(args.env)
    token = env.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID", file=sys.stderr)
        return 2

    try:
        send_message(token, chat_id, args.text)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""
Send a Telegram message using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from a .env file.
Usage:
  python3 scripts/telegram_notify.py --env /path/to/.env --text "message"
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request


def read_env_kv(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k and k not in out:
                    out[k] = v
    except FileNotFoundError:
        return out
    return out


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="Path to .env")
    ap.add_argument("--text", required=True, help="Message text")
    args = ap.parse_args()

    env = read_env_kv(args.env)
    token = env.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID", file=sys.stderr)
        return 2

    try:
        send_message(token, chat_id, args.text)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




