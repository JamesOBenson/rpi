#!/usr/bin/env python3
from llama_cpp import Llama
import time, sys, statistics

model_path = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else model_path.split("/")[-1]
is_qwen = "qwen" in model_path.lower()
n_ctx = 512 if is_qwen else 1024

FACTS = "The sky is blue because blue light scatters more than red."
SYSTEM = "You are STEM Buddy. Answer in 1-2 short sentences."
QUESTION = "Why is the sky blue?"

if is_qwen:
    prompt = "<|im_start|>system\n" + SYSTEM + "\n
