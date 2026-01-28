#!/bin/bash
# Sync logs and audit files to Git (commit + push).
# Run this on the SERVER inside /home/botuser/trading_bot/trading_bot

set -euo pipefail

cd /home/botuser/trading_bot/trading_bot

echo "== sync_logs_to_git.sh =="
echo "time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "pwd:  $(pwd)"

# Ensure we don't accidentally commit secrets
if [ -f ".env" ]; then
  echo "WARN: .env exists (should be ignored). Not adding it."
fi

git status --porcelain >/dev/null 2>&1 || {
  echo "ERROR: Not a git repo here"
  exit 1
}

# Add only log/audit artifacts
git add -A logs audit_logs 2>/dev/null || true

# Commit only if something staged
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git config user.name "Bot Server" >/dev/null 2>&1 || true
git config user.email "bot@server.local" >/dev/null 2>&1 || true

msg="Auto-sync: logs+audit $(date -u '+%Y-%m-%d_%H-%M-%S_UTC')"
git commit -m "$msg"

echo "Pushing to origin/main..."
git push origin main

echo "Done."

# Sync logs and audit files to Git (commit + push).
# Run this on the SERVER inside /home/botuser/trading_bot/trading_bot

set -euo pipefail

cd /home/botuser/trading_bot/trading_bot

echo "== sync_logs_to_git.sh =="
echo "time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "pwd:  $(pwd)"

# Ensure we don't accidentally commit secrets
if [ -f ".env" ]; then
  echo "WARN: .env exists (should be ignored). Not adding it."
fi

git status --porcelain >/dev/null 2>&1 || {
  echo "ERROR: Not a git repo here"
  exit 1
}

# Add only log/audit artifacts
git add -A logs audit_logs 2>/dev/null || true

# Commit only if something staged
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git config user.name "Bot Server" >/dev/null 2>&1 || true
git config user.email "bot@server.local" >/dev/null 2>&1 || true

msg="Auto-sync: logs+audit $(date -u '+%Y-%m-%d_%H-%M-%S_UTC')"
git commit -m "$msg"

echo "Pushing to origin/main..."
git push origin main

echo "Done."

# Sync logs and audit files to Git (commit + push).
# Run this on the SERVER inside /home/botuser/trading_bot/trading_bot

set -euo pipefail

cd /home/botuser/trading_bot/trading_bot

echo "== sync_logs_to_git.sh =="
echo "time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "pwd:  $(pwd)"

# Ensure we don't accidentally commit secrets
if [ -f ".env" ]; then
  echo "WARN: .env exists (should be ignored). Not adding it."
fi

git status --porcelain >/dev/null 2>&1 || {
  echo "ERROR: Not a git repo here"
  exit 1
}

# Add only log/audit artifacts
git add -A logs audit_logs 2>/dev/null || true

# Commit only if something staged
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git config user.name "Bot Server" >/dev/null 2>&1 || true
git config user.email "bot@server.local" >/dev/null 2>&1 || true

msg="Auto-sync: logs+audit $(date -u '+%Y-%m-%d_%H-%M-%S_UTC')"
git commit -m "$msg"

echo "Pushing to origin/main..."
git push origin main

echo "Done."



