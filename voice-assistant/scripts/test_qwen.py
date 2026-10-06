#!/usr/bin/env python3
from llama_cpp import Llama
import time

llm = Llama(model_path='models/Qwen3.5-2B-Q4_K_M.gguf', n_ctx=512, n_threads=4, verbose=False)

prompt = "<|im_start|>system\nYou are STEM Buddy. Answer in 1-2 short sentences.\n<|im_end|>\n<|im_start|>user\nWhy is the sky blue? /no_think\n<|im_end|>\n<|im_start|>assistant\n"

t0 = time.time()
chars = 0
for out in llm(prompt, max_tokens=50, stream=True):
    t = out['choices'][0].get('text', '')
    if t:
        chars += len(t)
        print(t, end='', flush=True)
print()
elapsed = time.time() - t0
print(f'Total: {chars} chars in {elapsed:.2f}s ({chars/elapsed:.0f} chars/s)')