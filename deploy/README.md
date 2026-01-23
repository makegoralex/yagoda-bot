# Server install (systemd)

This installs a systemd unit that starts Docker Compose on boot and restarts it on deploy.

```bash
cd /home/yagoda_staff/yagoda-bot
chmod +x deploy/install_systemd.sh
./deploy/install_systemd.sh
```

Make sure `.env` exists with `TELEGRAM_BOT_TOKEN` before running the script.

## Native (no Docker)
Use this if Docker is not installed on the server.

```bash
cd /home/yagoda_staff/yagoda-bot
chmod +x deploy/install_native_systemd.sh
./deploy/install_native_systemd.sh
```

This creates two services:
- `yagoda-backend.service` (uvicorn)
- `yagoda-bot-native.service` (telegram bot)

## GitHub Actions autodeploy
This repo includes a GitHub Actions workflow that deploys on every push to `main`.

Required repository secrets:
- `SERVER_IP` — server IP address
- `SERVER_USER` — SSH username
- `SSH_PRIVATE_KEY` — private key with access to the server

The workflow runs `./deploy/install_user_systemd.sh` on the server after `git pull` (no sudo).

### One-time setup for user services
User services require lingering to keep running after logout:
```bash
chmod +x deploy/enable_linger.sh
./deploy/enable_linger.sh
```
