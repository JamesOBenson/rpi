#!/bin/bash
# Deploy leaked-password.
#   Local (default):  ./deploy.sh
#   Remote to RPi:    ./deploy.sh --remote [--kiosk] [--scale N] [--hibp] [sudo password]
set -e
cd "$(dirname "$0")"

RPi_HOST="rpi@10.30.4.181"
RPi_PATH="/home/rpi/rpi"
RPi_DIR="leaked-password"
SUDO_PASS="rpi"
REMOTE=0
KIOSK=0
SCALE=1
HIBP=0
STOP=0

usage() {
    cat <<'EOF'
Usage:
  ./deploy.sh
  ./deploy.sh --stop
  ./deploy.sh --remote [--kiosk] [--scale N] [--hibp] [sudo password]

Local deploy (macOS, Linux, Windows via Git Bash/WSL):
  1. Creates/refreshes ./venv
  2. Installs dependencies (Flask, requests)
  3. Starts the app in the background (PID in .lp.pid, log in .lp.log)

  PORT=5001 ./deploy.sh   → serves at http://localhost:5001
  ./deploy.sh --stop      → stops the locally running app

Remote deploy (RPi at 10.30.4.181):
  1. rsyncs code to /home/rpi/rpi/leaked-password, sets up the venv
  2. Installs + enables the leaked-password systemd service (port 5000)
  3. --kiosk    Also installs the browser kiosk (X + fluxbox + surf) that
                opens the site fullscreen now and at every boot
  4. --scale N  Kiosk page zoom (surf -z): 0.5 = half, 1 = native,
                2 = double. Implies --kiosk.

Options:
  --stop      Stop the locally running app (kills .lp.pid).
  -h, --help  Show this help.

Examples:
  ./deploy.sh                      # this machine only
  ./deploy.sh --remote             # Pi: web app
  ./deploy.sh --remote --kiosk     # Pi: web app + kiosk
  ./deploy.sh --remote --scale 0.5 # Pi: kiosk at half size (4K panel)
  ./deploy.sh --remote --hibp      # Pi: start local HIBP database download
                                   # (~35 GB, 30-90 min, resumable; breach
                                   # checks then run offline)
  ./deploy.sh --stop               # stop the locally running app

Notes:
  - macOS: AirPlay Receiver usually occupies port 5000 → use PORT=5001
  - Debian/Ubuntu: if venv creation fails, run: sudo apt install python3-venv
  - Stop the local app: ./deploy.sh --stop
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --remote) REMOTE=1; shift ;;
        --kiosk) KIOSK=1; shift ;;
        --scale)
            if [ -z "${2:-}" ]; then
                echo "Error: --scale needs a value (e.g. 0.5, 1, 2)" >&2
                exit 1
            fi
            SCALE="$2"; shift 2 ;;
        --hibp) HIBP=1; shift ;;
        --stop) STOP=1; shift ;;
        *) SUDO_PASS="$1"; shift ;;
    esac
done

# Stop the local app and exit before doing anything else
if [ "$STOP" = "1" ]; then
    if [ -f .lp.pid ] && kill -0 "$(cat .lp.pid)" 2>/dev/null; then
        kill "$(cat .lp.pid)"
        echo "Stopped the local app."
    else
        echo "No local app running."
    fi
    rm -f .lp.pid
    exit 0
fi

# A scale factor only makes sense for the kiosk
[ "$SCALE" != "1" ] && KIOSK=1
# The HIBP database lives on the remote box
[ "$HIBP" = "1" ] && REMOTE=1

local_deploy() {
    PY=$(command -v python3 || command -v python)
    echo "Creating venv with $PY ..."
    "$PY" -m venv venv
    # Windows venvs use venv\Scripts, Unix venvs use venv/bin
    if [ -x venv/Scripts/python.exe ]; then
        PYTHON=venv/Scripts/python.exe
    elif [ -x venv/Scripts/python ]; then
        PYTHON=venv/Scripts/python
    else
        PYTHON=venv/bin/python
    fi
    echo "Installing dependencies ..."
    "$PYTHON" -m pip install -q -r requirements.txt

    # Start the app (inherits PORT from the environment, default 5000)
    PORT="${PORT:-5000}"
    PID_FILE=.lp.pid
    LOG_FILE=.lp.log
    if curl -sf -o /dev/null "http://localhost:$PORT/"; then
        echo "Already serving at http://localhost:$PORT"
        return
    fi
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        sleep 1
    fi
    nohup "$PYTHON" app.py </dev/null >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Running at http://localhost:$PORT"
        echo "Stop it with: kill \$(cat $PID_FILE)   (log: $LOG_FILE)"
    else
        echo "Failed to start — last lines of $LOG_FILE:"
        tail -3 "$LOG_FILE" 2>/dev/null
        exit 1
    fi
}

# Bake the scale factor into the kiosk startup line (surf -z = page zoom)
if [ "$REMOTE" = "1" ] && [ "$SCALE" != "1" ]; then
    cat > fluxbox-startup <<EOF
#!/bin/sh
# Kiosk startup: open the password checker fullscreen (zoom $SCALE), then run fluxbox
surf -f -z $SCALE http://localhost:5000 &
exec fluxbox
EOF
fi

if [ "$REMOTE" = "1" ]; then
    echo "Syncing code to $RPi_HOST:$RPi_PATH/$RPi_DIR ..."
    ssh "$RPi_HOST" "mkdir -p $RPi_PATH/$RPi_DIR"
    rsync -az --delete --exclude venv --exclude __pycache__ --exclude .git --exclude hibp --exclude .lp.pid --exclude .lp.log \
        ./ "$RPi_HOST:$RPi_PATH/$RPi_DIR/"

    echo "Setting up Python venv ..."
    ssh "$RPi_HOST" "python3 -m venv $RPi_PATH/$RPi_DIR/venv && $RPi_PATH/$RPi_DIR/venv/bin/pip install -q -r $RPi_PATH/$RPi_DIR/requirements.txt"

    echo "Installing systemd service ..."
    ssh "$RPi_HOST" "
        echo '$SUDO_PASS' | sudo -S cp $RPi_PATH/$RPi_DIR/leaked-password.service /etc/systemd/system/leaked-password.service &&
        echo '$SUDO_PASS' | sudo -S systemctl daemon-reload &&
        echo '$SUDO_PASS' | sudo -S systemctl enable --now leaked-password.service
    "

    if [ "$KIOSK" = "1" ]; then
        echo "Installing kiosk (X + fluxbox + surf) ..."
        ssh "$RPi_HOST" "echo '$SUDO_PASS' | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get install -y xserver-xorg xserver-xorg-video-modesetting xserver-xorg-input-evdev x11-apps xinit x11-utils fluxbox surf fonts-dejavu-core fonts-noto-color-emoji 2>&1 | tail -1"
        ssh "$RPi_HOST" "
            bash $RPi_PATH/$RPi_DIR/xauth-setup.sh >/dev/null &&
            mkdir -p /home/rpi/.fluxbox &&
            cp $RPi_PATH/$RPi_DIR/fluxbox-startup /home/rpi/.fluxbox/startup &&
            echo '$SUDO_PASS' | sudo -S cp $RPi_PATH/$RPi_DIR/xorg.conf /etc/X11/xorg.conf &&
            echo '$SUDO_PASS' | sudo -S cp $RPi_PATH/$RPi_DIR/xorg.service /etc/systemd/system/xorg.service &&
            echo '$SUDO_PASS' | sudo -S cp $RPi_PATH/$RPi_DIR/rpi-kiosk.service /etc/systemd/system/rpi-kiosk.service &&
            echo '$SUDO_PASS' | sudo -S systemctl daemon-reload &&
            echo '$SUDO_PASS' | sudo -S systemctl disable getty@tty1 &&
            echo '$SUDO_PASS' | sudo -S systemctl enable --now xorg.service rpi-kiosk.service &&
            sleep 2 &&
            echo '$SUDO_PASS' | sudo -S systemctl restart rpi-kiosk.service
        "
        if [ "$SCALE" != "1" ]; then
            echo "Kiosk installed — page zoom $SCALE."
        else
            echo "Kiosk installed — auto-opens the site fullscreen at boot (HDMI display)."
        fi
    fi

    if [ "$HIBP" = "1" ]; then
        echo "Starting HIBP local database download on the Pi (background, ~35 GB, ~30-90 min) ..."
        ssh "$RPi_HOST" "cd $RPi_PATH/$RPi_DIR && nohup $RPi_PATH/$RPi_DIR/venv/bin/python hibp_db.py download </dev/null >> hibp-download.log 2>&1 & sleep 2; tail -1 $RPi_PATH/$RPi_DIR/hibp-download.log"
        echo "Follow progress:  ssh $RPi_HOST 'tail -f $RPi_PATH/$RPi_DIR/hibp-download.log'"
        echo "Check state:      ssh $RPi_HOST '$RPi_PATH/$RPi_DIR/venv/bin/python $RPi_PATH/$RPi_DIR/hibp_db.py status'"
    fi

    echo "Done. Check status:"
    echo "  ssh $RPi_HOST 'systemctl status leaked-password'"
    if [ "$KIOSK" = "1" ]; then
        echo "  ssh $RPi_HOST 'systemctl status xorg rpi-kiosk'"
    fi
else
    local_deploy
fi