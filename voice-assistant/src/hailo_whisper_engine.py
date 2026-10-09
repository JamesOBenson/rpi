#!/usr/bin/env python3
"""
Hailo Whisper STT Engine
========================
Whisper base (multilingual, English-forced) running on the Hailo-8L AI chip.

Uses Hailo's precompiled model-zoo HEFs (compiled by Hailo, v2.19.0 toolchain):
  - base-whisper-encoder-5s_h8l.hef
      5s mel window (1, 500, 80) -> context (1, 250, 512)      ~24 ms
  - base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef
      fixed 24-position greedy decode, ~4 ms per step.
      The H8L decoder HEF was compiled WITHOUT the token embedding ops, so
      the embedding lookup runs on the host using two .npy weight assets:
        token_embedding_weight_base.npy  (51865 x 512)
        onnx_add_input_base.npy          (24 x 512, per-position bias)

Interface matches WhisperSTT (faster-whisper): transcribe(audio) -> str.
CPU fallback lives in main.py: if this engine cannot be constructed
(no chip, missing files, driver error) the service falls back to the
full-CPU WhisperSTT automatically.

Mel math replicates Hailo's reference audio_utils.py (torch.stft semantics,
periodic Hann, reflect center padding, log10 with max-8 clamp, (x+4)/4) in
pure numpy, verified against the torch implementation to cosine 0.99998.
"""

import os
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 16000

WINDOW_SAMPLES = 5 * SAMPLE_RATE  # 80000 samples per 5s encoder window
N_FRAMES = 500  # mel frames per window (5s @ 10 fps)
DEC_SEQ = 24  # fixed decoder sequence length
N_FFT = 400
HOP = 160

# Whisper forced decoder prefix (multilingual vocab):
# <|startoftranscript|> <|en|> <|transcribe|> <|notimestamps|>
FORCED_IDS = [50258, 50259, 50359, 50363]

# Repetition penalty (matches Hailo's reference pipeline)
PENALTY = 1.5
PENALTY_WINDOW = 8
PUNCT_TOKENS = {11, 13}

DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "hailo-whisper"
MEL_FILTERS_PATH = PROJECT_ROOT / "data" / "hailo_whisper" / "mel_filters.npz"

_HAILO_DIST_PACKAGES = "/usr/lib/python3/dist-packages"


def _import_hailo_platform():
    """Import hailo_platform (system package) into a venv if needed."""
    try:
        import hailo_platform  # noqa: F401

        return
    except ImportError:
        if os.path.isdir(_HAILO_DIST_PACKAGES) and _HAILO_DIST_PACKAGES not in sys.path:
            sys.path.insert(0, _HAILO_DIST_PACKAGES)
            import hailo_platform  # noqa: F401
        else:
            raise


class HailoWhisperSTT:
    """Whisper base on Hailo-8L. transcribe(audio: f32 mono 16k) -> str."""

    def __init__(self, model_dir: str = None):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.enc_path = self.model_dir / "base-whisper-encoder-5s_h8l.hef"
        self.dec_path = (
            self.model_dir / "base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"
        )

        if not os.path.exists("/dev/hailo0"):
            raise RuntimeError("Hailo device not present (/dev/hailo0 missing)")
        required = [
            self.enc_path,
            self.dec_path,
            self.model_dir / "token_embedding_weight_base.npy",
            self.model_dir / "onnx_add_input_base.npy",
            MEL_FILTERS_PATH,
        ]
        missing = [str(p) for p in required if not Path(p).exists()]
        if missing:
            raise RuntimeError(f"missing Hailo whisper assets: {missing}")

        _import_hailo_platform()
        from hailo_platform import (
            HEF,
            VDevice,
            HailoSchedulingAlgorithm,
            FormatType,
        )

        t0 = time.time()
        print("Loading Hailo Whisper STT (base, Hailo-8L)...")

        # --- Host-side weight assets ---
        self.token_emb = np.load(
            self.model_dir / "token_embedding_weight_base.npy"
        ).astype(np.float32)
        self.add_input = np.load(self.model_dir / "onnx_add_input_base.npy").astype(
            np.float32
        )
        with np.load(MEL_FILTERS_PATH) as f:
            self.mel_filters = f["mel_80"].astype(np.float32)
        # periodic Hann (torch.hann_window default)
        self.window = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(
            np.float32
        )

        # --- Tokenizer (local vendored copy first, then HF cache) ---
        from transformers import AutoTokenizer

        tok_dir = self.model_dir / "tokenizer"
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(tok_dir) if tok_dir.exists() else "openai/whisper-base"
        )
        self.eos_id = self.tokenizer.eos_token_id

        # --- Hailo device + models ---
        self._HEF = HEF
        self._FormatType = FormatType
        params = VDevice.create_params()
        params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
        params.group_id = "SHARED"
        self._vdevice = VDevice(params)

        self.enc_name = HEF(str(self.enc_path)).get_network_group_names()[0]
        dec_meta = HEF(str(self.dec_path))
        self.dec_name = dec_meta.get_network_group_names()[0]
        self.sorted_dec_outputs = dec_meta.get_sorted_output_names()
        self.useful_outputs = [n for n in self.sorted_dec_outputs if "conv" in n]

        self.enc_model = self._vdevice.create_infer_model(str(self.enc_path))
        self.dec_model = self._vdevice.create_infer_model(str(self.dec_path))
        self.enc_model.input().set_format_type(FormatType.FLOAT32)
        self.enc_model.output().set_format_type(FormatType.FLOAT32)
        self.dec_model.input(f"{self.dec_name}/input_layer1").set_format_type(
            FormatType.FLOAT32
        )
        self.dec_model.input(f"{self.dec_name}/input_layer2").set_format_type(
            FormatType.FLOAT32
        )
        for name in self.sorted_dec_outputs:
            self.dec_model.output(name).set_format_type(FormatType.FLOAT32)

        # Keep the configure contexts alive for the object's lifetime
        # (mirrors the reference `with model.configure() as cfg:` usage).
        self._enc_cfg = self.enc_model.configure()
        self._enc_cfg.__enter__()
        self._dec_cfg = self.dec_model.configure()
        self._dec_cfg.__enter__()
        self.enc_bindings = self._enc_cfg.create_bindings()
        self.dec_bindings = self._dec_cfg.create_bindings()

        # --- Preallocate buffers from live vstream shapes ---
        self._enc_in = np.zeros(self.enc_model.input().shape, dtype=np.float32)
        self._enc_out = np.zeros(self.enc_model.output().shape, dtype=np.float32)
        self._dec_in2 = np.zeros(
            self.dec_model.input(f"{self.dec_name}/input_layer2").shape,
            dtype=np.float32,
        )
        self._dec_outs = {
            name: np.zeros(self.dec_model.output(name).shape, dtype=np.float32)
            for name in self.sorted_dec_outputs
        }

        self.timeout_ms = 60_000
        print(f"✓ Hailo Whisper STT ready in {time.time() - t0:.1f}s")

    # ------------------------------------------------------------------ mel
    def _mel_window(self, chunk: np.ndarray) -> np.ndarray:
        """80000 samples -> (500, 80) mel (time-major, for the HEF input)."""
        x = np.pad(chunk, N_FFT // 2, mode="reflect")
        idx = np.arange(N_FFT)[None, :] + HOP * np.arange(N_FRAMES)[:, None]
        frames = x[idx] * self.window  # (500, 400)
        mag = (np.abs(np.fft.rfft(frames, N_FFT, axis=1)) ** 2).T  # (201, 500)
        log = np.log10(np.clip(self.mel_filters @ mag, 1e-10, None))  # (80, 500)
        log = np.maximum(log, log.max() - 8.0)
        return ((log + 4.0) / 4.0).T.astype(np.float32)  # (500, 80)

    def _make_mels(self, audio: np.ndarray):
        n_chunks = max(1, int(np.ceil(len(audio) / WINDOW_SAMPLES)))
        padded = np.zeros(n_chunks * WINDOW_SAMPLES, dtype=np.float32)
        padded[: len(audio)] = audio
        return [
            self._mel_window(padded[i * WINDOW_SAMPLES : (i + 1) * WINDOW_SAMPLES])
            for i in range(n_chunks)
        ]

    # --------------------------------------------------------------- decode
    def _decode(self, encoded: np.ndarray) -> str:
        """Greedy 24-position decode of one encoder context."""
        ids = np.zeros(DEC_SEQ, dtype=np.int64)
        ids[: len(FORCED_IDS)] = FORCED_IDS
        generated = []

        for i in range(len(FORCED_IDS) - 1, DEC_SEQ - 1):
            # Host-side token embedding: gather + per-position bias
            emb = (
                (self.token_emb[ids] + self.add_input)
                .reshape(DEC_SEQ, 1, 512)
                .astype(np.float32)
            )

            self.dec_bindings.input(f"{self.dec_name}/input_layer1").set_buffer(encoded)
            self.dec_bindings.input(f"{self.dec_name}/input_layer2").set_buffer(emb)
            for name in self.sorted_dec_outputs:
                self.dec_bindings.output(name).set_buffer(self._dec_outs[name])
            self._dec_cfg.run([self.dec_bindings], self.timeout_ms)

            # Reassemble the split lm_head outputs -> (1, 24, 51865)
            logits = np.concatenate(
                [self._dec_outs[name][0, i] for name in self.useful_outputs], axis=0
            ).copy()
            for tok in set(generated[-PENALTY_WINDOW:]):
                if tok not in PUNCT_TOKENS:
                    logits[tok] /= PENALTY

            tok = int(np.argmax(logits))
            generated.append(tok)
            if tok == self.eos_id:
                break
            ids[i + 1] = tok

        return self.tokenizer.decode(generated, skip_special_tokens=True)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe 16kHz mono float32 audio (-1..1). Returns text."""
        if audio is None or len(audio) < SAMPLE_RATE // 10:
            return ""
        t0 = time.time()
        mels = self._make_mels(np.asarray(audio, dtype=np.float32))
        texts = []
        for mel in mels:
            self.enc_bindings.input().set_buffer(
                np.ascontiguousarray(mel[np.newaxis, ...])
            )
            self.enc_bindings.output().set_buffer(self._enc_out)
            self._enc_cfg.run([self.enc_bindings], self.timeout_ms)
            text = self._decode(self._enc_out)
            if text and text.strip():
                texts.append(text.strip())
        result = " ".join(texts).strip()
        n_sec = len(audio) / SAMPLE_RATE
        print(
            f"  ⏱ hailo-whisper: {n_sec:.1f}s audio -> {time.time() - t0:.2f}s -> {result!r}"
        )
        return result

    def close(self):
        for cfg in (self._dec_cfg, self._enc_cfg):
            try:
                cfg.__exit__(None, None, None)
            except Exception:
                pass
        try:
            self._vdevice.close()
        except Exception:
            pass
