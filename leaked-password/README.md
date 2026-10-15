# Leaked Password Checker

**100% offline** password security analyzer with web interface.

## Features

- **Web interface**: Clean, modern UI for password analysis
- **Strength analysis**: Pattern detection, common passwords, dictionary words
- **Entropy calculation**: Bits of entropy, estimated crack time
- **HIBP breach check**: Online check against Have I Been Pwned (privacy-preserving k-anonymity), or fully offline against a local copy of the HIBP database (see below)
- **Privacy**: No passwords sent anywhere - all analysis is local (except optional HIBP check)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web server (port 5000, override with PORT=...)
python3 app.py

# Open http://localhost:5000 in your browser
```

Or use the deploy script, which sets up a venv and starts the app for you:

```bash
./deploy.sh                # → http://localhost:5000
PORT=5001 ./deploy.sh      # → http://localhost:5001 (macOS: AirPlay uses 5000)
./deploy.sh --stop         # stop it again
```

## Deployment

`deploy.sh` deploys locally (default) or to the RPi (10.30.4.181):

```bash
./deploy.sh                        # this machine: venv + dependencies
./deploy.sh --remote               # RPi: sync code, venv, systemd service
./deploy.sh --remote --kiosk       # RPi: + browser kiosk (X + fluxbox + surf)
./deploy.sh --remote --scale 0.5   # RPi: kiosk page zoom (0.5 = half, 2 = double)
./deploy.sh --help                 # full usage
```

- **Local**: works on macOS, Linux, and Windows (Git Bash/WSL). Starts the
  app in the background (PID in `.lp.pid`, log in `.lp.log`);
  `./deploy.sh --stop` stops it. On macOS, AirPlay Receiver usually
  occupies port 5000, so use `PORT=5001 ./deploy.sh`.
- **RPi web app**: installs `leaked-password.service` (enabled, port 5000).
- **RPi kiosk**: installs the browser stack and `xorg` + `rpi-kiosk` services;
  the site opens fullscreen on the HDMI display now and at every boot.
  `--scale N` sets the page zoom (`surf -z N`); it implies `--kiosk`.
- **`--hibp`**: starts a one-time ~35 GB download of the full HIBP Pwned
  Passwords corpus on the Pi (background, resumable, ~30-90 min).

## Local HIBP Database (Offline Breach Checking)

`hibp_db.py` downloads the complete Have I Been Pwned Pwned Passwords corpus
(1,048,576 range requests from the official API, ~35 GB) into `./hibp/`:

```bash
python3 hibp_db.py download          # one-time, resumable, prints progress
python3 hibp_db.py status            # groups completed + size
python3 hibp_db.py check "password"  # offline lookup
```

Once a prefix group exists, breach checks run **fully offline** (the web UI
and CLI use the local database automatically and fall back to the online
k-anonymity API for groups not yet downloaded). No password or full hash
ever leaves the machine. Standard library only; ~35 GB disk; each check reads one ~140 MB group file
once, caches it, and binary-searches (milliseconds).

## CLI Usage

```bash
# Basic offline analysis
python3 check_password.py "MyP@ssw0rd123"

# With online HIBP breach check
python3 check_password.py --check "MyP@ssw0rd123"
```

## Output Example

```
==================================================
  PASSWORD SECURITY ANALYSIS
==================================================

Length:           18 characters
Entropy:          118.0 bits
Estimated crack:  1041105540908839808 years

⚠ PATTERNS FOUND:
  • Contains weak word: 'pass'

==================================================
  STRENGTH: 🟡 MODERATE
==================================================

Recommendations:
  • Remove predictable patterns
  • Use a passphrase (4+ random words)
```

## How It Works

### Entropy Calculation
- Calculates password entropy based on character pool size (lowercase, uppercase, digits, symbols)
- Higher entropy = harder to crack

### Pattern Detection
- Common words (password, admin, welcome, etc.)
- Keyboard patterns (qwerty, 1234, etc.)
- Repeated characters
- Case-only passwords

### Common Password Check
- Checks against top 100 most common breached passwords

### HIBP Breach Check (Optional)
- Uses k-anonymity: only sends first 5 chars of SHA1 hash
- Never sends the actual password
- Returns breach count if found

## Security

- **Offline by default**: All analysis runs locally
- **HIBP k-anonymity**: Only SHA1 hash prefix is sent (5 chars)
- **No storage**: Passwords are never stored or logged
- **No telemetry**: Nothing is sent anywhere

## Requirements

### CLI Mode
- Python 3.8+
- No external dependencies (uses only standard library)

### Web Interface
- Python 3.8+
- Flask 2.0+

```bash
pip install -r requirements.txt
```