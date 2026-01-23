#!/usr/bin/env bash
set -euo pipefail

if [ ! -f requirements.txt ]; then
  echo "Run this script from the repo root (requirements.txt not found)." >&2
  exit 1
fi

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

sudo cp deploy/yagoda-backend.service /etc/systemd/system/yagoda-backend.service
sudo cp deploy/yagoda-bot-native.service /etc/systemd/system/yagoda-bot-native.service
sudo systemctl daemon-reload
sudo systemctl enable yagoda-backend.service
sudo systemctl enable yagoda-bot-native.service
sudo systemctl restart yagoda-backend.service
sudo systemctl restart yagoda-bot-native.service

sudo systemctl status yagoda-backend.service --no-pager
sudo systemctl status yagoda-bot-native.service --no-pager
