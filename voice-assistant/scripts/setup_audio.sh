#!/bin/bash
# Auto-detect and configure ALSA for USB audio

echo "🔊 Setting up audio..."

# Remove hardcoded card config
sudo rm -f /etc/asound.conf

# Test playback with default device
echo "Testing audio output..."
if sox -n -t alsa default synth 0.1 sine 1000 vol 0.5 2>&1 | grep -q "Done"; then
    echo "✓ Audio device working (default)"
    exit 0
else
    echo "✗ Default audio device failed"
    echo "Available devices:"
    aplay -l 2>/dev/null | head -10
    exit 1
fi
