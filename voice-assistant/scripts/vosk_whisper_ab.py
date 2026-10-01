#!/usr/bin/env python3
"""A/B: Vosk small vs Vosk large vs Whisper small.en (int8).

Same test audio, four conditions (clean / 10dB / 5dB / low-pass).
Reports transcript + decode time for each engine.
Service must be stopped first (holds the mic + CPU).
"""
import json, os, time, wave
import numpy as np
from vosk import Model, KaldiRecognizer
from faster_whisper import WhisperModel
from tts_engine import TextToSpeech

ROOT = "/home/rpi/voice-assistant"
SR = 16000
rng = np.random.default_rng(42)

# --- test audio -------------------------------------------------------------
tts = TextToSpeech()
wav_path = tts.synthesize("Buddy. What is a black hole?")

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

audio = load_wav_16k(wav_path)

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

conditions = [
    ("clean",              audio),
    ("noise @ 10dB",       add_noise(audio, 10)),
    ("noise @ 5dB",        add_noise(audio, 5)),
    ("telephone (lowpass)", lowpass(audio)),
]

# --- engines ----------------------------------------------------------------
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
vosk_small = load_vosk(f"{ROOT}/models/vosk-model-small-en-us-0.15")
vosk_large = load_vosk(f"{ROOT}/models/vosk-model-en-us-0.22")
whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
n_sec = len(audio) / SR
print(f"engines ready | test audio: {n_sec:.1f}s\n", flush=True)

def vosk_run(model, a16):
    rec = KaldiRecognizer(model, SR)
    chunk = 1600
    t0 = time.time()
    for i in range(0, len(a16), chunk):
        rec.AcceptWaveform(a16[i:i + chunk].tobytes())
    text = json.loads(rec.FinalResult()).get("text", "")
    return text, time.time() - t0

def whisper_run(a16):
    f32 = a16.astype(np.float32) / 32768.0
    t0 = time.time()
    segs, _ = whisper.transcribe(
        f32, language="en", beam_size=1,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 300})
    text = " ".join(s.text.strip() for s in segs).strip()
    return text, time.time() - t0

# --- run --------------------------------------------------------------------
print(f"target: 'buddy what is a black hole'\n")
for label, a in conditions:
    print(f"--- {label} ---")
    for name, fn in [("vosk small",  lambda: vosk_run(vosk_small, a)),
                     ("vosk large",  lambda: vosk_run(vosk_large, a)),
                     ("whisper s.en", lambda: whisper_run(a))]:
        text, dt = fn()
        print(f"  {name:12s} {dt:5.2f}s  {text!r}")
    print()