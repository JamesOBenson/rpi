#!/usr/bin/env python3
"""Tune faster-whisper on the Pi 5: cpu_threads sweep + small.en vs base.en."""
import os, time, wave
import numpy as np
from faster_whisper import WhisperModel

ROOT = "/home/rpi/voice-assistant"
SR = 16000

# Use a realistic 4-second-ish question clip (synthesized via piper earlier?
# No - keep self-contained: generate a tone+speech mix? Simplest: reuse TTS.)
import sys
sys.path.insert(0, f"{ROOT}/src")
os.chdir(f"{ROOT}/src")
from tts_engine import TextToSpeech

tts = TextToSpeech()
wav_path = tts.synthesize("Buddy. Why do astronauts float in space? What is gravity?")

def load_wav_16k(path):
    w = wave.open(path, "rb")
    sr = w.getframerate()
    data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if sr != SR:
        n_out = int(len(data) * SR / sr)
        x_old = np.linspace(0, 1, len(data), endpoint=False)
        x_new = np.linspace(0, 1, n_out, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.int16)
    return data

audio = load_wav_16k(wav_path).astype(np.float32) / 32768.0
n_sec = len(audio) / SR
print(f"test audio: {n_sec:.1f}s | target: 'buddy why do astronauts float in space what is gravity'\n")

def bench(model_name, cpu_threads, compute="int8", label=""):
    m = WhisperModel(model_name, device="cpu", compute_type=compute, cpu_threads=cpu_threads)
    # warmup
    list(m.transcribe(audio[: SR], language="en", beam_size=1, vad_filter=True)[0])
    t0 = time.time()
    segs, _ = m.transcribe(audio, language="en", beam_size=1,
                           vad_filter=True, vad_parameters={"min_silence_duration_ms": 300})
    text = " ".join(s.text.strip() for s in segs).strip()  # generator: work happens HERE
    dt = time.time() - t0
    print(f"{label:28s} threads={cpu_threads:<3d} {dt:5.2f}s  RTF={dt/n_sec:4.2f}  {text!r}")
    del m

for model_name, label in [("small.en", "whisper small.en"), ("base.en", "whisper base.en")]:
    print(f"=== {model_name} ===")
    for t in [1, 2, 4, 8]:
        bench(model_name, t, label=label)
    print()