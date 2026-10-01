#!/usr/bin/env python3
"""Offline verification of the NEW wake path on REAL missed-wake audio.

Replicates wait_for_question's hybrid idle branch exactly:
  window -> _trim_silence -> _normalize_for_asr -> whisper -> _has_wake
         -> _after_wake -> _meaningful -> return (q, audio)
"""
import glob, os, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 16000
sys.path.insert(0, os.path.join(ROOT, "src"))
from stt_engine import WakeWordListener
from whisper_engine import WhisperSTT

print("Loading engines...", flush=True)
wake = WakeWordListener(wake_word="buddy", model_size="large", hybrid=True)
whisper = WhisperSTT(model_size="base.en", cpu_threads=4)
wake.whisper = whisper

def load(f):
    """Load as int16 - exactly what the ring buffer holds in production."""
    w = wave.open(f, "rb")
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

wavs = sorted(glob.glob(f"{ROOT}/logs/audio/idle-*.wav")) + \
       sorted(glob.glob(f"{ROOT}/logs/audio/q-*.wav"))
print(f"\nTesting {len(wavs)} real captures through the NEW wake path:\n")

for f in wavs:
    window = load(f)
    audio = wake._normalize_for_asr(wake._trim_silence(window))
    if audio is None:
        print(f"{os.path.basename(f)}: (all silence - skipped)")
        continue
    if len(audio) / SR > wake.max_question_sec:
        print(f"{os.path.basename(f)}: ({len(audio)/SR:.1f}s voiced - long background, skipped, NO whisper decode)\n")
        continue
    text = whisper.transcribe(audio)
    if wake._has_wake(text):
        q = wake._after_wake(text)
        ok = wake._meaningful(q)
        print(f"{os.path.basename(f)}:")
        print(f"  whisper: {text!r}")
        print(f"  -> WAKE CONFIRMED, question={q!r}  {'PROCESSED' if ok else '(too short)'}\n")
    else:
        print(f"{os.path.basename(f)}:")
        print(f"  whisper: {text!r}")
        print(f"  -> not addressed to us, ignored\n")