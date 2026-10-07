#!/usr/bin/env python3
"""
TTS HTTP Client
===============
Client for the Piper TTS HTTP server (tts_server.py).
Drop-in replacement for TextToSpeech.
"""

import io
import time
import wave
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 22050  # Piper default


class TTSClient:
    """HTTP client for Piper TTS server."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8766",
        timeout: float = 30.0,
    ):
        """
        Initialize TTS HTTP client.
        
        Args:
            server_url: URL of the TTS server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._check_health()

    def _check_health(self):
        """Verify server is running."""
        try:
            import requests
            resp = requests.get(
                f"{self.server_url}/health",
                timeout=5.0,
            )
            if resp.status_code == 200:
                print(f"✓ TTS server ready")
            else:
                print(f"⚠ TTS server returned {resp.status_code}")
        except Exception as e:
            print(f"⚠ TTS server unavailable ({e})")
            raise

    def synthesize(self, text: str, speed: float = 0.9, length_scale: float = 1.0) -> np.ndarray:
        """
        Synthesize text to audio via HTTP.
        
        Args:
            text: Text to synthesize
            speed: Overall speed multiplier (default 0.9)
            length_scale: Speech rate control (default 1.0, lower = faster)
            
        Returns:
            NumPy array of float32 audio samples (-1.0..1.0)
        """
        import requests
        
        if not text.strip():
            return np.array([], dtype=np.float32)
        
        try:
            resp = requests.post(
                f"{self.server_url}/synthesize",
                json={"text": text, "speed": speed, "length_scale": length_scale},
                timeout=self.timeout,
            )
            
            if resp.status_code != 200:
                error = resp.json().get("error", "Unknown error")
                print(f"  ✗ TTS error: {error}")
                return np.array([], dtype=np.float32)
            
            # Decode WAV audio
            wav_data = resp.content
            with wave.open(io.BytesIO(wav_data), "rb") as wav:
                n_frames = wav.getnframes()
                sample_width = wav.getsampwidth()
                
                # Read raw audio data
                raw = wav.readframes(n_frames)
                
                # Convert to float32
                if sample_width == 2:  # 16-bit
                    audio = np.frombuffer(raw, dtype=np.int16)
                    audio = audio.astype(np.float32) / 32768.0
                else:
                    print(f"  ⚠ Unexpected sample width: {sample_width}")
                    audio = np.array([], dtype=np.float32)
                
                return audio
        
        except Exception as e:
            print(f"  ✗ TTS request failed: {e}")
            return np.array([], dtype=np.float32)


# Test
if __name__ == "__main__":
    print("TTS HTTP Client Test")
    
    try:
        client = TTSClient()
        audio = client.synthesize("Hello, this is a test of the TTS server.")
        print(f"Generated {len(audio)} samples")
        
        # Play audio
        sd.play(audio, SAMPLE_RATE)
        sd.wait()
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
        print("\nStart the TTS server first:")
        print("  python3 tts_server.py --voice en_US-amy-medium")