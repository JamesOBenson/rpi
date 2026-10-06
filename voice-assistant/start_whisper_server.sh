#!/bin/bash
# Start Whisper HTTP server in background
# Run this before ./buddy.sh when using question_engine: "whisper-http"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8765
MODEL="small.en"
PROMPT="STEM and cybersecurity questions for kids. Topics: passwords, phishing, scams, black holes, sky, rockets, electricity, atoms, viruses, hacking."

echo "Starting Whisper HTTP server..."
echo "  Model: $MODEL"
echo "  Port: $PORT"

python3 src/whisper_server.py \
    --port $PORT \
    --model $MODEL \
    --prompt "$PROMPT" &

SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo "✓ Whisper server ready (PID: $SERVER_PID)"
        echo "  Run './buddy.sh' to start the assistant"
        echo "  (server will keep running in background)"
        exit 0
    fi
    sleep 0.5
done

echo "✗ Server failed to start"
kill $SERVER_PID 2>/dev/null || true
exit 1