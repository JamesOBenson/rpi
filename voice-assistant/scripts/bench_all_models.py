#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

MODELS = {
    "K2-Horizon-1B": {"file": "K2-Horizon-1B-Q4_K_M.gguf", "url": "https://huggingface.co/IFM/K2-Horizon-0.9B-GGUF/resolve/main/K2-Horizon-1B-Q4_K_M.gguf"},
    "Qwen3.5-2B": {"file": "Qwen3.5-2B-Q4_K_M.gguf", "url": "https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf"},
    "MiniCPM3-2B": {"file": "minicpm3-2b-q4_k_m.gguf", "url": "https://huggingface.co/unsloth/MiniCPM3-2B-GGUF/resolve/main/minicpm3-2b-q4_k_m.gguf"},
    "Gemma-3n-E2B": {"file": "gemma-3n-E2B-it-Q4_K_M.gguf", "url": "https://huggingface.co/unsloth/gemma-3n-E2B-it-GGUF/resolve/main/gemma-3n-E2B-it-Q4_K_M.gguf"},
}

def download(name, info):
    p = MODELS_DIR / info["file"]
    if p.exists() and p.stat().st_size > 0:
        print(f"✓ {name} - present")
        return
    print(f"Downloading {name}...")
    subprocess.run(["wget", "-q", "--show-progress", info["url"], "-O", str(p)], capture_output=False)

def bench(name, path):
    result = subprocess.run(["venv/bin/python", str(PROJECT_ROOT/"scripts/bench_model_tps.py"), str(path), name], capture_output=True, text=True, timeout=120)
    return result.stdout + result.stderr

if __name__ == "__main__":
    MODELS_DIR.mkdir(exist_ok=True)
    if "--download" in sys.argv:
        print("=== Downloading ===")
        for n, i in MODELS.items(): download(n, i)
    
    avail = [(n, MODELS_DIR/i["file"]) for n, i in MODELS.items() if (MODELS_DIR/i["file"]).exists() and (MODELS_DIR/i["file"]).stat().st_size > 0]
    if not avail:
        print("No models. Use --download")
        sys.exit(1)
    
    print(f"
=== Benchmarking {len(avail)} models ===
")
    for name, path in avail:
        print(f"
{'='*50}
{name}
{'='*50}")
        print(bench(name, path))
    
    print("
Thresholds: >=10 t/s good, 6-10 borderline, <6 too slow")
