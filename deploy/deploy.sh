#!/usr/bin/env bash
set -euo pipefail

# Deploy voice-budget-bot from this repository to the native systemd service.
# Usage: deploy/deploy.sh   (set SSH_HOST / SSH_KEY env to override)
# Target: root@<host>:/opt/voice-budget-bot  -> systemd unit voice-budget-bot.service

HOST="${SSH_HOST:-ya.ramadoit.ru}"
KEY="${SSH_KEY:-/home/dikusar/projects/bot-memory/access/id_ed25519_voice_memory_agent}"
DST="/opt/voice-budget-bot"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSH=(ssh -i "$KEY" -o ConnectTimeout=15 "root@$HOST")
RSYNC=(rsync -az --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache')

cd "$REPO_DIR"

"${RSYNC[@]}" -e "ssh -i $KEY" \
  bot.py config.py schemas.py welcome.py categories.py database.py \
  "root@$HOST:$DST/"
"${RSYNC[@]}" -e "ssh -i $KEY" services/ "root@$HOST:$DST/services/"
"${RSYNC[@]}" -e "ssh -i $KEY" handlers/ "root@$HOST:$DST/handlers/"

# Reinstall deps only when requirements.txt changed.
LOCAL_SHA="$(sha256sum requirements.txt | cut -d' ' -f1)"
CURRENT_SHA="$("${SSH[@]}" "cat $DST/.deploy.requirements.sha 2>/dev/null || true")"
if [ "$LOCAL_SHA" != "$CURRENT_SHA" ]; then
  echo "requirements changed, installing"
  "${SSH[@]}" "$DST/.venv/bin/pip install -q -r $DST/requirements.txt"
  "${SSH[@]}" "echo $LOCAL_SHA > $DST/.deploy.requirements.sha"
fi

"${SSH[@]}" "systemctl restart voice-budget-bot && systemctl is-active voice-budget-bot"
echo "deployed voice-budget-bot"
