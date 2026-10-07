# Whisper HTTP Server

> **Note (Oct 7):** the Pi now ships `question_engine: "whisper"`
> (in-process faster-whisper) and `whisper-server.service` is stopped.
> This HTTP mode is optional — use it only if you want the model in a
> separate warm process. An A/B on the same capture showed the in-process
> faster-whisper path is the reliable one on this hardware.

Keeps the Whisper model loaded in a separate process, avoiding reload overhead and isolating crashes.

## Why Use This?

**Problem:** Loading Whisper takes ~2-3 seconds. If main.py crashes or restarts, the model reloads.

**Solution:** Run Whisper in a dedicated HTTP server process that:
- Loads the model once at startup
- Stays warm between requests
- Survives main.py crashes
- Allows parallel transcription requests

## Quick Start

### 1. Start the server (in a separate terminal)

```bash
cd voice-assistant
python3 src/whisper_server.py --model small.en --prompt "STEM questions..."
```

Or use the helper script:
```bash
./start_whisper_server.sh
```

### 2. Configure main.py

Edit `config/settings.yaml`:

```yaml
stt:
  question_engine: "whisper-http"  # or "whisper" for direct loading
  whisper_server_url: "http://127.0.0.1:8765"
  whisper_timeout: 30.0
```

### 3. Run the assistant

```bash
./buddy.sh
```

## API

### POST /transcribe

**Request:**
```json
{
  "audio": "<base64-encoded-float32-array>"
}
```

**Response:**
```json
{
  "text": "transcribed text",
  "duration": 2.5
}
```

### GET /health

**Response:**
```json
{
  "status": "ok",
  "model": "small.en"
}
```

## Performance

| Mode | First Request | Subsequent | RAM |
|------|---------------|------------|-----|
| Direct (`whisper`) | ~2.5s | ~1.8s | ~500MB |
| HTTP (`whisper-http`) | ~1.8s | ~1.8s | ~500MB (separate process) |

**Benefits:**
- No cold-start penalty after crashes
- Model stays warm in background
- Crashes isolated to server process
- Can serve multiple clients

## Troubleshooting

**Server won't start:**
```bash
# Check port is free
lsof -i :8765

# Check faster-whisper is installed
pip3 install faster-whisper
```

**Client can't connect:**
```bash
# Test server health
curl http://127.0.0.1:8765/health

# Check server is running
ps aux | grep whisper_server
```

**Timeout errors:**
- Increase `whisper_timeout` in settings.yaml
- Check CPU load (top / htop)
- Reduce `cpu_threads` if system is busy

## Implementation Details

- **Server:** `src/whisper_server.py` - HTTP server with faster-whisper
- **Client:** `src/whisper_client.py` - Drop-in replacement for WhisperSTT
- **Integration:** `src/main.py` - Supports both modes via `question_engine` config

The client is a drop-in replacement - same `transcribe(audio)` API, just sends HTTP requests instead of calling the model directly.