#!/usr/bin/env python3
"""
Mic noise suppression (RNNoise)
===============================
Wraps the sounddevice input stream with Xiph's RNNoise neural noise
suppressor (same filter class WebRTC/Chrome use in calls).

- Kills stationary noise: fans, AC, mains hum, hiss.
- Dulls non-stationary noise and background voices so the person in
  front of the mic dominates the capture. It cannot make other people
  disappear - wake-word checking remains the gate for that.

RNNoise works in 480-sample frames at 48 kHz. The mic stream is opened
at 48 kHz; this wrapper denoises and resamples to 16 kHz (spectral
decimation with built-in anti-aliasing lowpass, no scipy) before
Vosk/Whisper see it.
"""

import ctypes
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
_LIB_PATH = PROJECT_ROOT / "lib" / "librnnoise.so"
_FRAME = 480      # RNNoise frame size at 48 kHz
_SR48, _SR16 = 48000, 16000


def _load_lib():
    lib = ctypes.CDLL(str(_LIB_PATH))
    lib.rnnoise_create.restype = ctypes.c_void_p
    lib.rnnoise_create.argtypes = [ctypes.c_void_p]
    lib.rnnoise_process_frame.restype = ctypes.c_int
    lib.rnnoise_process_frame.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
    ]
    lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
    return lib


def _new_state(lib):
    # Pretrained model embedded in the .so (v0.1.1 symbol)
    model = ctypes.c_char.in_dll(lib, "rnnoise_model_orig")
    state = lib.rnnoise_create(ctypes.byref(model))
    if not state:
        raise RuntimeError("rnnoise_create failed")
    return state


def _decimate3(x48):
    """48 kHz -> 16 kHz: keep the 0-8 kHz spectrum, IFFT at 1/3 length.
    Exact for len(x48) % 6 == 0 (all chunks are: n16 is a multiple
    of 160 samples = 10 RNNoise frames).
    The /3 is required: rfft accumulates n samples but irfft only
    divides by n/6, so the output is 3x too loud without it - which
    lifted the noise floor above the AGC gate and sox's 2% trigger
    and broke question endpointing."""
    n = len(x48) // 6 * 6
    spec = np.fft.rfft(x48[:n])
    return (np.fft.irfft(spec[: n // 6 + 1], n=n // 3) / 3).astype(
        np.float32)


class NoiseSuppressedStream:
    """Drop-in wrapper around a 48 kHz sounddevice InputStream.

    read(n16) -> (n16 x 1 float32 at 16 kHz, overflow) - same shape as
    sd.InputStream.read(), so wait_for_question()/watch_for_stop()
    work unchanged.
    """

    def __init__(self, base_stream):
        self._lib = _load_lib()
        self._state = _new_state(self._lib)
        self._base = base_stream

    def read(self, n16):
        n48 = n16 * 3
        data, overflow = self._base.read(n48)
        x = data.flatten().astype(np.float32)
        if len(x) % _FRAME:  # defensive; real chunks always align
            x = np.concatenate([x, np.zeros(_FRAME - len(x) % _FRAME,
                                            dtype=np.float32)])
        y = np.empty_like(x)
        for i in range(0, len(x), _FRAME):
            self._lib.rnnoise_process_frame(
                self._state,
                y[i:i + _FRAME].ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                x[i:i + _FRAME].ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        out = _decimate3(y)
        return out.astype(np.float32).reshape(-1, 1), overflow

    def stop(self):
        self._base.stop()

    def close(self):
        self._base.close()
        if self._state:
            self._lib.rnnoise_destroy(self._state)
            self._state = None


def denoise_16k(audio16: np.ndarray) -> np.ndarray:
    """Offline 16 kHz float32 -> denoised 16 kHz float32.

    Used for debugging/verification on saved WAVs (the live path goes
    through NoiseSuppressedStream). Upsample 3x, RNNoise, decimate back.
    """
    lib = _load_lib()
    state = _new_state(lib)
    try:
        # n must be a multiple of 160 (= 480/3) so that 3n is a whole
        # number of RNNoise frames - otherwise the last frame call reads
        # past the end of the buffer.
        n = (len(audio16) // 160) * 160
        x = np.asarray(audio16[:n], dtype=np.float32)
        X = np.fft.rfft(x)
        Xz = np.zeros(3 * n // 2 + 1, dtype=complex)
        Xz[: len(X)] = X
        x48 = np.fft.irfft(Xz, n=3 * n).astype(np.float32)
        y = np.empty_like(x48)
        if len(x48) % _FRAME:
            pad = _FRAME - len(x48) % _FRAME
            x48 = np.concatenate([x48, np.zeros(pad, np.float32)])
            y = np.empty_like(x48)
        for i in range(0, len(x48), _FRAME):
            lib.rnnoise_process_frame(
                state,
                y[i:i + _FRAME].ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                x48[i:i + _FRAME].ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        return _decimate3(y).astype(np.float32)
    finally:
        lib.rnnoise_destroy(state)