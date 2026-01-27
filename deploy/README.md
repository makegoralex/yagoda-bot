# Server install (systemd)
This installs systemd units that run the backend and Telegram bot natively.

```bash
cd /home/yagoda_staff/yagoda-bot
chmod +x deploy/install_native_systemd.sh
./deploy/install_native_systemd.sh
```

Если у вас всё ещё используется `deploy/install_systemd.sh`, он теперь просто
переадресует на нативный установщик.

This creates two services:
- `yagoda-backend.service` (uvicorn)
- `yagoda-bot-native.service` (telegram bot)

## GitHub Actions autodeploy
This repo includes a GitHub Actions workflow that deploys on every push to `main` and
on every pull request update (demo deployment).

Required repository secrets:
- `SERVER_IP` — server IP address
- `SERVER_USER` — SSH username
- `SSH_PRIVATE_KEY` — private key with access to the server

The workflow runs `./deploy/refresh_native.sh` on the server after updating the
working tree to install dependencies and restart services.

### One-time setup for user services
User services require lingering to keep running after logout:
```bash
chmod +x deploy/enable_linger.sh
./deploy/enable_linger.sh
```
