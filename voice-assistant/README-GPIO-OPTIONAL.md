# STEM Buddy - GPIO Optional Mode

## ✅ Works Without GPIO Pins!

If your **Hailo-8L HAT covers the GPIO pins**, the voice assistant **still works perfectly** - it just uses console output instead of LEDs and voice-only interrupt instead of a physical button.

### What Still Works (No GPIO Needed)

| Feature | Status | Notes |
|---------|--------|-------|
| Wake Word Detection | ✅ | "Hey Buddy" still works |
| Speech Recognition | ✅ | Vosk works offline |
| Knowledge Base | ✅ | RAG with Wikipedia |
| LLM Answers | ✅ | Phi-3 generates responses |
| Text-to-Speech | ✅ | Piper speaks answers |
| Voice Interrupt | ✅ | Say "STOP!" anytime |

### What Changes (GPIO Not Available)

| Feature | Without GPIO | With GPIO |
|---------|--------------|-----------|
| Visual Feedback | Console colors | RGB LED colors |
| Physical Button | ❌ Not available | ✅ GPIO button |
| LED States | Text output | Actual LEDs |

---

## 🚀 Quick Start (No GPIO)

### 1. Update Configuration

```yaml
# config/settings.yaml
gpio:
  enabled: false  # ← Set this to false
```

### 2. Install and Run

```bash
cd ~/voice-assistant
source venv/bin/activate
pip install -r requirements.txt

# Download models
# (See main README.md for model download instructions)

# Run
cd src
python main.py
```

### 3. Use Voice Interrupt

Since there's no physical button, use voice commands:

- Say **"STOP!"** at any time to interrupt
- Say **"cut it"** or **"enough"** also work

---

## 📺 What You'll See

Instead of LED colors, you'll see console output:

```
[LISTENING]
🎤 Listening...
  → 'How do rockets work?'

[THINKING]
🧠 Processing question...

[SPEAKING]
🔊 Speaking: Rockets work like a balloon...

[IDLE]
```

---

## 🔌 Optional: USB Alternatives

If you want visual feedback without GPIO:

### USB RGB LED Strip
- Plug into USB
- Control via software (not GPIO)
- Example: [Adafruit NeoPixel](https://www.adafruit.com/product/1428)

### USB Push Button
- Plug into USB
- Acts as keyboard input
- Any key press can interrupt

---

## 🎯 Demo Without GPIO

The assistant works **just as well** without GPIO! The core AI features are all software-based:

1. **Say "Hey Buddy!"** → Console shows `[LISTENING]`
2. **Ask a question** → Console shows `[THINKING]`
3. **Hear the answer** → Console shows `[SPEAKING]`
4. **Say "STOP!"** → Console shows `[INTERRUPTED]`

---

## 📊 Performance

| Metric | With GPIO | Without GPIO |
|--------|-----------|--------------|
| Wake Word Latency | ~100ms | ~100ms |
| STT Speed | ~2x real-time | ~2x real-time |
| LLM Response | ~3-5 seconds | ~3-5 seconds |
| TTS Quality | Same | Same |

**No performance difference!** GPIO is only for visual/physical feedback.

---

## 💡 Tips for Demo

Without visual LED feedback:

1. **Use a large screen** - Show the console output to kids
2. **Announce states** - "I'm listening now!" "Let me think..."
3. **Use the Hailo board LEDs** - If your Hailo-8L has status LEDs, they may light up during AI processing
4. **Focus on the voice** - The TTS is the main feedback

---

## 🛠️ Troubleshooting

### "GPIO permission denied"
```bash
# This is OK! Just set gpio.enabled: false in config
```

### "No visual feedback"
```bash
# Check console output - it shows colored state names
# Or connect a monitor to the RPi
```

### "Can't interrupt"
```bash
# Say "STOP!" loudly
# Make sure Vosk transcribed it correctly
# Check console for "Interrupt word detected"
```

---

**The assistant works great without GPIO!** The AI magic is all in the software. 🚀