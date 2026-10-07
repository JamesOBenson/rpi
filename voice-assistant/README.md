# 🤖 STEM Buddy

**An offline voice assistant for kids**  
Built for Raspberry Pi 5 (Hailo-8L AI accelerator optional)

> Say "Hey Buddy" and ask anything about science, space, animals, or inventions!

---

## 🎯 What is STEM Buddy?

STEM Buddy is a **completely offline** voice assistant designed to spark curiosity in 4th and 5th graders (ages 9-11). It runs entirely on a Raspberry Pi 5 with 8GB RAM. The Hailo-8L AI accelerator is **optional**: with it, Whisper speech-to-text runs on the chip (~0.8s); without it, the same Whisper model runs on CPU (~1.8s) automatically.

### Key Features

- ✅ **Voice activation** - Say "Hey Buddy" to start
- ✅ **100% offline** - No internet required after setup
- ✅ **Kid-friendly** - Simple, exciting answers
- ✅ **Noise suppression** - RNNoise on the mic kills fan/AC/background noise
- ✅ **Safety interrupt** - Physical button or say "STOP!"
- ✅ **LED feedback** - Visual states (listening, thinking, speaking)
- ✅ **Wikipedia knowledge** - Curated STEM facts
- ✅ **Open source** - MIT license, free to modify

---

## 📦 Hardware Required

| Component | Required | Notes |
|-----------|----------|-------|
| Raspberry Pi 5 (8GB) | ✅ | Main computer |
| Hailo-8L AI HAT | ⚠️ | Optional - accelerates Whisper STT (~0.8s vs ~1.8s CPU); the service falls back to CPU Whisper automatically if it's absent |
| USB Microphone | ✅ | Any decent USB mic works |
| USB Speakers | ✅ | Or 3.5mm audio output |
| Push Button | ⚠️ | For interrupt (can skip) |
| RGB LED | ⚠️ | Visual feedback (can skip) |

### Total Cost: ~$200-300 (excluding Pi; Hailo-8L is optional)

---

## 🚀 Quick Start

### 1. Set Up the Project

```bash
cd ~
mkdir voice-assistant && cd voice-assistant
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Download AI Models

```bash
# One-time system dependency
sudo apt install portaudio19-dev

# Downloads all 3 models (~1GB total): STT + TTS + LLM
./download_models.sh
```

### 5. Run the Assistant

```bash
./run.sh
```

**Plug in your USB microphone and speakers first.** The app tells you if
it can't find them.

---

### ⚡ Performance (measured on Raspberry Pi 5)

| Stage | Time |
|-------|------|
| Model load (startup) | ~8 sec (LLM 3 sec) |
| Wake word + STT (Hailo / CPU) | ~0.8 / ~1.8 sec |
| RAG retrieval | ~0.3 sec |
| LLM answer (Gemma 3n E2B, first sentence) | ~2-2.5 sec |
| **Total: end-of-speech → first audio** | **~2.5-3 sec** |

The STT stage runs Whisper on the **Hailo-8L** (~0.8s) when the chip is
installed; otherwise it uses in-process **faster-whisper** on CPU (~1.8s).
`stt.question_engine` in `config/settings.yaml` selects the backend:
`"hailo"` (chip, transparent CPU fallback), `"whisper"` (in-process
faster-whisper — what the Pi ships with), or `"whisper-http"` (separate
warm server process, see WHISPER_HTTP.md).

The Pi runs **Gemma 3n E2B** (Q4_K_M). Switch models via `llm.model` in
`config/settings.yaml` — the benchmarks below compare the candidates.
Since RAG supplies the facts, the LLM's only job is synthesizing one
sentence, so a small model suffices.

---

### 📊 LLM Benchmark Results

Tested on Raspberry Pi 5 (8GB RAM), 4 CPU threads, Q4_K_M quantization:

| Model | Released | Size | Prefill | Decode | RAM | Status |
|-------|----------|------|---------|--------|-----|--------|
| **Qwen3-0.6B** | Jun 27, 2025 | 0.5GB | **167 t/s** | **24 t/s** | 0.5GB | Fastest raw speed |
| Qwen3-1.7B | Apr 28, 2025 | 1.2GB | 63 t/s | 9 t/s | 1.2GB | Fallback (richer on hard questions) |
| Qwen3.5-2B | Feb 16, 2026 | 1.2GB | 51 t/s | 7.1 t/s | 1.2GB | Good alternative |
| **Gemma-3n-E2B** | Jun 26, 2025 | 2.9GB | 32 t/s | 6.1 t/s | 2.9GB | ✅ Running on the Pi (default) |

*Measured with the service stopped and the Pi near idle temperature; expect
~20% lower decode rates when the board is hot (it throttles at ~80°C).*

**Running on the Pi**: Gemma 3n E2B — ~2.5 s to first sentence, designed
for on-device use. Qwen3-0.6B is faster on raw t/s; switch via `llm.model`
if answers feel slow.

**Failed models** (unsupported architectures or download issues):
- Spark-X2.5-1.7B - `spark2_5` architecture (llama.cpp doesn't support)
- K2-Horizon-1B - `k2-horizon` architecture (llama.cpp doesn't support)
- LFM2.5-8B-A1B, Ling-3.0-tiny - MoE models, download/network issues

To re-benchmark:
```bash
cd ~/voice-assistant
sudo systemctl stop stem-buddy.service
venv/bin/python scripts/bench_model_tps.py models/Qwen3-1.7B-Q4_K_M.gguf
sudo systemctl start stem-buddy.service
```

---

## 🐍 Fresh Pi Install (TL;DR)

Flash **Raspberry Pi OS (64-bit, Lite)** onto a **Pi 5 (8GB)**, enable SSH,
plug in a USB mic + speaker. Then, in order:

```bash
# 1. System packages (audio, venv, build tools for RNNoise)
sudo apt update
sudo apt install -y alsa-utils python3-venv portaudio19-dev build-essential wget

# 2. Code + Python deps (vosk, faster-whisper, piper-tts, openwakeword, ...)
cd ~
git clone https://github.com/JamesOBenson/rpi.git && cd rpi/voice-assistant
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. Build RNNoise (mic noise suppression, ~1 min)
./scripts/build_rnnoise.sh

# 4. Models: Vosk wake word, Piper voice, Gemma 3n LLM (~1GB total).
#    faster-whisper small.en auto-downloads on first run (~500MB).
./download_models.sh
```

5. **Config** — `config/settings.yaml` works out of the box for most USB
   mics (auto-detects the default device). Change only if it picks the wrong
   one, or to switch the LLM (`llm.model`):

```bash
arecord -l                     # check your mic is the default device
```

6. **Service** — write `/etc/systemd/system/stem-buddy.service` (adjust
   paths/username if you're not `rpi`):

```ini
[Unit]
Description=STEM Buddy voice assistant
After=network.target sound.target

[Service]
User=rpi
WorkingDirectory=/home/rpi/voice-assistant
Environment=PYTHONPATH=/home/rpi/voice-assistant
ExecStart=/home/rpi/voice-assistant/venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 7. Start + verify (~40 s to full startup)
sudo systemctl daemon-reload
sudo systemctl enable --now stem-buddy.service
journalctl -u stem-buddy -f    # good signs: "✓ Whisper STT ready" then [LISTENING]
```

Wiring the GPIO button/LED? Add your user to the `gpio` group first:
`sudo usermod -aG gpio $USER` (log out/in). Full details:
[DEPLOY_TO_RPI.md](DEPLOY_TO_RPI.md).

---

## ⚡ Autostart at Boot

STEM Buddy runs as a **systemd service** so it starts automatically when the
Pi boots - no manual launching needed.

### First-time install (run once on the Pi)

```bash
cd ~/voice-assistant
./buddy.sh install
```

### Manage the service

```bash
./buddy.sh status     # Is it running?
./buddy.sh logs       # Live logs (Ctrl+C to stop)
./buddy.sh logs-tail  # Last 50 log lines
./buddy.sh restart    # Restart (after code changes)
./buddy.sh stop       # Stop
./buddy.sh start      # Start
./buddy.sh disable    # Turn off autostart
./buddy.sh enable     # Turn on autostart
```

### What happens at boot

```
Pi boots → systemd starts stem-buddy.service (after ~3s)
         → loads Vosk endpointer, Hailo/CPU Whisper STT, Piper TTS, Gemma/Qwen3 LLM, knowledge base
         → ~8 seconds later: "Listening... (say 'Buddy' or just ask)"
```

> **Note:** If you plug in USB mic/speakers, reboot or run `./buddy.sh restart`
> so it detects them.

---

## 🎤 How to Use

### Start Listening
Say: **"Hey Buddy!"** (or clap loudly for demo mode)

### Ask Questions
- "How do rockets work?"
- "Why is the sky blue?"
- "Tell me about dinosaurs!"
- "What causes rainbows?"
- "How do bees make honey?"

### Interrupt
- Say: **"STOP!"**
- Or press the physical button

### LED States

| Color | Meaning |
|-------|---------|
| 🔴 Off | Waiting for "Hey Buddy" |
| 🔵 Blue | Listening to your question |
| 🟡 Yellow | Thinking about answer |
| 🟢 Green | Speaking response |
| 🔴 Red | Interrupted |

---

## 📁 Project Structure

```
voice-assistant/
├── src/
│   ├── main.py                # Main orchestrator
│   ├── stt_engine.py          # Wake word (Vosk grammar) + sox question endpoint
│   ├── noise_suppressor.py    # RNNoise mic processing
│   ├── speaker_filter.py      # Same-speaker voice filter (campplus)
│   ├── openwakeword_listener.py # Optional openWakeWord wake detection
│   ├── whisper_engine.py      # In-process faster-whisper STT (question engine)
│   ├── whisper_client.py      # whisper-http STT client (optional mode)
│   ├── whisper_server.py      # whisper-http STT server (optional mode)
│   ├── hailo_whisper_engine.py # Question STT on Hailo-8L (optional)
│   ├── tts_engine.py          # TTS (Piper, in-process)
│   ├── tts_client.py / tts_server.py # TTS http mode (optional)
│   ├── llm_engine.py          # Local LLM (Gemma 3n / Qwen3 via llama.cpp)
│   ├── knowledge_base.py      # RAG with ChromaDB
│   ├── interrupt_handler.py   # Button + voice interrupt
│   └── led_controller.py      # LED feedback (GPIO optional)
├── config/
│   └── settings.yaml          # Configuration (source of truth)
├── models/                    # Downloaded AI models (not in git)
├── data/                      # Knowledge base + debug captures
├── scripts/                   # Benchmarks, model downloads, RNNoise build
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 🔧 Configuration

Edit `config/settings.yaml`:

```yaml
wake_word: "hey buddy"
button_pin: 4      # GPIO pin for interrupt button
led_pin: 17        # GPIO pin for LED
voice_speed: 1.0   # Speech speed (0.5 to 2.0)
```

### Wake word

`wake_word.framework` chooses who detects "buddy":

| framework | How it works | Notes |
|-----------|--------------|-------|
| `vosk` (default) | Grammar-constrained Vosk recognizer: can only output the wake word or nothing | Free, offline, no key. Idle audio is never transcribed. |
| `whisper` | Whisper transcribes every utterance and judges the wake word | Robust but slow (5-36s per sentence on CPU). |
| `porcupine` | Picovoice dedicated keyword spotter | **Free tier ended 2026-06-30** - enterprise AccessKey only (console.picovoice.ai). |
| `openwakeword` | Offline wake-word library, multiple wake words at once | Requires `pip install openwakeword`; built-in models: buddy, hey_jarvis, computer, alexa, more at github.com/dscripka/openWakeWord |

Tuning (`vosk`): `wake_word.wake_confidence` (default 0.3). Raise to 0.5+
if background audio false-triggers; lower to 0.15 if it misses you.

If background audio still causes false wakes, the upgrade path is **openWakeWord**
(offline, MIT, no key): train a custom "buddy" model once (free, ~1-2h:
Synthetic clips via Piper + openWakeWord's training notebook).

### GPIO Wiring

GPIO is entirely optional. With nothing wired (or a Hailo HAT covering the
pins) everything still works: LED feedback falls back to console colors and
the interrupt button to voice ("STOP!", also "cut it" / "enough"). Set
`gpio.enabled: false` in `config/settings.yaml`.

```
┌─────────────┐
│ Raspberry Pi │
│      GPIO 4  │───┬──────┬────── GND (GPIO 6)
│              │   │      │
│            ┌─┴─┐  │
│            │   │  │
│            │   │  │
│            └─┬─┘  │
│              │    │
│           ┌──┴──┐ │
│           │ 1k  │ │
│           │  Ω  │ │
│           └──┬──┘ │
│              │    │
│              └────┴─────── GND
└─────────────┘
```

---

## 🧠 Knowledge Base

STEM Buddy ships with a **1,033-fact knowledge base** covering:

### Cybersecurity (1,023 facts)

| Grade Level | Topics |
|-------------|--------|
| **5th Grade** | Passwords, online safety, phishing, devices, privacy, social media, gaming, email, cyberbullying, videos, apps, shopping, friends |
| **Middle School** | 2FA, networks, malware, VPNs, firewalls, cookies, backups, updates, social engineering, authentication, incident response, mobile security |
| **High School** | Cryptography, network security, vulnerabilities, web security, secure coding, risk management, threat intelligence, pentesting, security tools, ethics, incident response |
| **College** | Zero trust, supply chain, threat hunting, AI security, legal/compliance, forensics, cloud security, DevSecOps, physical security, emerging threats |

### STEM Demo Facts (10 facts)
Space, animals, physics, inventions, nature

**Storage**: 214 KB
**Query time**: <1 second

### How It Works (RAG)

```
Question → Vector Search (ChromaDB) → Top 3 Facts → LLM → Kid-Friendly Answer
```

When the LLM (Gemma 3n E2B on the Pi, or Qwen3-0.6B / Qwen3-1.7B) is installed, it synthesizes the retrieved facts into a
natural answer. Without it, the best matching fact is spoken directly -
still fast and accurate!

### Pipeline

```
Mic → RNNoise → Wake word → Question capture → STT → RAG + LLM → TTS → Speakers
```

1. **Noise suppression** - 48 kHz mic capture, RNNoise suppression (`audio.noise_suppression`)
2. **Wake word** - Always-on. Vosk small model, grammar-constrained to "Buddy" (conf ≥ 0.3); plays a short chime when it lands
3. **Question capture** - sox silence endpoint: starts when you speak, stops 0.7 s after you stop. The threshold (4%) is in `src/stt_engine.py` — retune it for a new room
4. **STT** - Transcribes the question. In-process **faster-whisper** `small.en` int8 (the Pi default; `stt.whisper_model`), Hailo-8L Whisper when the chip is installed, or a separate HTTP server (WHISPER_HTTP.md)
5. **RAG** - Retrieves relevant facts (ChromaDB vector search)
6. **LLM** - Generates kid-friendly answer (streamed; Gemma 3n E2B on the Pi — or Qwen3 via `llm.model`)
7. **TTS** - Converts answer to speech (Piper, streamed sentence by sentence)

---

## 🎓 Educational Value

This project teaches students about:

- **AI & Machine Learning** - How computers understand speech
- **Natural Language Processing** - Converting speech to text
- **Knowledge Retrieval** - Finding information from databases
- **Audio Processing** - Capturing and playing sound
- **Hardware Integration** - Connecting sensors and LEDs

---

## 🐛 Troubleshooting

### "No audio input"
```bash
# Check microphone
arecord -l

# Test with Python
python3 -c "import sounddevice as sd; sd.play(sd.rec(1, 16000))"
```

### "GPIO permission denied"
```bash
sudo usermod -a -G gpio $USER
# Log out and back in
```

### "Model not found"
Download models manually from URLs in setup instructions.

### "Slow responses"
- Use smaller Vosk model (`vosk-model-small-en-us-0.15`) - already the default
- Reduce LLM context window in config
- Use `stt.question_engine: "hailo"` - Whisper on the Hailo-8L chip; `"whisper"` (in-process faster-whisper) is the CPU path the Pi ships with
- If it stops hearing you after a move, retune the sox question-capture threshold in `src/stt_engine.py` (4% on the current Pi)

### "It hears the wrong words"
With `stt.debug_audio: true`, every question capture is saved to
`data/debug/` — listen to what the mic actually got before tuning
anything (play the last `q-*.wav`). On the Pi, faster-whisper
`small.en` transcribed real captures perfectly where the old
whisper.cpp HTTP server returned garbage — suspect the engine before
the microphone.

---

## 🙏 Credits

Parts of this project were inspired by the creators of
[whisplay-ai-chatbot](https://github.com/PiSugar/whisplay-ai-chatbot) —
notably the separate HTTP server architecture for Whisper/TTS, the sox
silence-based question endpointing, the faster-whisper `small.en`
tuning, and the wake-word chime (their sox synth, used verbatim).

## 📄 License

MIT License - Free to use, modify, and distribute.

## 🤝 Contributing

This is a demo project for educational purposes. Feel free to:
- Add more knowledge topics
- Improve wake word detection
- Add new voices
- Create educational activities

---

## 📞 Support

For questions or issues, check:
- [Vosk documentation](https://github.com/alphacep/vosk-api)
- [Piper TTS](https://github.com/rhasspy/piper)
- [ChromaDB](https://docs.trychroma.com/)

---

**Built with ❤️ for curious kids everywhere** 🚀