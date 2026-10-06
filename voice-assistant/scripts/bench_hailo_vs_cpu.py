#!/usr/bin/env python3
"""Hailo-8L Whisper vs CPU Whisper (small.en) on real field captures.

Run with the stem-buddy service STOPPED so nothing else competes for the
A76 cores:  ./buddy.sh stop && venv/bin/python scripts/bench_hailo_vs_cpu.py
"""
import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hailo_whisper_engine import HailoWhisperSTT  # noqa: E402
from whisper_engine import WhisperSTT  # noqa: E402

SR = 16000
PROMPT = ("STEM and cybersecurity questions for kids. Topics: passwords, "
          "phishing, scams, black holes, sky, rockets, electricity, atoms, "
          "viruses, hacking.")  # same bias as production config


def load_wav(path):
    w = wave.open(str(path))
    a = np.frombuffer(w.readframes(w.getnframes()),
                      dtype=np.int16).astype(np.float32)
    return a / 32768.0


def main():
    # Real field audio: TV/background (idle-*) + actual user questions (q-*,
    # non-raw = post speaker-filter, i.e. what production feeds the engines).
    idle = sorted((ROOT / "logs/audio").glob("idle-*.wav"))[-6:]
    q = sorted(p for p in (ROOT / "logs/audio").glob("q-*.wav")
               if "-raw" not in p.name)[-4:]
    files = idle + q
    print(f"Benchmarking {len(files)} real captures "
          f"({len(idle)} TV, {len(q)} user)")

    print("Loading Hailo Whisper (base, Hailo-8L)...", flush=True)
    hailo = HailoWhisperSTT()
    print("Loading CPU Whisper (small.en, int8, 4 threads)...", flush=True)
    cpu = WhisperSTT(model_size="small.en", cpu_threads=4,
                     initial_prompt=PROMPT)

    # Warm both engines (first decode pays graph/model warmup).
    silence = np.zeros(SR // 2, dtype=np.float32)
    hailo.transcribe(silence)
    cpu.transcribe(silence)

    print(f"\n{'capture':42s} {'dur':>5s} {'hailo':>8s} {'cpu':>8s} {'x':>6s}")
    rows = []
    for p in files:
        a = load_wav(p)
        dur = len(a) / SR
        t0 = time.time(); h = hailo.transcribe(a); dt_h = time.time() - t0
        t0 = time.time(); c = cpu.transcribe(a); dt_c = time.time() - t0
        rows.append((dt_h, dt_c))
        print(f"{p.name:42s} {dur:5.1f} {dt_h:7.2f}s {dt_c:7.2f}s "
              f"{dt_c / dt_h:5.1f}x")
        print(f"    hailo: {h!r}")
        print(f"    cpu:   {c!r}")

    hs = [r[0] for r in rows]
    cs = [r[1] for r in rows]
    print(f"\n=== Summary (n={len(rows)}) ===")
    print(f"Hailo: median {statistics.median(hs):.2f}s, "
          f"mean {statistics.mean(hs):.2f}s, max {max(hs):.2f}s")
    print(f"CPU:   median {statistics.median(cs):.2f}s, "
          f"mean {statistics.mean(cs):.2f}s, max {max(cs):.2f}s")
    print(f"Speedup (cpu/hailo): "
          f"median {statistics.median([r[1] / r[0] for r in rows]):.1f}x")
    hailo.close()


if __name__ == "__main__":
    main()