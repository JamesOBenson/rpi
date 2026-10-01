#!/usr/bin/env python3
"""
Live end-to-end test: beeps, then listens for "Buddy" + question,
runs RAG+LLM, and speaks the answer. Uses the real components.
The service must be stopped first (it holds the mic).
"""
import sys
import time
import threading

sys.path.insert(0, "src")
import numpy as np
import sounddevice as sd

from stt_engine import WakeWordListener
from whisper_engine import WhisperSTT
from llm_engine import LocalLLM
from knowledge_base import KnowledgeBase
from tts_engine import TextToSpeech


def beep(freq=880, dur=0.7):
    t = np.linspace(0, dur, int(16000 * dur), False)
    tone = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sd.play(tone, 16000, blocking=True)


print("Setting up components...", flush=True)
wake = WakeWordListener(wake_word="buddy", model_size="small", hybrid=True)
whisper = WhisperSTT(model_size="small.en")
llm = LocalLLM()
kb = KnowledgeBase()
tts = TextToSpeech()
llm.initialize()
kb.initialize()
print("Ready.", flush=True)

stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
stream.start()
print(">>> BEEP in 1s - when you hear it, say: Buddy, what is a black hole?", flush=True)
time.sleep(1)
beep()
beep()

q, q_audio = wake.wait_for_question(stream)
if q_audio is not None:
    w = whisper.transcribe(q_audio)
    if w:
        q = w
print(f"\n>>> CAPTURED QUESTION: {q!r}", flush=True)

if q:
    print("Thinking...", flush=True)
    ans = llm.query_with_rag(q, kb, top_k=3)
    print(f">>> ANSWER: {ans}", flush=True)
    stop_ev = threading.Event()
    watching = threading.Event()
    watching.set()
    w = threading.Thread(target=wake.watch_for_stop, args=(stream, stop_ev, watching), daemon=True)
    w.start()
    tts.speak(ans, on_interrupt=stop_ev.is_set)
    watching.clear()
    w.join(timeout=1)
    if stop_ev.is_set():
        print(">>> INTERRUPTED by STOP", flush=True)

stream.stop()
stream.close()
print(">>> DONE", flush=True)