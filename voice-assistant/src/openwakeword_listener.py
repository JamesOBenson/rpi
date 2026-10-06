#!/usr/bin/env python3
"""
OpenWakeWord Listener
=====================
Lightweight wake word detection using OpenWakeWord library.
Replaces Vosk for wake word detection - lower CPU, multiple wake words.

https://github.com/dscripka/openWakeWord
"""

import time
import threading
from pathlib import Path
import numpy as np

import sounddevice as sd

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SAMPLES = 1280  # ~80ms at 16kHz


class OpenWakeWordListener:
    """
    Continuous wake word detection with OpenWakeWord.
    
    Features:
    - Multiple wake words simultaneously
    - Low CPU usage (~2-5% on Pi 5)
    - Configurable threshold and cooldown
    - Compatible with WakeWordListener interface
    """
    
    def __init__(
        self,
        wake_words: list = None,
        threshold: float = 0.5,
        cooldown: float = 1.5,
        sample_rate: int = 16000,
    ):
        """
        Initialize OpenWakeWord listener.
        
        Args:
            wake_words: List of wake word model names (e.g., ["hey_jarvis", "buddy"])
            threshold: Detection threshold (0.0-1.0, higher = less false positives)
            cooldown: Seconds between wake word triggers
            sample_rate: Audio sample rate (default 16000)
        """
        self.wake_words = wake_words or ["hey_jarvis"]
        self.threshold = threshold
        self.cooldown = cooldown
        self.sample_rate = sample_rate
        self._running = False
        self._thread = None
        self._last_wake_time = 0
        self._wake_detected = threading.Event()
        self._stream = None
        
        # Load OpenWakeWord model
        try:
            from openwakeword.model import Model
            print(f"Loading OpenWakeWord models: {self.wake_words}")
            self.model = Model(wakeword_models=self.wake_words)
            print(f"✓ OpenWakeWord ready ({len(self.wake_words)} wake words)")
        except ImportError:
            print("✗ Install openwakeword: pip install openwakeword")
            raise
        except Exception as e:
            print(f"✗ OpenWakeWord error: {e}")
            raise
    
    def start(self):
        """Start listening in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._thread.start()
        print(f"✓ OpenWakeWord listening (threshold={self.threshold}, cooldown={self.cooldown}s)")
    
    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        print("✓ OpenWakeWord stopped")
    
    def _detect_loop(self):
        """Main detection loop - runs in background thread."""
        try:
            # Open audio stream
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=CHUNK_SAMPLES,
            )
            self._stream.start()
            
            while self._running:
                # Read audio chunk
                data, overflowed = self._stream.read(CHUNK_SAMPLES, error=False)
                if overflowed:
                    continue
                
                audio = data.flatten().astype(np.int16)
                
                # Detect wake words
                try:
                    prediction = self.model.predict(audio)
                except Exception:
                    continue
                
                now = time.time()
                if now - self._last_wake_time < self.cooldown:
                    continue
                
                # Check each wake word
                for keyword, score in prediction.items():
                    if score >= self.threshold:
                        self._last_wake_time = now
                        keyword_clean = keyword.replace("_", " ")
                        print(f"  ✓ Wake word: {keyword_clean} (score={score:.3f})")
                        self._wake_detected.set()
                        break
        
        except Exception as e:
            print(f"✗ OpenWakeWord error: {e}")
        finally:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
    
    def wait_for_question(self, stream, question_timeout: float = 10.0) -> tuple:
        """
        Block until wake word is detected, then capture question.
        
        Args:
            stream: Audio stream (used for question capture)
            question_timeout: Max seconds to wait for question after wake word
            
        Returns:
            (question_text, question_audio) - text is empty, audio contains the question
        """
        print("  (waiting for wake word...)")
        
        # Wait for wake word
        self._wake_detected.wait()
        self._wake_detected.clear()
        
        print("  ✓ Buddy! Say your question")
        
        # Capture question audio
        start_time = time.time()
        audio_buffer = []
        silence_count = 0
        heard_speech = False
        
        while time.time() - start_time < question_timeout:
            try:
                chunk, _ = stream.read(int(0.1 * self.sample_rate))
                audio_buffer.append(chunk)
                
                energy = np.mean(np.abs(chunk))
                if energy >= 0.01:
                    heard_speech = True
                    silence_count = 0
                else:
                    silence_count += 1
                    if heard_speech and silence_count > 8:  # 0.8s silence
                        print("  (end of speech)")
                        break
            except Exception:
                break
        
        # Combine audio
        audio = np.concatenate(audio_buffer) if audio_buffer else None
        
        # Return empty text - Whisper will transcribe the audio
        return "", audio


# Test
if __name__ == "__main__":
    print("OpenWakeWord Test - Say 'Hey Jarvis' or 'Buddy'...")
    print("Press Ctrl+C to stop\n")
    
    listener = OpenWakeWordListener(
        wake_words=["hey_jarvis", "buddy"],
        threshold=0.5,
        cooldown=1.5,
    )
    
    listener.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()