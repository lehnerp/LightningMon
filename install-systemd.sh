#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="lightning-dashboard.service"

if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    RUN_USER="$SUDO_USER"
else
    RUN_USER="$(id -un)"
fi

if [[ "$RUN_USER" == "root" && "$(id -u)" -ne 0 ]]; then
    RUN_USER="$(id -un)"
fi

SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

cat > "$TMP_FILE" <<EOF
[Unit]
Description=LightningMaps Zabbix + Web Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
ExecStart=$SCRIPT_DIR/run.sh
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

if [[ "$(id -u)" -eq 0 ]]; then
    install -m 0644 "$TMP_FILE" "$SERVICE_FILE"
    systemctl daemon-reload
else
    sudo install -m 0644 "$TMP_FILE" "$SERVICE_FILE"
    sudo systemctl daemon-reload
fi

echo "Installed $SERVICE_FILE"
echo "Run user: $RUN_USER"
echo "Project directory: $SCRIPT_DIR"
echo
echo "Enable/start with:"
echo "  sudo systemctl enable --now $SERVICE_NAME"
echo "Logs:"
echo "  journalctl -u $SERVICE_NAME -f"
