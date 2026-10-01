#!/usr/bin/env python3
"""Run one captured question WAV through all engines (wake-word reliability)."""
import json, os, sys, wave
import numpy as np
from vosk import Model, KaldiRecognizer
from faster_whisper import WhisperModel

ROOT = "/home/rpi/voice-assistant"
SR = 16000
wav = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/logs/audio/q-20261001-111333.wav"

w = wave.open(wav, "rb")
a16 = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
print(f"file: {os.path.basename(wav)}  {len(a16)/SR:.2f}s  "
      f"peak={np.abs(a16.astype(np.int32)).max()/32768:.3f}  "
      f"rms={np.abs(a16.astype(np.float32)).mean()/32768:.3f}\n")

def load_vosk(p):
    dn = os.open(os.devnull, os.O_WRONLY); sv = os.dup(2); os.dup2(dn, 2)
    try:
        return Model(p)
    finally:
        os.dup2(sv, 2); os.close(sv); os.close(dn)

engines = []
engines.append(("vosk SMALL (always-on)", load_vosk(f"{ROOT}/models/vosk-model-small-en-us-0.15")))
engines.append(("vosk LARGE", load_vosk(f"{ROOT}/models/vosk-model-en-us-0.22")))

def vosk(m):
    rec = KaldiRecognizer(m, SR)
    for i in range(0, len(a16), 1600):
        rec.AcceptWaveform(a16[i:i+1600].tobytes())
    return json.loads(rec.FinalResult()).get("text", "")

for name, m in engines:
    print(f"{name:22s} -> {vosk(m)!r}")

f32 = a16.astype(np.float32) / 32768.0
for ms in ["base.en", "small.en"]:
    wm = WhisperModel(ms, device="cpu", compute_type="int8", cpu_threads=4)
    segs, _ = wm.transcribe(f32, language="en", beam_size=1,
                            vad_filter=True, vad_parameters={"min_silence_duration_ms": 300})
    print(f"whisper {ms:8s}      -> {' '.join(s.text.strip() for s in segs).strip()!r}")