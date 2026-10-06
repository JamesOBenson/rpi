#!/bin/bash
# Start Piper TTS HTTP server in background
# Run this before ./buddy.sh when using tts.mode: "http"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8766
VOICE="en_US-amy-medium"

echo "Starting Piper TTS server..."
echo "  Voice: $VOICE"
echo "  Port: $PORT"

# Start server in background
python3 src/tts_server.py \
    --port $PORT \
    --voice $VOICE &

SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo "✓ TTS server ready (PID: $SERVER_PID)"
        echo "  Run './buddy.sh' to start the assistant"
        exit 0
    fi
    sleep 0.5
done

echo "✗ Server failed to start"
kill $SERVER_PID 2>/dev/null || true
exit 1