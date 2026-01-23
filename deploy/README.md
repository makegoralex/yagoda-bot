# Server install (systemd)

This installs a systemd unit that starts Docker Compose on boot and restarts it on deploy.

```bash
cd /home/yagoda_staff/yagoda-bot
chmod +x deploy/install_systemd.sh
./deploy/install_systemd.sh
```

Make sure `.env` exists with `TELEGRAM_BOT_TOKEN` before running the script.
