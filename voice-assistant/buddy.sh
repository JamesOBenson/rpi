#!/usr/bin/env bash
# STEM Buddy service manager
# Usage: ./buddy.sh {start|stop|restart|status|logs|enable|disable}

set -e
SERVICE="stem-buddy.service"

cmd="${1:-status}"

need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        sudo "$@"
    else
        "$@"
    fi
}

case "$cmd" in
    start)
        need_root systemctl start "$SERVICE"
        echo "▶ STEM Buddy started. Watch logs with: ./buddy.sh logs"
        ;;
    stop)
        need_root systemctl stop "$SERVICE"
        echo "■ STEM Buddy stopped."
        ;;
    restart)
        need_root systemctl restart "$SERVICE"
        echo "↻ STEM Buddy restarted."
        ;;
    status)
        systemctl status "$SERVICE" --no-pager -l | head -20
        ;;
    logs)
        echo "=== Live logs (Ctrl+C to stop) ==="
        journalctl -u "$SERVICE" -f
        ;;
    logs-tail)
        journalctl -u "$SERVICE" --no-pager -n 50
        ;;
    enable)
        need_root systemctl enable "$SERVICE"
        echo "✓ STEM Buddy will start automatically at boot."
        ;;
    disable)
        need_root systemctl disable "$SERVICE"
        echo "✗ STEM Buddy will NOT start at boot (still running until stopped)."
        ;;
    install)
        # Copy the service file and enable (run once on a new Pi)
        if [ ! -f "/etc/systemd/system/$SERVICE" ]; then
            echo "Installing $SERVICE..."
            need_root tee "/etc/systemd/system/$SERVICE" > /dev/null << 'EOF'
[Unit]
Description=STEM Buddy - Offline Voice Assistant
After=network.target sound.target
Wants=sound.target

[Service]
Type=simple
User=rpi
Group=rpi
WorkingDirectory=/home/rpi/voice-assistant
Environment=PATH=/home/rpi/voice-assistant/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=HOME=/home/rpi
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/rpi/voice-assistant/venv/bin/python /home/rpi/voice-assistant/src/main.py
Restart=on-failure
RestartSec=5
ExecStartPre=/bin/sleep 3

[Install]
WantedBy=multi-user.target
EOF
        fi
        need_root systemctl daemon-reload
        need_root systemctl enable "$SERVICE"
        need_root systemctl start "$SERVICE"
        echo "✓ STEM Buddy installed, enabled at boot, and started."
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|logs-tail|enable|disable|install}"
        exit 1
        ;;
esac