#!/usr/bin/env bash
# Run STEM Buddy from the project root
# Usage: ./run.sh
set -e

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ No virtual environment found. Run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

echo "🎤 Starting STEM Buddy..."
python3 src/main.py "$@"