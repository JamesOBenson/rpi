#!/usr/bin/env python3
"""Benchmark Vosk small vs large on the Pi: real-time factor + accuracy."""
import time, json, wave, os
import numpy as np
from vosk import Model, KaldiRecognizer
from tts_engine import TextToSpeech

ROOT = "/home/rpi/voice-assistant"

# 1. Make test audio with the same TTS voice the assistant uses
tts = TextToSpeech()
wav_path = tts.synthesize("Buddy. Why is the sky blue?")
print(f"test audio: {wav_path}")

def load_wav_16k(path):
    w = wave.open(path, "rb")
    sr = w.getframerate()
    data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if sr != 16000:  # linear resample
        n_out = int(len(data) * 16000 / sr)
        x_old = np.linspace(0, 1, len(data), endpoint=False)
        x_new = np.linspace(0, 1, n_out, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.int16)
    return data

audio = load_wav_16k(wav_path)
n_sec = len(audio) / 16000
print(f"audio length: {n_sec:.1f}s")
chunk = 1600  # 0.1s chunks, same as the live pipeline

results = {}
for name, path in [("small", f"{ROOT}/models/vosk-model-small-en-us-0.15"),
                   ("large", f"{ROOT}/models/vosk-model-en-us-0.22")]:
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull, 2)
    try:
        model = Model(path)
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)
    rec = KaldiRecognizer(model, 16000)
    t0 = time.time()
    for i in range(0, len(audio), chunk):
        rec.AcceptWaveform(audio[i:i + chunk].tobytes())
    text = json.loads(rec.FinalResult()).get("text", "")
    dt = time.time() - t0
    rtf = dt / n_sec
    results[name] = text
    print(f"[{name:5s}] RTF={rtf:.2f}  ({dt:.2f}s to process {n_sec:.1f}s audio)  -> {text!r}")
    del model

print()
print("SMALL:", results["small"])
print("LARGE:", results["large"])