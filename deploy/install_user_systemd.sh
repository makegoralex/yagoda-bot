#!/usr/bin/env bash
set -euo pipefail

if [ ! -f requirements.txt ]; then
  echo "Run this script from the repo root (requirements.txt not found)." >&2
  exit 1
fi

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

mkdir -p ~/.config/systemd/user
cp deploy/yagoda-backend.user.service ~/.config/systemd/user/yagoda-backend.service
cp deploy/yagoda-bot.user.service ~/.config/systemd/user/yagoda-bot.service

systemctl --user daemon-reload
systemctl --user enable --now yagoda-backend.service
systemctl --user enable --now yagoda-bot.service

systemctl --user status yagoda-backend.service --no-pager
systemctl --user status yagoda-bot.service --no-pager
