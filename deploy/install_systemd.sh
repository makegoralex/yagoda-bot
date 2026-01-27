#!/usr/bin/env bash
set -euo pipefail

if [ ! -f requirements.txt ]; then
  echo "Run this script from the repo root (requirements.txt not found)." >&2
  exit 1
fi

echo "[yagoda] install_systemd.sh is deprecated; using native systemd installer."
chmod +x deploy/refresh_native.sh
chmod +x deploy/install_native_systemd.sh
./deploy/install_native_systemd.sh
