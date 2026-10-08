#!/usr/bin/env bash
# Download all AI models for STEM Buddy
# Run once: ./download_models.sh
set -e
cd "$(dirname "$0")"
mkdir -p models
cd models

echo "=== Downloading AI Models ==="

# 1. Vosk STT models - if missing
#    small (68MB) = always-on wake word in hybrid mode
#    large (1.3GB) = for question_engine: vosk (A/B)
if [ ! -d "vosk-model-small-en-us-0.15" ]; then
    echo "1/4: Vosk STT small model (68MB)..."
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
else
    echo "1/4: Vosk STT small model - already present"
fi
if [ ! -d "vosk-model-en-us-0.22" ]; then
    echo "      Vosk STT large model (1.3GB, optional)..."
    wget -q https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
    unzip -q vosk-model-en-us-0.22.zip
    rm vosk-model-en-us-0.22.zip
else
    echo "      Vosk STT large model - already present"
fi

# 2. Piper TTS voice (61MB) - if missing
if [ ! -f "en_US-lessac-medium.onnx" ]; then
    echo "2/4: Piper TTS voice (61MB)..."
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
else
    echo "2/3: Piper TTS voice - already present"
fi

# 2b. OpenWakeWord 'buddy' wake model (1.2MB) - custom community model
#     https://huggingface.co/benjamin-paine/hey-buddy
mkdir -p oww
if [ ! -f "oww/hey-buddy.onnx" ]; then
    echo "      OpenWakeWord buddy wake model (1.2MB)..."
    wget -q "https://huggingface.co/benjamin-paine/hey-buddy/resolve/main/models/hey-buddy.onnx" -O oww/hey-buddy.onnx
else
    echo "      OpenWakeWord buddy wake model - already present"
fi


# 2c. Speaker-lock model (CAMPPlus, 29.6MB) - no public source for this
#     exact build, so it's stored in this repo: voice-assistant/models/spk/
mkdir -p spk
if [ ! -f "spk/campplus_en.onnx" ]; then
    echo "      Speaker-lock CAMPPlus model (29.6MB)..."
    wget -q "https://github.com/JamesOBenson/rpi/raw/main/voice-assistant/models/spk/campplus_en.onnx" -O spk/campplus_en.onnx
else
    echo "      Speaker-lock model - already present"
fi

# 3. Gemma 3n E2B LLM (2.9GB) - if missing
#    Backup: Qwen3-1.7B (1.2GB, prompted below) - equally good answers.
#    Switch with llm.model in ../config/settings.yaml
if [ ! -f "gemma-3n-E2B-it-Q4_K_M.gguf" ]; then
    echo "3/4: Gemma 3n E2B LLM (2.9GB)..."
    wget -q "https://huggingface.co/unsloth/gemma-3n-E2B-it-GGUF/resolve/main/gemma-3n-E2B-it-Q4_K_M.gguf" -O gemma-3n-E2B-it-Q4_K_M.gguf
else
    echo "3/4: Gemma 3n E2B LLM - already present"
fi

# Optional: Qwen3-1.7B backup (1.2GB) - equally good answers, smaller
if [ ! -f "Qwen3-1.7B-Q4_K_M.gguf" ]; then
    read -p "Also download Qwen3-1.7B backup (1.2GB)? [Y/n] " reply
    if [[ ! "$reply" =~ ^[Nn]$ ]]; then
        echo "  Downloading Qwen3-1.7B (1.2GB)..."
        wget -q "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf" -O Qwen3-1.7B-Q4_K_M.gguf
    fi
fi

# 4. Whisper STT model (small.en, ~460MB) - if missing
#    First run downloads it from HuggingFace into ~/.cache/huggingface.
if [ -d "$HOME/.cache/huggingface/hub/models--Systran--faster-whisper-small.en" ]; then
    echo "4/4: Whisper STT model - already present"
else
    echo "4/4: Whisper STT model (small.en, ~460MB)..."
    if [ -x "../venv/bin/python" ]; then
        ../venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"
    else
        echo "   (skipped - run: venv/bin/python -c \"from faster_whisper import WhisperModel; WhisperModel('small.en')\")"
    fi
fi

echo ""
echo "=== Done! Models in $(pwd) ==="
ls -lh *.gguf *.onnx* oww/*.onnx 2>/dev/null
echo ""
echo "To switch LLM: edit config/settings.yaml -> llm.model"
echo "To switch STT: edit config/settings.yaml -> stt.question_engine (whisper|vosk)"