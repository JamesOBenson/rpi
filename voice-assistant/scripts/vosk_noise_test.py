#!/usr/bin/env python3
"""Vosk small vs large under noise - the real-world accuracy test."""
import json, os, wave
import numpy as np
from vosk import Model, KaldiRecognizer
from tts_engine import TextToSpeech

ROOT = "/home/rpi/voice-assistant"
rng = np.random.default_rng(42)

tts = TextToSpeech()
wav_path = tts.synthesize("Buddy. What is a black hole?")

def load_wav_16k(path):
    w = wave.open(path, "rb")
    sr = w.getframerate()
    data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if sr != 16000:
        n_out = int(len(data) * 16000 / sr)
        x_old = np.linspace(0, 1, len(data), endpoint=False)
        x_new = np.linspace(0, 1, n_out, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.int16)
    return data

audio = load_wav_16k(wav_path)

def add_noise(a, snr_db):
    """Mix white noise at the given SNR (dB)."""
    power = np.mean(a.astype(np.float64) ** 2)
    noise_power = power / (10 ** (snr_db / 10))
    noise = rng.standard_normal(len(a)).astype(np.float32)
    noise *= np.sqrt(noise_power / (np.mean(noise.astype(np.float64) ** 2) + 1e-9))
    return np.clip(a + noise, -32768, 32767).astype(np.int16)

def lowpass(a, cutoff=1200):
    """Telephone-quality low-pass (kills high frequencies)."""
    # simple one-pole lowpass cascade (pure numpy)
    rc = 1 / (2 * np.pi * cutoff)
    dt = 1 / 16000
    alpha = dt / (rc + dt)
    out = np.empty_like(a, dtype=np.float32)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = out[i - 1] + alpha * (a[i] - out[i - 1])
    return out.astype(np.int16)

conditions = [
    ("clean",            audio),
    ("noise @ 10dB SNR", add_noise(audio, 10)),
    ("noise @ 5dB SNR",  add_noise(audio, 5)),
    ("telephone (low-pass)", lowpass(audio)),
]

models = {}
for name, path in [("small", f"{ROOT}/models/vosk-model-small-en-us-0.15"),
                   ("large", f"{ROOT}/models/vosk-model-en-us-0.22")]:
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull, 2)
    try:
        models[name] = Model(path)
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)

chunk = 1600
print(f"{'condition':22s} | {'SMALL':30s} | LARGE")
print("-" * 80)
for label, a in conditions:
    row = {}
    for name, model in models.items():
        rec = KaldiRecognizer(model, 16000)
        for i in range(0, len(a), chunk):
            rec.AcceptWaveform(a[i:i + chunk].tobytes())
        row[name] = json.loads(rec.FinalResult()).get("text", "")
    print(f"{label:22s} | {row['small']:30s} | {row['large']}")
print()
print("target: 'buddy what is a black hole'")