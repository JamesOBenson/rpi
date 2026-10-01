#!/usr/bin/env python3
"""1) TTS warm-up check: first vs subsequent synthesis times.
2) whisper tiny.en accuracy on the real user captures."""
import os, sys, time, glob
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from tts_engine import TextToSpeech
from whisper_engine import WhisperSTT

print("=== TTS warm-up test ===")
tts = TextToSpeech()
t0 = time.time(); w1 = tts.synthesize("Hello there friend"); t1 = time.time() - t0
t0 = time.time(); w2 = tts.synthesize("The sky is blue because of the way sunlight scatters in the air."); t2 = time.time() - t0
t0 = time.time(); w3 = tts.synthesize("Want to know more?"); t3 = time.time() - t0
os.unlink(w1); os.unlink(w2); os.unlink(w3)
print(f"  synth #1 (cold):    {t1:.2f}s")
print(f"  synth #2 (warm):    {t2:.2f}s")
print(f"  synth #3 (warm):    {t3:.2f}s")

print("\n=== whisper tiny.en on real user captures ===")
tiny = WhisperSTT(model_size="tiny.en", cpu_threads=4)
base = WhisperSTT(model_size="base.en", cpu_threads=4)

import wave
for f in sorted(glob.glob(f"{ROOT}/logs/audio/q-*.wav")):
    w = wave.open(f, "rb")
    a16 = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    t0 = time.time(); a = tiny.transcribe(a16.astype(np.float32)/32768.0); t_tiny = time.time()-t0
    t0 = time.time(); b = base.transcribe(a16.astype(np.float32)/32768.0); t_base = time.time()-t0
    print(f"  {os.path.basename(f)} ({len(a16)/16000:.1f}s)")
    print(f"    tiny {t_tiny:4.2f}s: {a!r}")
    print(f"    base {t_base:4.2f}s: {b!r}")