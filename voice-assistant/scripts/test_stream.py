#!/usr/bin/env python3
import sys, time
sys.path.insert(0, "src")
import llama_cpp
print("llama-cpp-python:", llama_cpp.__version__)
llm = llama_cpp.Llama(
    "/home/rpi/voice-assistant/models/qwen2-1.5b-instruct.Q4_K_M.gguf",
    n_ctx=512, n_threads=8, verbose=False
)
prompt = "###system\nYou are a helper. Answer in one short sentence.\n###\n###user\nWhat is a black hole?\n###\n###assistant\n"
t0 = time.time()
first = None
n = 0
for out in llm(prompt, max_tokens=60, temperature=0.3, stream=True, echo=False):
    tok = out["choices"][0]["text"]
    if first is None:
        first = time.time()
        print(f"first token: {first - t0:.2f}s  ({tok!r})")
    n += 1
t1 = time.time()
print(f"total: {t1 - t0:.2f}s for {n} tokens = {(n)/(t1 - t0):.1f} tok/s")