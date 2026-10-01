#!/usr/bin/env python3
"""Measure the latency of each pipeline stage."""
import sys, time, json, tempfile, subprocess
sys.path.insert(0, "src")
from llm_engine import LocalLLM
from knowledge_base import KnowledgeBase
from tts_engine import TextToSpeech

question = "What is a black hole"
print(f"Question: {question!r}\n")

t0 = time.time()
kb = KnowledgeBase(); kb.initialize()
t_kb = time.time() - t0
print(f"[1] Knowledge base init:      {t_kb:.2f}s")

t0 = time.time()
docs = kb.query(question, top_k=3)
t_rag = time.time() - t0
doc_chars = sum(len(d["text"]) for d in docs)
print(f"[2] RAG search (top_k=3):     {t_rag:.2f}s  ({len(docs)} docs, {doc_chars} chars)")

t0 = time.time()
llm = LocalLLM(); llm.initialize()
t_llm_load = time.time() - t0
print(f"[3] LLM load:                 {t_llm_load:.2f}s")

t0 = time.time()
ans = llm.query_with_rag(question, kb, top_k=3)
t_gen = time.time() - t0
# Show prompt size (drives prefill time)
prompt = llm._build_prompt(question, kb.query(question, top_k=3))
print(f"[4] LLM generate (full):      {t_gen:.2f}s  -> {len(ans.split())} words")
print(f"    prompt size: {len(prompt)} chars  |  answer: {ans}")

t0 = time.time()
tts = TextToSpeech()
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    out = f.name
subprocess.run(["piper", "-m", str(tts.model_path), "-f", out], input=ans.encode(), capture_output=True, timeout=60)
t_tts = time.time() - t0

import wave
with wave.open(out, "rb") as wf:
    dur = wf.getnframes() / wf.getframerate()
print(f"[5] TTS synthesize:           {t_tts:.2f}s  ({dur:.1f}s of audio)")
import os; os.unlink(out)

print(f"\n=== Perceived latency (question-done -> first word heard) ===")
print(f"RAG + LLM + TTS = {t_rag + t_gen + t_tts:.1f}s  (+ ~0.5-1s speech pause)")
print(f"Audio playback (the answer itself) = {dur:.1f}s")