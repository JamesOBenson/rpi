# STEM Buddy Startup Guide

## Quick Start

### 1. Install Dependencies

```bash
cd voice-assistant

# Install new dependencies
pip3 install openwakeword faster-whisper requests --break-system-packages

# Or if using venv:
~/.venv/bin/pip install openwakeword faster-whisper requests
```

### 2. Run the Assistant (Auto-starts HTTP servers!)

```bash
# This automatically starts Whisper + TTS HTTP servers if configured
./buddy.sh start

# Or just run directly (manual mode):
./buddy.sh
```

**The HTTP servers auto-start** when you run `./buddy.sh start` if your config has:
- `question_engine: "whisper-http"`
- `tts.mode: "http"`

### 3. Manual Server Start (Optional)

If you want more control, start servers manually:

```bash
# Terminal 1: Whisper server
python3 src/whisper_server.py --model small.en --port 8765 &

# Terminal 2: TTS server  
python3 src/tts_server.py --voice en_US-amy-medium --port 8766 &

# Terminal 3: Main app
./buddy.sh
```

## Wake Word Options

| Framework | Pros | Cons |
|-----------|------|------|
| **openwakeword** | Low CPU (~2-5%), multiple wake words | Requires `pip install openwakeword` |
| **vosk** | Built-in, no extra install | Higher CPU, single wake word |
| **porcupine** | Very accurate | Requires AccessKey (free tier ended) |

### Available OpenWakeWord Models

Built-in models (no download needed):
- `hey_jarvis`
- `buddy`
- `computer`
- `alexa`
- `simon`
- `jarvis`
- `google`
- `hey_siri`

Download more: https://github.com/dscripka/openWakeWord

## Troubleshooting

### OpenWakeWord won't load

```bash
# Install the library
pip3 install openwakeword --break-system-packages

# Test it works
python3 -c "from openwakeword.model import Model; print('OK')"
```

### Whisper server won't start

```bash
# Check port is free
lsof -i :8765

# Check faster-whisper is installed
pip3 list | grep -i whisper

# Try direct mode instead
# Edit config/settings.yaml: question_engine: "whisper"
```

### Wake word not detecting

1. **Adjust threshold** (lower = more sensitive):
   ```yaml
   wake_word:
     threshold: 0.3  # Try 0.3-0.7 range
   ```

2. **Check microphone**:
   ```bash
   arecord -l  # List input devices
   ```

3. **Try Vosk fallback**:
   ```yaml
   wake_word:
     framework: "vosk"
   ```

### Audio quality issues

1. **Enable noise suppression** (default):
   ```yaml
   audio:
     noise_suppression: true
   ```

2. **Check sample rate**:
   ```bash
   # Should be 48000 with noise suppression
   # or 16000 without
   ```

## Performance Tips

| Setting | Recommendation |
|---------|---------------|
| `whisper_threads` | 4 (not 8 - avoids slow A53 cores) |
| `whisper_model` | `small.en` for best accuracy |
| `question_engine` | `whisper-http` for stability |
| `wake_word.threshold` | 0.5 (adjust 0.3-0.7) |

## Architecture

```
┌──────────────────┐
│  OpenWakeWord    │  ← Detects "buddy"
│  (2-5% CPU)      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Capture Audio   │  ← Records question
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     HTTP     ┌──────────────────┐
│  main.py         │ ───────────► │ whisper_server   │
│  (orchestrator)  │              │ (model stays warm)│
└──────────────────┘              └──────────────────┘
```

## Full Config Example

```yaml
wake_word:
  framework: "openwakeword"
  wake_words: "buddy,hey_jarvis"
  threshold: 0.5
  cooldown: 1.5

stt:
  question_engine: "whisper-http"
  whisper_server_url: "http://127.0.0.1:8765"
  whisper_timeout: 30.0
  whisper_model: "small.en"
  whisper_threads: 4

audio:
  noise_suppression: true
```