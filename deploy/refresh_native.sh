#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_REF="${DEPLOY_REF:-origin/main}"

cd "$REPO_ROOT"

echo "[yagoda] Updating repository"
git fetch origin --prune

git checkout -f "$DEPLOY_REF"
git reset --hard "$DEPLOY_REF"

echo "[yagoda] Installing dependencies"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

echo "[yagoda] Restarting services"
sudo systemctl daemon-reload
sudo systemctl restart yagoda-backend.service
sudo systemctl restart yagoda-bot-native.service

echo "[yagoda] Verifying health endpoint"
curl -fsS http://localhost:8000/health >/dev/null

HOME_HEADERS="$(mktemp)"
HOME_BODY="$(mktemp)"
cleanup() {
  rm -f "$HOME_HEADERS" "$HOME_BODY"
}
trap cleanup EXIT

curl -fsS -D "$HOME_HEADERS" http://localhost:8000/ -o "$HOME_BODY"
if ! grep -qi '^content-type:.*text/html' "$HOME_HEADERS"; then
  echo "[yagoda] Warning: / did not return HTML" >&2
  exit 1
fi
if grep -Eq '"detail"[[:space:]]*:[[:space:]]*"Not Found"' "$HOME_BODY"; then
  echo "[yagoda] Warning: / responded with Not Found payload" >&2
  exit 1
fi

printf "[yagoda] OK\n"
