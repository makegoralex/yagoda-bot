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
