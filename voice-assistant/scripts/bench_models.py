#!/usr/bin/env python3
"""Benchmark LLM models for STEM Buddy - speed, quality, RAM."""

from pathlib import Path
from time import time
import sys

PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

MODELS = {
    "K2-Horizon-0.9B": {"size": "0.9B", "quant": "Q8_0", "file": "K2-Horizon-0.9B-Q8_0.gguf", "is_qwen": False,
        "url": "https://huggingface.co/neversleep/K2-Horizon-0.9B-GGUF/resolve/main/K2-Horizon-0.9B-Q8_0.gguf"},
    "Spark-X2.5-1.7B": {"size": "1.7B", "quant": "Q4_K_M", "file": "spark-x2.5-1.7b-instruct-q4_k_m.gguf", "is_qwen": False,
        "url": "https://huggingface.co/modelscope/spark-x2.5-1.7b-instruct-gguf/resolve/main/spark-x2.5-1.7b-instruct-q4_k_m.gguf"},
    "Qwen3.5-2B": {"size": "2B", "quant": "Q4_K_XL", "file": "qwen3.5-2b-instruct-q4_k_xl.gguf", "is_qwen": True,
        "url": "https://huggingface.co/Qwen/Qwen3.5-2B-Instruct-GGUF/resolve/main/qwen3.5-2b-instruct-q4_k_xl.gguf"},
    "MiniCPM5-2B": {"size": "2B", "quant": "Q4_K_M", "file": "minicpm5-2b-q4_k_m.gguf", "is_qwen": False,
        "url": "https://huggingface.co/openbmb/Minicpm5-2b-gguf/resolve/main/minicpm5-2b-q4_k_m.gguf"},
    "Ling-3.0-tiny": {"size": "7.9B-A1.3B", "quant": "Q4_K_M", "file": "ling-3.0-tiny-a1.3b-q4_k_m.gguf", "is_qwen": False,
        "url": "https://huggingface.co/lingyi-inc/Ling-3.0-tiny-A1.3B-GGUF/resolve/main/ling-3.0-tiny-a1.3b-q4_k_m.gguf"},
    "LFM2.5-8B": {"size": "8B-A1B", "quant": "Q4_K_M", "file": "lfm2.5-8b-a1b-q4_k_m.gguf", "is_qwen": False,
        "url": "https://huggingface.co/lingyi-inc/LFM2.5-8B-A1B-GGUF/resolve/main/lfm2.5-8b-a1b-q4_k_m.gguf"},
}

QUESTIONS = ["Why is the sky blue?", "How do rockets work?", "What is gravity?"]
MOCK_CTX = [{"text": "Sky is blue because blue light scatters more."}, {"text": "Rockets use Newtons Third Law."}]
SYS = "You are STEM Buddy for 4th-5th graders. Answer in 1-2 short sentences, simple words, under 40 words."

