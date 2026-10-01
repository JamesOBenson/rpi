#!/usr/bin/env python3
"""Test vosk SetWords context biasing on REAL missed-wake audio."""
import glob, json, os
import numpy as np
from vosk import Model, KaldiRecognizer

ROOT = "/home/rpi/voice-assistant"
SR = 16000
wavs = sorted(glob.glob(f"{ROOT}/logs/audio/idle-*.wav"))
if not wavs:
    print("no idle wavs"); raise SystemExit(1)

def load_vosk(p):
    dn = os.open(os.devnull, os.O_WRONLY); sv = os.dup(2); os.dup2(dn, 2)
    try:
        return Model(p)
    finally:
        os.dup2(sv, 2); os.close(sv); os.close(dn)

m = load_vosk(f"{ROOT}/models/vosk-model-en-us-0.22")
print(f"vosk SetWords available: {hasattr(KaldiRecognizer, 'SetWords')}\n")

for w in wavs:
    import wave
    wh = wave.open(w, "rb")
    a16 = np.frombuffer(wh.readframes(wh.getnframes()), dtype=np.int16)
    line = f"{os.path.basename(w)}  {len(a16)/SR:4.1f}s"
    for label, words in [("plain", None), ("biased", ["buddy"])]:
        rec = KaldiRecognizer(m, SR)
        if words and hasattr(rec, "SetWords"):
            rec.SetWords(words)
        for i in range(0, len(a16), 1600):
            rec.AcceptWaveform(a16[i:i+1600].tobytes())
        txt = json.loads(rec.FinalResult()).get("text", "")
        hit = "HIT " if "buddy" in txt else "    "
        line += f"   {label:6s} {hit} {txt!r}"
    print(line)