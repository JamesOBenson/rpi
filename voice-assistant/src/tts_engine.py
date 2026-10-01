#!/usr/bin/env python3
"""
Text-to-Speech Engine
=====================
Uses Piper TTS for natural-sounding offline speech.

Fast, low-latency, and completely offline.
"""

import subprocess
import tempfile
import wave
import shutil
import numpy as np
import sounddevice as sd
from pathlib import Path
from typing import Optional

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent


class TextToSpeech:
    """Offline TTS using Piper."""

    def __init__(
        self,
        voice_model: str = None,
        speed: float = 1.0
    ):
        """
        Initialize TTS engine.

        Args:
            voice_model: Path to Piper .onnx voice model
            speed: Speech speed multiplier (1.0 = normal)
        """
        if voice_model is None:
            voice_model = str(PROJECT_ROOT / "models" / "en_US-lessac-medium.onnx")
        self.model_path = Path(voice_model)
        self.speed = speed
        self.volume = 1.0
        self._current_process = None
        self._playing = False

        # Find Piper binary
        self.piper_binary = shutil.which("piper") or shutil.which("piper-tts")

        if not self.piper_binary:
            print("⚠️  Piper not found - install with: pip install piper-tts")
            self.available = False
        elif not self.model_path.exists():
            print(f"⚠️  Voice model not found: {self.model_path}")
            print("   Download from: https://huggingface.co/rhasspy/piper-voices")
            self.available = False
        else:
            print(f"✓ TTS ready (voice: {self.model_path.name})")
            self.available = True

    def speak(self, text: str, on_interrupt: Optional[callable] = None):
        """
        Speak text aloud (synthesize + play, blocking).

        Args:
            text: Text to speak
            on_interrupt: Optional callback checked during playback
        """
        if not text or not text.strip():
            return

        if not self.available:
            print(f"🔊 [no TTS] {text}")
            return

        print(f"🔊 Speaking...")
        path = self.synthesize(text)
        if path is None:
            return
        try:
            self._play_audio(path, on_interrupt)
        finally:
            Path(path).unlink(missing_ok=True)

    def synthesize(self, text: str) -> Optional[str]:
        """
        Synthesize text to a WAV file using Piper.

        Returns:
            Path to the .wav file, or None on failure.
        """
        if not self.available or not text or not text.strip():
            return None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name

            result = subprocess.run(
                [self.piper_binary, "-m", str(self.model_path), "-f", output_path],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=60
            )

            if result.returncode != 0 or not Path(output_path).exists():
                Path(output_path).unlink(missing_ok=True)
                print(f"❌ TTS synthesis failed: {result.stderr.decode()[:200]}")
                return None
            return output_path

        except subprocess.TimeoutExpired:
            print("❌ TTS timed out")
            return None
        except Exception as e:
            print(f"❌ TTS error: {e}")
            return None

    def play_wav(self, path: str, stop_event=None):
        """Play a WAV file, stopping early if stop_event is set."""
        on_interrupt = stop_event.is_set if stop_event is not None else None
        self._play_audio(path, on_interrupt)

    def _play_audio(self, audio_path: str, on_interrupt: Optional[callable] = None):
        """Play a WAV file, checking for interrupts each tick."""
        import time
        import threading
        try:
            with wave.open(audio_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()

            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            audio *= self.volume
            if channels > 1:
                audio = audio.reshape(-1, channels)

            self._playing = True
            done = threading.Event()

            def _blockplay():
                try:
                    sd.play(audio, sample_rate, blocking=True)
                except Exception:
                    pass
                finally:
                    done.set()

            t = threading.Thread(target=_blockplay, daemon=True)
            t.start()

            # Poll while playback runs; stop early if interrupted
            while not done.is_set():
                if on_interrupt and on_interrupt():
                    sd.stop()
                    break
                time.sleep(0.05)

            t.join(timeout=2)

        except Exception as e:
            print(f"⚠ Playback error: {e}")
            try:
                sd.stop()
            except Exception:
                pass
        finally:
            self._playing = False

    def stop(self):
        """Stop current playback immediately."""
        if self._playing:
            sd.stop()
            self._playing = False

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)."""
        if 0.0 <= volume <= 1.0:
            self.volume = volume

    def set_speed(self, speed: float):
        """Set speech speed (0.5 to 2.0)."""
        if 0.5 <= speed <= 2.0:
            self.speed = speed


# Test
if __name__ == "__main__":
    print("TTS Test")
    tts = TextToSpeech()
    if tts.available:
        tts.speak("Hello! I am STEM Buddy, your friendly science assistant.")
    else:
        print("TTS not available - check piper installation and voice model")