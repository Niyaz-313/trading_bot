#!/bin/bash
# Install watchdog systemd units (service+timer) on the server.

set -euo pipefail

SRC_DIR="/home/botuser/trading_bot/trading_bot/systemd"
DST_DIR="/etc/systemd/system"

echo "Installing watchdog units..."
sudo cp "$SRC_DIR/trading-bot-watchdog.service" "$DST_DIR/trading-bot-watchdog.service"
sudo cp "$SRC_DIR/trading-bot-watchdog.timer" "$DST_DIR/trading-bot-watchdog.timer"

sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot-watchdog.timer

echo "Done."
echo "Check:"
echo "  systemctl status trading-bot-watchdog.timer --no-pager -l"
echo "  journalctl -u trading-bot-watchdog.service -n 50 --no-pager"


# Install watchdog systemd units (service+timer) on the server.

set -euo pipefail

SRC_DIR="/home/botuser/trading_bot/trading_bot/systemd"
DST_DIR="/etc/systemd/system"

echo "Installing watchdog units..."
sudo cp "$SRC_DIR/trading-bot-watchdog.service" "$DST_DIR/trading-bot-watchdog.service"
sudo cp "$SRC_DIR/trading-bot-watchdog.timer" "$DST_DIR/trading-bot-watchdog.timer"

sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot-watchdog.timer

echo "Done."
echo "Check:"
echo "  systemctl status trading-bot-watchdog.timer --no-pager -l"
echo "  journalctl -u trading-bot-watchdog.service -n 50 --no-pager"


# Install watchdog systemd units (service+timer) on the server.

set -euo pipefail

SRC_DIR="/home/botuser/trading_bot/trading_bot/systemd"
DST_DIR="/etc/systemd/system"

echo "Installing watchdog units..."
sudo cp "$SRC_DIR/trading-bot-watchdog.service" "$DST_DIR/trading-bot-watchdog.service"
sudo cp "$SRC_DIR/trading-bot-watchdog.timer" "$DST_DIR/trading-bot-watchdog.timer"

sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot-watchdog.timer

echo "Done."
echo "Check:"
echo "  systemctl status trading-bot-watchdog.timer --no-pager -l"
echo "  journalctl -u trading-bot-watchdog.service -n 50 --no-pager"




