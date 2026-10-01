#!/usr/bin/env python3
"""
Whisper STT Engine
==================
High-accuracy batch transcription with faster-whisper (CTranslate2 backend).

Used in "hybrid" mode: the lightweight Vosk model watches the mic 24/7 for
the wake word, and only once "buddy" is heard does this model wake up and
transcribe the captured question. That's the classic always-on-voice-device
architecture (cheap keyword spotter + strong on-demand recognizer).

Why faster-whisper over openai-whisper: ~4-8x faster on CPU, int8 support,
clean aarch64 wheels.
"""

import time
from pathlib import Path
from typing import Optional

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 16000


class WhisperSTT:
    """Offline question transcription with faster-whisper."""

    def __init__(
        self,
        model_size: str = "small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
    ):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("✗ Install faster-whisper: pip install faster-whisper")
            raise

        self.model_size = model_size
        print(f"Loading Whisper model ({model_size}, {compute_type}, {cpu_threads} threads)...")
        t0 = time.time()
        # First run downloads the model from HuggingFace (~460MB for
        # small.en, ~140MB for base.en) into ~/.cache/huggingface -
        # offline after that.
        # NOTE: on the Pi 5 use 4 threads (the fast A76 cores). 8 threads
        # schedules onto the slow A55s and is ~2x slower (measured).
        self.model = WhisperModel(
            model_size, device=device, compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
        print(f"✓ Whisper STT ready in {time.time() - t0:.1f}s")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe 16kHz mono float32 audio (-1.0..1.0).

        Returns the transcript (may be empty for silence/garbage).
        """
        if audio is None or len(audio) < SAMPLE_RATE // 10:
            return ""
        t0 = time.time()
        segments, _info = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,  # greedy: ~2x faster than beam=5, negligible loss
            vad_filter=True,  # built-in Silero VAD trims silence
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        n_sec = len(audio) / SAMPLE_RATE
        print(f"  ⏱ whisper: {n_sec:.1f}s audio -> {time.time() - t0:.2f}s -> {text!r}")
        return text