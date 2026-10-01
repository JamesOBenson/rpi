#!/usr/bin/env python3
"""
Speech-to-Text Engine
=====================
Offline speech recognition using Vosk.
Fast, accurate, and works completely offline.
"""

import json
import os
import re
import time
import numpy as np
import sounddevice as sd
from pathlib import Path
from typing import Optional
from vosk import Model, KaldiRecognizer

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent

# Available Vosk models (config: stt.model_size)
#   small = ~68MB, fastest   |   large = ~1.3GB, much more accurate
# Both stream in real time on a Raspberry Pi 5.
VOSK_MODELS = {
    "small": "vosk-model-small-en-us-0.15",
    "large": "vosk-model-en-us-0.22",
}


class SpeechToText:
    """Offline speech recognition with Vosk."""
    
    def __init__(
        self,
        model_name: str = "vosk-model-small-en-us-0.15",
        sample_rate: int = 16000
    ):
        self.model_name = model_name
        self.sample_rate = sample_rate
        self.recognizer = None
        self.model_path = PROJECT_ROOT / "models" / model_name
        
        self._init_vosk()
        
    def _init_vosk(self):
        """Initialize Vosk recognizer."""
        try:
            from vosk import Model, KaldiRecognizer
            
            # Check if model exists
            if not self.model_path.exists():
                self._download_model()
                
            # Load model (suppress noisy Kaldi C++ logs)
            import os
            devnull = os.open(os.devnull, os.O_WRONLY)
            saved = os.dup(2)
            os.dup2(devnull, 2)
            try:
                model = Model(str(self.model_path))
            finally:
                os.dup2(saved, 2)
                os.close(saved)
                os.close(devnull)
            self.recognizer = KaldiRecognizer(model, self.sample_rate)
            self.recognizer.SetWords(True)
            print(f"✓ Vosk STT initialized")
            
        except ImportError:
            print("✗ Install Vosk: pip install vosk")
            raise
        except Exception as e:
            print(f"✗ Vosk error: {e}")
            raise
            
    def _download_model(self):
        """Download Vosk model."""
        print(f"⬇️  Downloading model: {self.model_name}")
        print(f"   From: https://alphacephei.com/vosk/models/")
        print(f"   To: {self.model_path}")
        
        # For RPi, download manually:
        # wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
        # unzip vosk-model-small-en-us-0.15.zip -d models/
        
        raise FileNotFoundError(
            f"Model not found. Download from:\n"
            f"https://alphacephei.com/vosk/models/{self.model_name}.zip"
        )
        
    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio: NumPy array (16kHz, mono, float32)
            
        Returns:
            Transcribed text
        """
        if self.recognizer is None:
            raise RuntimeError("Vosk not initialized")
        
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Feed in ~0.1s chunks (1600 samples at 16kHz)
        chunk_size = 1600
        for i in range(0, len(audio_int16), chunk_size):
            chunk = audio_int16[i:i + chunk_size].tobytes()
            self.recognizer.AcceptWaveform(chunk)
        
        # Get final result
        result = json.loads(self.recognizer.FinalResult())
        return result.get("text", "")
        
    def transcribe_streaming(
        self,
        duration: float = 10.0,
        silence_threshold: float = 0.01
    ) -> str:
        """
        Transcribe streaming audio from microphone.
        
        Args:
            duration: Max listening time in seconds
            silence_threshold: Stop on silence below this
            
        Returns:
            Transcribed text
        """
        import time
        
        print("🎤 Listening...")
        start_time = time.time()
        audio_buffer = []
        silence_count = 0
        heard_speech = False
        
        # Record in chunks.
        # Waits up to `duration` for speech to START, then stops 0.8s after
        # speech ENDS (so it doesn't cut off before you begin talking).
        while time.time() - start_time < duration:
            chunk = sd.rec(
                int(0.1 * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                blocking=True
            )
            
            audio_buffer.append(chunk)
            
            energy = np.mean(np.abs(chunk))
            if energy >= silence_threshold:
                heard_speech = True
                silence_count = 0
            else:
                silence_count += 1
                # Only stop early once we've heard you, then 0.8s of silence
                if heard_speech and silence_count > 8:
                    print("  (end of speech)")
                    break
                
        # Combine and transcribe
        audio = np.concatenate(audio_buffer)
        result = self.transcribe(audio)
        
        if result:
            print(f"  → '{result}'")
            
        return result
        
    def reset(self):
        """Reset recognizer state."""
        if self.recognizer:
            self.recognizer.Reset()


class WakeWordListener:
    """
    Continuous wake-word detector.

    Stays on the mic at all times. The instant it hears the wake word
    ("buddy") it captures the question - either from the same utterance
    ("buddy what is a black hole") or the next one ("buddy" ... "what
    is a black hole"). This is like Alexa/Siri: always listening.
    """

    FILLERS = ("buddy", "buddies", "hey", "hi", "hello", "uh", "can you",
               "could you", "please", "what do you want to know",
               "what would you like to know")

    def __init__(
        self,
        model_path: str = None,
        model_size: str = "small",
        wake_word: str = "buddy",
        sample_rate: int = 16000,
        question_timeout: float = 12.0
    ):
        if model_path is None:
            model_name = VOSK_MODELS.get(model_size, model_size)
            model_path = PROJECT_ROOT / "models" / model_name
            if not model_path.exists():
                fallback = PROJECT_ROOT / "models" / VOSK_MODELS["small"]
                if fallback.exists():
                    print(f"⚠  Vosk model '{model_name}' not found - falling back to small model")
                    model_path = fallback
            model_path = str(model_path)
        self.model_name = Path(model_path).name
        self.wake_word = wake_word.lower()
        self.sample_rate = sample_rate
        self.question_timeout = question_timeout

        print("Loading wake-word model (Vosk)...")
        # Suppress Kaldi C++ log spam during model load
        _err = os.dup(2)
        _devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(_devnull, 2)
        try:
            self.model = Model(model_path)
        finally:
            os.dup2(_err, 2)
            os.close(_devnull)
            os.close(_err)
        print(f"✓ Wake-word listener ready (Vosk model: {self.model_name}, always listening)")

    def _rec(self):
        return KaldiRecognizer(self.model, self.sample_rate)

    def _clean(self, text: str) -> str:
        return re.sub(r"[^a-z ]", "", text.lower()).strip()

    def _meaningful(self, text: str) -> bool:
        """True if text has at least 2 real (non-filler) words."""
        words = [w for w in self._clean(text).split() if w not in self.FILLERS]
        return len(words) >= 2

    def _after_wake(self, text: str) -> str:
        """Return the words that come after the wake word."""
        clean = self._clean(text)
        idx = clean.rfind(self.wake_word)
        after = clean[idx + len(self.wake_word):] if idx >= 0 else clean
        for _ in range(4):
            new = re.sub(
                r"^(hey|hi|hello|buddy|buddies|can you|could you|please)\s+", "", after)
            if new == after:
                break
            after = new
        return after.strip()

    def wait_for_question(self, stream) -> str:
        """
        Block on an open sounddevice InputStream until the wake word is
        heard and a question is captured. Returns the question text.
        """
        rec = self._rec()
        state = "idle"  # or "question"
        state_start = time.time()
        chunk_frames = self.sample_rate // 10  # 0.1s

        while True:
            data, _overflow = stream.read(chunk_frames)
            chunk = (data.flatten() * 32767).astype(np.int16).tobytes()
            has_final = rec.AcceptWaveform(chunk)

            if not has_final:
                continue

            final = json.loads(rec.FinalResult()).get("text", "") or ""
            rec.Reset()
            now = time.time()

            if state == "idle":
                if self.wake_word in self._clean(final).split():
                    q = self._after_wake(final)
                    if self._meaningful(q):
                        return q
                    print("  ✓ Buddy! Say your question")
                    state = "question"
                    state_start = now
            else:  # already heard wake word, waiting for the question
                if self._meaningful(final):
                    return final
                state_start = now  # was noise, keep waiting

            # Timeout: heard 'buddy' but no question
            if state == "question" and (now - state_start) > self.question_timeout:
                print("  (no question heard - back to listening for 'Buddy')")
                state = "idle"
                state_start = now

    def watch_for_stop(self, stream, stop_event, watching):
        """
        Run in a thread while the assistant is speaking. Listens for the
        word 'stop' and sets stop_event when heard. Consumes the stream in
        real time so no audio backlogs up. Stops when `watching` is cleared
        (answer finished) so it never lingers on the mic.
        """
        rec = self._rec()
        chunk_frames = self.sample_rate // 10
        while watching.is_set() and not stop_event.is_set():
            try:
                data, _overflow = stream.read(chunk_frames)
            except Exception:
                break
            chunk = (data.flatten() * 32767).astype(np.int16).tobytes()
            has_final = rec.AcceptWaveform(chunk)
            text = ""
            if has_final:
                text = json.loads(rec.FinalResult()).get("text", "") or ""
                rec.Reset()
            else:
                text = json.loads(rec.PartialResult()).get("text", "") or ""
            words = self._clean(text).split()
            # Require a SHORT utterance containing 'stop' - a human says
            # "stop" (1-2 words); our own TTS sentences are much longer.
            if "stop" in words and len(words) <= 4:
                stop_event.set()
                break


# Test
if __name__ == "__main__":
    print("STT Test - Say something...")
    stt = SpeechToText()
    text = stt.transcribe_streaming(duration=10.0)
    print(f"Result: {text}")