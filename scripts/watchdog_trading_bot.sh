#!/bin/bash
# Watchdog: checks trading-bot.service and notifies Telegram on status changes.

set -euo pipefail

PROJECT_DIR="/home/botuser/trading_bot/trading_bot"
ENV_PATH="$PROJECT_DIR/.env"
STATE_DIR="$PROJECT_DIR/state"
STATE_FILE="$STATE_DIR/watchdog_last_state.txt"

mkdir -p "$STATE_DIR"

unit="trading-bot.service"
now_utc="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

active="$(systemctl is-active "$unit" 2>/dev/null || true)"
failed="$(systemctl is-failed "$unit" 2>/dev/null || true)"

state="$active"
if [[ "$failed" == "failed" ]]; then
  state="failed"
fi

prev=""
if [[ -f "$STATE_FILE" ]]; then
  prev="$(cat "$STATE_FILE" 2>/dev/null || true)"
fi

if [[ "$state" == "$prev" ]]; then
  exit 0
fi

echo "$state" > "$STATE_FILE"

host="$(hostname)"
text=""

if [[ "$state" == "active" ]]; then
  text="✅ Trading bot RECOVERED on $host ($unit) at $now_utc"
else
  # inactive / failed / activating / deactivating / unknown
  text="🛑 Trading bot NOT RUNNING on $host ($unit). state=$state at $now_utc"
fi

# Use system python to avoid depending on venv
python3 "$PROJECT_DIR/scripts/telegram_notify.py" --env "$ENV_PATH" --text "$text" >/dev/null 2>&1 || true


