#!/bin/bash
# Quick test to verify setup

echo "=== STEM Buddy Setup Test ==="
echo ""

# Check dependencies
echo "1. Checking dependencies..."
python3 -c "import openwakeword" 2>/dev/null && echo "  ✓ openwakeword" || echo "  ✗ openwakeword (pip install openwakeword)"
python3 -c "import faster_whisper" 2>/dev/null && echo "  ✓ faster-whisper" || echo "  ✗ faster-whisper (pip install faster-whisper)"
which piper 2>/dev/null && echo "  ✓ piper-tts" || echo "  ✗ piper-tts (needs installation)"
echo ""

# Check config
echo "2. Checking config..."
grep -q 'framework: "openwakeword"' config/settings.yaml && echo "  ✓ OpenWakeWord enabled" || echo "  ✗ OpenWakeWord not enabled"
grep -q 'question_engine: "whisper-http"' config/settings.yaml && echo "  ✓ Whisper HTTP enabled" || echo "  ✗ Whisper HTTP not enabled"
grep -q 'mode: "http"' config/settings.yaml && echo "  ✓ TTS HTTP enabled" || echo "  ✗ TTS HTTP not enabled"
echo ""

# Check servers
echo "3. HTTP server status..."
pgrep -f "whisper_server.py" > /dev/null && echo "  ✓ Whisper server running" || echo "  ✗ Whisper server NOT running"
pgrep -f "tts_server.py" > /dev/null && echo "  ✓ TTS server running" || echo "  ✗ TTS server NOT running"
echo ""

# Check service
echo "4. Systemd service..."
systemctl is-active stem-buddy.service 2>/dev/null | grep -q "active" && echo "  ✓ Service running" || echo "  ✗ Service NOT running"
echo ""

echo "=== Test Complete ==="
echo ""
echo "To start everything:"
echo "  ./buddy.sh start"
echo ""
echo "To start just HTTP servers:"
echo "  ./buddy.sh servers"