#!/usr/bin/env bash
# Download all AI models for STEM Buddy
# Run once: ./download_models.sh
set -e
cd "$(dirname "$0")"
mkdir -p models
cd models

echo "=== Downloading AI Models ==="

# 1. Vosk STT model (30MB) - if missing
if [ ! -d "vosk-model-small-en-us-0.15" ]; then
    echo "1/3: Vosk STT model (30MB)..."
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
else
    echo "1/3: Vosk STT model - already present"
fi

# 2. Piper TTS voice (61MB) - if missing
if [ ! -f "en_US-lessac-medium.onnx" ]; then
    echo "2/3: Piper TTS voice (61MB)..."
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
else
    echo "2/3: Piper TTS voice - already present"
fi

# 3. Qwen2-1.5B LLM (941MB) - if missing
if [ ! -f "qwen2-1.5b-instruct.Q4_K_M.gguf" ]; then
    echo "3/3: Qwen2-1.5B LLM (941MB)..."
    wget -q "https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF/resolve/main/qwen2-1_5b-instruct-q4_k_m.gguf" -O qwen2-1.5b-instruct.Q4_K_M.gguf
else
    echo "3/3: Qwen2-1.5B LLM - already present"
fi

# Optional: Phi-3 mini (2.3GB) - deeper but slower (~30s answers)
if [ ! -f "phi-3-mini-4k-instruct.Q4_K_M.gguf" ]; then
    read -p "Also download Phi-3 mini (2.3GB, slower but deeper)? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        echo "  Downloading Phi-3 mini (2.3GB)..."
        wget -q "https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF/resolve/main/Phi-3-mini-4k-instruct-Q4_K_M.gguf" -O phi-3-mini-4k-instruct.Q4_K_M.gguf
    fi
fi

echo ""
echo "=== Done! Models in $(pwd) ==="
ls -lh *.gguf *.onnx* 2>/dev/null
echo ""
echo "To switch models, edit config/settings.yaml -> llm.model"