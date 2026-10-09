#!/usr/bin/env bash
# Generate the systemd units from the .in templates with the REAL
# user/home/install paths (no hardcoded username or location), install
# them, and (re)start both services.
#
#   bash systemd/install.sh      # run as a normal user; uses sudo itself
set -euo pipefail

if [ "$(id -u)" = 0 ]; then
    echo "Run without sudo: $0 (it escalates only for the files it writes)." >&2
    exit 1
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

INSTALL_USER="$(id -un)"
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
INSTALL_DIR="$(pwd)"

# Domain + question bias for Whisper (keep in sync with start_whisper_server.sh)
PROMPT="STEM and cybersecurity questions for kids. Topics: passwords, phishing, scams, black holes, sky, rockets, electricity, atoms, viruses, hacking. The user asks questions: What is a virus? What is malware? "

if [ ! -x "$INSTALL_DIR/venv/bin/python" ]; then
    echo "✗ venv missing: $INSTALL_DIR/venv — run setup.sh first" >&2
    exit 1
fi

for name in whisper-server stem-buddy; do
    sed -e "s|__USER__|$INSTALL_USER|g" \
        -e "s|__HOME__|$INSTALL_HOME|g" \
        -e "s|__DIR__|$INSTALL_DIR|g" \
        -e "s|__PROMPT__|$PROMPT|g" \
        "systemd/$name.service.in" \
        | sudo tee "/etc/systemd/system/$name.service" >/dev/null
    echo "✓ /etc/systemd/system/$name.service"
done

sudo systemctl daemon-reload
sudo systemctl enable whisper-server stem-buddy
sudo systemctl restart whisper-server stem-buddy
echo "✓ installed for user '$INSTALL_USER' at $INSTALL_DIR; services restarted"