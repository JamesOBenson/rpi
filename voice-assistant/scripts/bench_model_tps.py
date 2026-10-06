#!/usr/bin/env python3
"""Benchmark any .gguf LLM for STEM Buddy on the Pi: prefill + decode speed.

Usage:
    venv/bin/python scripts/bench_model_tps.py <model.gguf> [label]

Run with the service stopped (sudo -n systemctl stop stem-buddy.service) -
a running assistant degrades results by ~40%. Restart it afterwards.

Methodology (matters!):
- llama-cpp-python >= 0.3 reuses KV cache across calls with the SAME prompt
  ("full prompt already cached, skipping reset"), so we call llm.reset()
  before every timed run.
- prefill: llm(prompt, max_tokens=1), reset between runs, median of 5.
- generation: stream 100 tokens, rate = (tokens-1) / (total - first_token),
  median of 3.
- 4 threads: this Pi exposes only 4 A76 cores; 8 threads measured ~15% slower.
- Chat format is auto-detected from the model filename:
  * "qwen" in name -> Qwen im_start template + /no_think (thinking off;
    without it Qwen3 models think for ~17s before answering) + a guard that
    skips the empty think-tag pair Qwen3 emits before the answer
  * anything else  -> Gemma-style <start_of_turn> template
  n_ctx auto-bumps to 1024 for non-Qwen models (Gemma 3 RoPE minimum).

The prompt mirrors the real app (same system prompt, 3 RAG facts, same
question), so numbers are comparable across model generations.

Interpreting results (this Pi, 4 A76 cores @ 2.4GHz):
    decode >= 10 t/s  -> good, first sentence ~2-3s, usable as default
    decode  6-10 t/s  -> borderline, watch first-sentence latency
    decode <  6 t/s   -> too slow for the voice loop
    prefill < 40 t/s  -> first sentence will feel slow regardless of decode

Recent measurements on this Pi (for reference):
    Qwen2-1.5B Q4_K_M   ~12 t/s decode   (old default, measured when cooler)
    Qwen3-1.7B Q4_K_M   ~ 9 t/s decode   (current backup)
    Gemma 3n E2B Q4_K_M ~ 6 t/s decode   (current default - shorter answers)
    Qwen3-4B     Q4_K_S  ~ 5 t/s decode   (too slow)

    NOTE: this machine idles ~63C and hits 80C (throttle zone) within ~30s
    of 4-thread load, so decode rates are thermally capped. If results look
    far off from these, check cooling before drawing conclusions.
"""
import sys, time, statistics
from llama_cpp import Llama

IM_START = "\u003c|im_start|>"
IM_END = "\u003c|im_end|>"
THINK_END = "\u003c/think\u003e"
SOT = "<start_of_turn>"
EOT = "<end_of_turn>"

FACTS = [
    "The sky is blue because sunlight scatters off air molecules. Blue light scatters more than red light, so the whole sky looks blue to our eyes.",
    "Octopuses have blue blood because they use hemocyanin, which contains copper, instead of the iron in our blood.",
    "Blue light has a shorter wavelength than red light, so it scatters in all directions when sunlight hits the atmosphere.",
]
SYSTEM = ("You are STEM Buddy, a friendly AI for 4th-5th graders.\n"
          "Answer in 1-2 short sentences, simple words, under 40 words.\n"
          "Use the facts below when they answer the question; ignore them otherwise.")
QUESTION = "why is the sky blue"


def build_prompt(model_name: str):
    """Return (prompt, stop_tokens) in the model's native chat format."""
    facts = "\n- ".join(FACTS)
    if "qwen" in model_name.lower():
        user_msg = f"Facts:\n- {facts}\n\nQ: {QUESTION} /no_think"
        prompt = (
            f"{IM_START}system\n{SYSTEM}\n{IM_END}\n"
            f"{IM_START}user\n{user_msg}{IM_END}\n"
            f"{IM_START}assistant\n"
        )
        return prompt, ["\n\nQ:", "\n\nQuestion:", "Question:", "###"]
    user_msg = f"{SYSTEM}\nFacts:\n- {facts}\n\nQ: {QUESTION}"
    prompt = (
        f"{SOT}user\n{user_msg}\n{EOT}\n"
        f"{SOT}model\n"
    )
    return prompt, [EOT, SOT]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    model_path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else model_path.split("/")[-1]
    is_qwen = "qwen" in model_path.lower()
    prompt, stop = build_prompt(model_path)

    n_ctx = 512 if is_qwen else 1024
    llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=4,
                n_gpu_layers=0, verbose=False)
    ntok = len(llm.tokenize(prompt.encode("utf-8"), add_bos=True))
    llm(prompt, max_tokens=1)  # warmup

    times = []
    for _ in range(5):
        llm.reset()
        t0 = time.time()
        llm(prompt, max_tokens=1)
        times.append(time.time() - t0)
    med = statistics.median(times)
    print(f"[{label}] prompt={ntok} tok | prefill median {med:.2f}s -> "
          f"{ntok/med:.0f} t/s  (range {min(times):.2f}-{max(times):.2f})")

    rates = []
    for _ in range(3):
        llm.reset()
        first = None; toks = 0; t0 = time.time()
        buffer = ""
        for out in llm(prompt, max_tokens=100, temperature=0.3,
                       stop=stop, stream=True):
            t = out["choices"][0].get("text")
            if not t:
                continue
            buffer += t
            # Skip think tags for Qwen models
            if is_qwen and THINK_END in buffer:
                idx = buffer.find(THINK_END)
                buffer = buffer[idx + len(THINK_END):]
            if buffer:
                if first is None:
                    first = time.time() - t0
                toks += 1
                buffer = ""
        total = time.time() - t0
        if first is not None and total > first and toks > 1:
            rates.append((toks - 1) / (total - first))
    if rates:
        print(f"[{label}] generation {statistics.median(rates):.1f} t/s "
              f"(range {min(rates):.1f}-{max(rates):.1f})")
    else:
        print(f"[{label}] generation: no tokens generated")


if __name__ == "__main__":
    main()