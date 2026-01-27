#!/usr/bin/env bash
set -euo pipefail

SERVICE_PATH=/etc/systemd/system/yagoda-bot.service

if [ ! -f docker-compose.yml ]; then
  echo "Run this script from the repo root (docker-compose.yml not found)." >&2
  exit 1
fi

chmod +x deploy/refresh_docker.sh

sudo cp deploy/yagoda-bot.service "$SERVICE_PATH"
sudo systemctl daemon-reload
sudo systemctl enable yagoda-bot.service
sudo systemctl restart yagoda-bot.service

sudo systemctl status yagoda-bot.service --no-pager
