#!/usr/bin/env python3
"""Deciding A/B: base.en vs small.en vs vosk large under all conditions."""
import json, os, time, wave
import numpy as np
from vosk import Model, KaldiRecognizer
from faster_whisper import WhisperModel
from tts_engine import TextToSpeech

ROOT = "/home/rpi/voice-assistant"
SR = 16000
THREADS = 4  # A76-only on Pi 5 (8 threads hits the A55s and is 2x slower)
rng = np.random.default_rng(42)

tts = TextToSpeech()

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

def add_noise(a, snr_db):
    power = np.mean(a.astype(np.float64) ** 2)
    noise_power = power / (10 ** (snr_db / 10))
    noise = rng.standard_normal(len(a)).astype(np.float32)
    noise *= np.sqrt(noise_power / (np.mean(noise.astype(np.float64) ** 2) + 1e-9))
    return np.clip(a + noise, -32768, 32767).astype(np.int16)

def lowpass(a, cutoff=1200):
    rc = 1 / (2 * np.pi * cutoff)
    dt = 1 / SR
    alpha = dt / (rc + dt)
    out = np.empty_like(a, dtype=np.float32)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = out[i - 1] + alpha * (a[i] - out[i - 1])
    return out.astype(np.int16)

def load_vosk(path):
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull, 2)
    try:
        return Model(path)
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)

print("loading engines...", flush=True)
vosk_large = load_vosk(f"{ROOT}/models/vosk-model-en-us-0.22")
whisper_base = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=THREADS)
whisper_small = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=THREADS)

def vosk_run(model, a16):
    rec = KaldiRecognizer(model, SR)
    chunk = 1600
    t0 = time.time()
    for i in range(0, len(a16), chunk):
        rec.AcceptWaveform(a16[i:i + chunk].tobytes())
    text = json.loads(rec.FinalResult()).get("text", "")
    return text, time.time() - t0

def whisper_run(model, a16):
    f32 = a16.astype(np.float32) / 32768.0
    t0 = time.time()
    segs, _ = model.transcribe(f32, language="en", beam_size=1,
                               vad_filter=True, vad_parameters={"min_silence_duration_ms": 300})
    text = " ".join(s.text.strip() for s in segs).strip()  # generator: work here
    return text, time.time() - t0

# Two different questions for robustness
questions = [
    "Buddy. What is a black hole?",
    "Buddy. How much does a fax farm cost?",
]

for q in questions:
    wav_path = tts.synthesize(q)
    audio = load_wav_16k(wav_path)
    print(f"\n########## {q!r}  ({len(audio)/SR:.1f}s) ##########")
    conditions = [
        ("clean",              audio),
        ("noise @ 10dB",       add_noise(audio, 10)),
        ("noise @ 5dB",        add_noise(audio, 5)),
        ("telephone (lowpass)", lowpass(audio)),
    ]
    for label, a in conditions:
        print(f"--- {label} ---")
        for name, fn in [("vosk large",  lambda: vosk_run(vosk_large, a)),
                         ("whisper base", lambda: whisper_run(whisper_base, a)),
                         ("whisper small", lambda: whisper_run(whisper_small, a))]:
            text, dt = fn()
            print(f"  {name:13s} {dt:5.2f}s  {text!r}")
        print()