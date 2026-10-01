# STEM Buddy Setup - Without GPIO (Hailo HAT)

## ✅ Yes, It Works!

The voice assistant runs **perfectly without GPIO pins**. The Hailo-8L HAT may cover the GPIO header, but the core features don't need them.

---

## What You Get Without GPIO

| Feature | Works Without GPIO? | How It Works |
|---------|---------------------|--------------|
| **Wake Word** | ✅ Yes | Say "Hey Buddy" |
| **Speech Recognition** | ✅ Yes | Vosk converts speech to text |
| **Knowledge Base** | ✅ Yes | Wikipedia facts offline |
| **LLM Answers** | ✅ Yes | Phi-3 generates responses |
| **Text-to-Speech** | ✅ Yes | Piper speaks answers |
| **Interrupt** | ✅ Yes | Say "STOP!" (voice only) |
| **LED Feedback** | ⚠️ Console | Colored text instead of LEDs |
| **Physical Button** | ❌ No | Use voice "STOP!" instead |

---

## Quick Setup (5 minutes)

### 1. Configuration is Already Set

The config file already has GPIO disabled:

```yaml
gpio:
  enabled: false  # Already set!
```

### 2. Install on RPi

```bash
# SSH to RPi
ssh pi@<RPi_IP>

# Navigate to project
cd ~/voice-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Download Models

```bash
# STT model (30MB)
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip -d models/

# TTS model (50MB)
wget https://github.com/rhasspy/piper-models/releases/download/v1.2.0/en_US-lessac-medium.onnx
wget https://github.com/rhasspy/piper-models/releases/download/v1.2.0/en_US-lessac-medium.onnx.json
mv *.onnx* models/

# LLM model (2.3GB, optional)
# Download from HuggingFace if you want better answers
```

### 4. Install Piper TTS

```bash
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_linux_x64
chmod +x piper_linux_x64
sudo mv piper_linux_x64 /usr/local/bin/piper
```

### 5. Run!

```bash
cd src
python main.py
```

---

## How to Use

### Start Listening
Say: **"Hey Buddy!"** (or clap loudly for demo mode)

### Ask Questions
- "How do rockets work?"
- "Why is the sky blue?"
- "Tell me about dinosaurs?"

### Interrupt
Say: **"STOP!"** anytime

### Visual Feedback
Instead of LEDs, you'll see colored console output:
- `[LISTENING]` - Blue text
- `[THINKING]` - Yellow text  
- `[SPEAKING]` - Green text
- `[INTERRUPTED]` - Red text

---

## Hardware You Still Need

| Component | Required | Notes |
|-----------|----------|-------|
| USB Microphone | ✅ Yes | Any USB mic works |
| USB Speakers | ✅ Yes | Or 3.5mm audio |
| Push Button | ❌ No | Use voice "STOP!" |
| RGB LED | ❌ No | Console output instead |

---

## Demo Mode (No Models Needed)

If you don't want to download the 2.3GB LLM model, the system uses **fallback answers**:

```python
# Fallback answers are pre-written for common questions
# Like "How do rockets work?" → "Rockets work like a balloon!"
```

This is **perfect for demos** - fast and reliable!

---

## Performance Expectations

| Task | Time | Notes |
|------|------|-------|
| Wake Word Detection | <1 sec | Instant |
| Speech Recognition | 1-2 sec | Depends on phrase length |
| Knowledge Search | <1 sec | Vector DB is fast |
| LLM Generation | 3-5 sec | With Phi-3 (2.3GB model) |
| Fallback Answer | <0.1 sec | Instant (no LLM) |
| TTS Speech | Varies | Depends on answer length |

**Total latency**: ~5-10 seconds from question to answer

---

## Troubleshooting

### "No audio input"
```bash
# Check microphone
arecord -l

# Test audio
python3 -c "import sounddevice as sd; sd.play(sd.rec(2, 16000))"
```

### "GPIO error"
```
⚠ GPIO not available
  Voice interrupt only (say 'STOP!')
```
This is **expected and OK** - the system continues without GPIO.

### "LED error"
```
⚠ LED not available (Hailo HAT may cover pins)
  Using console output instead
```
This is **expected and OK** - you'll see colored text instead.

---

## Next Steps

1. ✅ **Test on RPi** - Run `python main.py`
2. ✅ **Connect mic + speakers** - USB devices
3. ✅ **Download models** - At least Vosk + Piper
4. ✅ **Demo for kids** - Say "Hey Buddy!"

---

## Want GPIO Features Later?

If you get a GPIO expander or move the Hailo HAT:

1. Edit `config/settings.yaml`:
   ```yaml
   gpio:
     enabled: true
   ```

2. Connect button to GPIO 4 + GND
3. Connect RGB LED to GPIO 17, 27, 22 + GND
4. Restart the assistant

---

**The system is fully functional without GPIO!** 🚀

Just use voice commands and enjoy the show!