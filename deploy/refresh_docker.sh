#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

echo "[yagoda] Updating repository"
git fetch origin --prune

git pull --ff-only

echo "[yagoda] Rebuilding and restarting containers"
docker compose up -d --build

echo "[yagoda] Verifying health endpoint"
curl -fsS http://localhost:8000/health >/dev/null

if ! curl -fsS http://localhost:8000/ >/dev/null; then
  echo "[yagoda] Warning: / did not return 200" >&2
  exit 1
fi

printf "[yagoda] OK\n"
