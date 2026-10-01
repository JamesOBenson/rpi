#!/usr/bin/env python3
"""Compare time-to-first-audio: old (full answer first) vs new (streaming)."""
import sys, time, threading, queue
sys.path.insert(0, "src")
from llm_engine import LocalLLM
from knowledge_base import KnowledgeBase
from tts_engine import TextToSpeech

question = "What is a black hole"
print(f"Question: {question!r}\n")
llm = LocalLLM(); llm.initialize()
kb = KnowledgeBase(); kb.initialize()
tts = TextToSpeech()

# --- OLD: generate full answer, THEN synthesize ---
t0 = time.time()
ctx = kb.query(question, top_k=3)
ans = llm._generate(llm._build_prompt(question, ctx))
t_gen = time.time() - t0
t0 = time.time()
old_wav = tts.synthesize(ans)
t_tts = time.time() - t0
print(f"OLD pipeline:")
print(f"   LLM (full answer):   {t_gen:.2f}s")
print(f"   TTS (full answer):   {t_tts:.2f}s")
print(f"   >>> first audio at:  {t_gen + t_tts:.2f}s\n")

# --- NEW: streaming, time until FIRST sentence audio is ready ---
ready = queue.Queue()
def worker():
    for sent in llm.query_with_rag_streaming(question, kb, top_k=3):
        wav = tts.synthesize(sent)
        if wav:
            ready.put(wav)
    ready.put(None)

t0 = time.time()
wt = threading.Thread(target=worker, daemon=True); wt.start()
first_wav = ready.get()
t_first = time.time() - t0
print(f"NEW pipeline (streaming):")
print(f"   >>> first audio at:  {t_first:.2f}s   <-- what you wait to hear")
# drain
while True:
    item = ready.get()
    if item is None:
        break
wt.join(timeout=3)
import os
os.unlink(old_wav)
print(f"\nSpeedup on first-word latency: {(t_gen + t_tts - t_first):.1f}s saved")