#!/bin/bash
#
# STEM Buddy Setup Script
# =======================
# Run this once to set up the voice assistant
#

set -e

echo "🚀 STEM Buddy Setup"
echo "=================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running on Raspberry Pi
if ! grep -q "Raspberry" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Not running on Raspberry Pi detected${NC}"
    echo "   Some features may not work (GPIO, Hailo-9L)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create directories
echo -e "${GREEN}✓${NC} Creating directories..."
mkdir -p src config data models logs vocab

# Install Python dependencies
echo -e "${GREEN}✓${NC} Installing Python packages..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Download Vosk model
echo -e "${GREEN}✓${NC} Downloading Vosk speech model..."
if [ ! -d "models/vosk-model-small-en-us-0.15" ]; then
    echo "  Downloading (30MB)..."
    wget -O vosk-model.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip vosk-model.zip -d models/
    rm vosk-model.zip
    echo "  ✓ Vosk model downloaded"
else
    echo "  ✓ Vosk model already exists"
fi

# Download Piper TTS voice
echo -e "${GREEN}✓${NC} Setting up Piper TTS..."
if ! command -v piper &> /dev/null; then
    echo "  ⚠️  Piper not found"
    echo "  Install from: https://github.com/rhasspy/piper"
    echo "  Or use fallback (espeak): sudo apt install espeak"
else
    echo "  ✓ Piper found"
fi

# Download LLM model (optional, large file)
echo -e "${GREEN}✓${NC} LLM model setup..."
if [ ! -f "models/phi-3-mini-4k-instruct.Q4_K_M.gguf" ]; then
    echo "  ⚠️  Phi-3 model not found (2.3GB)"
    echo "  Download manually from:"
    echo "  https://huggingface.co/Mozilla/phi-3-mini-4k-instruct-gguf"
    echo "  Place in: models/phi-3-mini-4k-instruct.Q4_K_M.gguf"
else
    echo "  ✓ Phi-3 model found"
fi

# Configure GPIO permissions
echo -e "${GREEN}✓${NC} Configuring GPIO..."
if groups | grep -q gpio; then
    echo "  ✓ User already in gpio group"
else
    echo "  Adding user to gpio group..."
    sudo usermod -a -G gpio $USER
    echo "  ⚠️  Log out and back in for GPIO access"
fi

# Create config file
echo -e "${GREEN}✓${NC} Creating configuration..."
if [ ! -f "config/settings.yaml" ]; then
    cp config/settings.yaml.example config/settings.yaml 2>/dev/null || true
    echo "  ✓ Config created"
fi

# Test audio
echo -e "${GREEN}✓${NC} Testing audio..."
python3 -c "import sounddevice as sd; print('Audio devices:', sd.query_devices())" 2>/dev/null || \
    echo "  ⚠️  Audio test skipped"

# Summary
echo ""
echo "=================="
echo "📦 Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Download Phi-3 model (optional, for better answers)"
echo "2. Connect microphone and speakers"
echo "3. Connect button to GPIO 4 and GND"
echo "4. Connect RGB LED to GPIO 17, 27, 22"
echo "5. Run: source venv/bin/activate && python src/main.py"
echo ""
echo "For help, see README.md"
echo ""