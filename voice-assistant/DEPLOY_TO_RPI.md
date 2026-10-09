# Deploy to Raspberry Pi 5

The reference deployment: **Pi 5 (8GB)**, user `rpi`, project at
`~/voice-assistant/`, service unit `stem-buddy.service`.

## From the Mac (day-to-day updates)

The Mac checkout is `~/Documents/GitHub/rpi/voice-assistant`.

```bash
cd ~/Documents/GitHub/rpi/voice-assistant

# Code changes
rsync -az src/ rpi:~/voice-assistant/src/

# Config changes (repo config is the source of truth)
rsync -az config/settings.yaml rpi:~/voice-assistant/config/

# Restart
ssh rpi 'sudo systemctl restart stem-buddy.service'
ssh rpi 'journalctl -u stem-buddy --since "1 min ago" --no-pager | tail'
```

When the service units or the Whisper prompt change (`systemd/` or
`start_whisper_server.sh`):

```bash
ssh rpi 'cd <voice-assistant checkout> && bash systemd/install.sh'
```

## Fresh install (on the Pi)

```bash
cd ~/voice-assistant
python3 -m venv venv
venv/bin/pip install -r requirements.txt
./download_models.sh          # STT + TTS + LLM models (~1-3GB)
sudo usermod -aG gpio rpi     # only if wiring GPIO pins
bash systemd/install.sh       # generates service units with real paths, starts both
```

## Notes

- **Question STT runs in a separate HTTP server** (`whisper-server.service`,
  faster-whisper small.en int8 on port 8765, with the STEM/cybersecurity +
  question bias from `systemd/install.sh`). The in-process `whisper` engine
  remains available via `question_engine: "whisper"`.
- Service units are **generated** from `systemd/*.service.in` by
  `systemd/install.sh` — paths and the Whisper prompt are substituted at
  install time, so no username or install location is hardcoded.
- **Piper** binary: `bin/piper/piper` (v1.2.0); voice model
  `models/en_US-lessac-medium.onnx`.
- **RNNoise** lib: `lib/librnnoise.so` (rebuild with
  `scripts/build_rnnoise.sh` if ever missing).
- If the service won't start, check the venv survived any reorg:
  `ls venv/bin/python lib/librnnoise.so voices models/spk/campplus_en.onnx`.

## Hailo-8L (optional)

```bash
sudo apt install -y hailo-rt   # SDK
```
Then set `stt.question_engine: "hailo"` — see README (Pipeline) and the
HEF/weight paths under `models/hailo-whisper/`.

## Troubleshooting

```bash
arecord -l            # mic present?
aplay -l              # speaker present?
ls -lh models/        # models present?
journalctl -u stem-buddy -n 50
```

GPIO permission denied: `sudo usermod -aG gpio rpi`, log out and back in.