"""
Post-NS signal chain for the 16 kHz mic stream: highpass -> AGC.

Ordering: RNNoise runs first (it needs 48k and does its own spectral
processing); this chain runs on the 16k output where filtering is
cheapest, then STT runs on the result.

HighPass - 2nd-order Butterworth biquad (RBJ cookbook, Q=0.707),
default 100 Hz. Cuts power hum (60 Hz), HVAC rumble and handling noise
below the vocal band. Runs through scipy lfilter (C speed).

AGC - RMS-targeted gain with a noise gate. While speech is present the
gain pulls the signal toward the target RMS (a kid's quiet question at
0.05 RMS becomes ~0.12 RMS); when the room is quiet the gain releases
back to 1.0 so the noise floor is never amplified. Max gain is capped.
"""
import numpy as np
from scipy.signal import butter, lfilter


class HighPass:
    """Second-order Butterworth highpass with persistent filter state.

    Coefficients come from scipy.signal.butter (prewarped, exact 3 dB
    point at fc) rather than hand-rolled cookbook math.
    """

    def __init__(self, sr: int = 16000, fc: float = 100.0):
        self.fc = fc
        b, a = butter(2, fc, fs=sr, btype="high")
        self.b = b.astype(np.float64)
        self.a = a.astype(np.float64)
        self.zi = np.zeros(2)

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self.zi = lfilter(self.b, self.a, x, zi=self.zi)
        return y.astype(np.float32)

    def reset(self):
        self.zi = np.zeros(2)


class AGC:
    """RMS-targeted gain, noise-gated, smoothed over ~100 ms chunks."""

    def __init__(self, target: float = 0.12, max_gain: float = 6.0,
                 noise_floor: float = 0.02, attack: float = 0.25,
                 release: float = 0.15):
        self.target = target
        self.max_gain = max_gain
        self.floor = noise_floor
        self.attack = attack
        self.release = release
        self.gain = 1.0

    def process(self, x: np.ndarray) -> np.ndarray:
        rms = float(np.sqrt(np.mean(np.square(x))))
        if rms > self.floor:
            desired = min(self.target / max(rms, 1e-6), self.max_gain)
            self.gain += (desired - self.gain) * self.attack
        else:
            self.gain += (1.0 - self.gain) * self.release
        return np.clip(x * self.gain, -1.0, 1.0).astype(np.float32)


class SignalChain:
    """Wraps any sounddevice-style stream: read() -> highpass -> AGC.

    Everything else (start/stop/close/flush) proxies to the wrapped
    stream, so it stays a drop-in replacement for self.stream.
    """

    def __init__(self, stream, hp: HighPass = None, agc: AGC = None):
        self.stream = stream
        self.hp = hp
        self.agc = agc

    def read(self, nframes):
        data, overflow = self.stream.read(nframes)
        x = data.flatten().astype(np.float32)
        if self.hp is not None:
            x = self.hp.process(x)
        if self.agc is not None:
            x = self.agc.process(x)
        return x.reshape(data.shape).astype(np.float32), overflow

    def __getattr__(self, name):
        return getattr(self.stream, name)