#!/usr/bin/env bash
# Benchmark all candidate LLM models
# Usage: ./bench_all.sh [--download]
set -e
cd "$(dirname "$0")/.."

# Stop the service to avoid interference
if systemctl is-active --quiet stem-buddy.service 2>/dev/null; then
    echo "Stopping stem-buddy.service..."
    sudo systemctl stop stem-buddy.service
fi

# Run benchmark
venv/bin/python scripts/bench_all_models.py "$@"

# Restart the service
if systemctl is-active --quiet stem-buddy.service 2>/dev/null || systemctl list-units --type=service --all | grep -q stem-buddy; then
    echo ""
    echo "Restarting stem-buddy.service..."
    sudo systemctl start stem-buddy.service
fi