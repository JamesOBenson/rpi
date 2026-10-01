# 🤖 STEM Buddy

**An offline voice assistant for kids**  
Built for Raspberry Pi 5 with Hailo-9L AI accelerator

> Say "Hey Buddy" and ask anything about science, space, animals, or inventions!

---

## 🎯 What is STEM Buddy?

STEM Buddy is a **completely offline** voice assistant designed to spark curiosity in 4th and 5th graders (ages 9-11). It runs entirely on a Raspberry Pi 5 with 8GB RAM and Hailo-9L AI accelerator.

### Key Features

- ✅ **Voice activation** - Say "Hey Buddy" to start
- ✅ **100% offline** - No internet required after setup
- ✅ **Kid-friendly** - Simple, exciting answers
- ✅ **Safety interrupt** - Physical button or say "STOP!"
- ✅ **LED feedback** - Visual states (listening, thinking, speaking)
- ✅ **Wikipedia knowledge** - Curated STEM facts
- ✅ **Open source** - MIT license, free to modify

---

## 📦 Hardware Required

| Component | Required | Notes |
|-----------|----------|-------|
| Raspberry Pi 5 (8GB) | ✅ | Main computer |
| Hailo-9L AI Board | ✅ | Accelerates AI inference |
| USB Microphone | ✅ | Any decent USB mic works |
| USB Speakers | ✅ | Or 3.5mm audio output |
| Push Button | ⚠️ | For interrupt (can skip) |
| RGB LED | ⚠️ | Visual feedback (can skip) |

### Total Cost: ~$300-400 (excluding Pi/Hailo)

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
| Model load (startup) | ~9 sec |
| Wake word + STT | ~2-5 sec |
| RAG retrieval | <0.5 sec |
| LLM answer (Qwen2-1.5B) | ~3-7 sec |
| **Total: question → spoken answer** | **~8-12 sec** |

Switch to the slower-but-deeper Phi-3 mini (~30s) via `config/settings.yaml`.

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
         → loads Vosk STT, Piper TTS, Qwen2 LLM, knowledge base
         → ~20 seconds later: "Listening... (say 'Buddy' or just ask)"
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
│   ├── main.py              # Main orchestrator
│   ├── wake_word.py         # Wake word detection
│   ├── stt_engine.py        # Speech-to-text (Vosk)
│   ├── tts_engine.py        # Text-to-speech (Piper)
│   ├── llm_engine.py        # Local LLM (Phi-3)
│   ├── knowledge_base.py    # RAG with ChromaDB
│   ├── audio_listener.py    # Audio capture
│   ├── interrupt_handler.py # Button + voice interrupt
│   └── led_controller.py    # LED feedback
├── config/
│   └── settings.yaml        # Configuration
├── models/                  # Downloaded AI models
├── data/                    # Knowledge base storage
├── logs/                    # Application logs
├── requirements.txt         # Python dependencies
├── setup.sh                # Setup script
└── README.md               # This file
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

### GPIO Wiring

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

When the Phi-3 LLM is installed, it synthesizes the retrieved facts into a
natural answer. Without it, the best matching fact is spoken directly -
still fast and accurate!

### Pipeline

```
Mic → Wake Word → STT → RAG + LLM → TTS → Speakers
       │           │        │            │
  "Hey Buddy"   Vosk   ChromaDB    Piper
                    (1033 facts) (Phi-3)
```

1. **Wake Word** - Detects "Hey Buddy"
2. **STT** - Converts speech to text (Vosk, offline)
3. **RAG** - Retrieves relevant facts (ChromaDB vector search)
4. **LLM** - Generates kid-friendly answer (Phi-3 mini, or fallback)
5. **TTS** - Converts answer to speech (Piper)

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
- Use smaller Vosk model (`vosk-model-small-en-us-0.15`)
- Reduce LLM context window in config
- Enable Hailo acceleration (advanced)

---

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