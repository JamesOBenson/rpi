#!/usr/bin/env python3
"""Does STREAMING vosk + SetWords(['buddy']) hear the user's 'buddy'?

Feeds the user's real direct captures in 0.1s chunks (exactly like the
live loop) and collects every final. Compares plain vs biased.
"""
import glob, json, os, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from stt_engine import WakeWordListener

SR = 16000
print("Loading vosk large...", flush=True)
wake = WakeWordListener(wake_word="buddy", model_size="large")
model = wake.model

def stream_finals(audio16, words=None):
    rec = wake._rec()
    if words and hasattr(rec, "SetWords"):
        rec.SetWords(words)
    finals = []
    for i in range(0, len(audio16), SR // 10):
        chunk = audio16[i:i + SR // 10].tobytes()
        if rec.AcceptWaveform(chunk):
            finals.append(json.loads(rec.FinalResult()).get("text", "") or "")
            rec.Reset()
    if rec.AcceptWaveform(b""):  # flush
        t = json.loads(rec.FinalResult()).get("text", "") or ""
        if t:
            finals.append(t)
    return finals

wavs = sorted(glob.glob(f"{ROOT}/logs/audio/q-*.wav"))
tail = np.zeros(SR, dtype=np.int16)  # 1s silence to force endpointing
for f in wavs:
    w = wave.open(f, "rb")
    a16 = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    audio = np.concatenate([a16, tail])
    plain = stream_finals(audio)
    biased = stream_finals(audio, words=["buddy"])
    hit_p = "buddy" in " ".join(plain)
    hit_b = "buddy" in " ".join(biased)
    print(f"\n{os.path.basename(f)} ({len(a16)/SR:.1f}s)")
    print(f"  plain : {plain}  {'WAKE' if hit_p else ''}")
    print(f"  biased: {biased}  {'WAKE' if hit_b else ''}")