#!/usr/bin/env python3
"""
Whisper HTTP Client
===================
Client for the Whisper HTTP server (whisper_server.py).
Drop-in replacement for WhisperSTT.
"""

import base64
import json
import time
from pathlib import Path

import numpy as np
import requests

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_RATE = 16000


class WhisperClient:
    """HTTP client for Whisper server - model stays warm in separate process."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8765",
        timeout: float = 30.0,
    ):
        """
        Initialize Whisper HTTP client.
        
        Args:
            server_url: URL of the Whisper server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._check_health()

    def _check_health(self):
        """Verify server is running."""
        try:
            resp = requests.get(
                f"{self.server_url}/health",
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"✓ Whisper server ready (model: {data.get('model', 'unknown')})")
            else:
                print(f"⚠ Whisper server returned {resp.status_code}")
        except requests.RequestException as e:
            print(f"⚠ Whisper server unavailable ({e})")
            raise

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe 16kHz mono float32 audio via HTTP.
        
        Args:
            audio: NumPy array (float32, -1.0..1.0)
            
        Returns:
            Transcribed text
        """
        if audio is None or len(audio) < SAMPLE_RATE // 10:
            return ""
        
        t0 = time.time()
        
        # Encode audio as base64
        audio_b64 = base64.b64encode(audio.tobytes()).decode("ascii")
        
        try:
            resp = requests.post(
                f"{self.server_url}/transcribe",
                json={"audio": audio_b64},
                timeout=self.timeout,
            )
            
            if resp.status_code != 200:
                error = resp.json().get("error", "Unknown error")
                print(f"  ✗ Whisper error: {error}")
                return ""
            
            data = resp.json()
            text = data.get("text", "")
            n_sec = len(audio) / SAMPLE_RATE
            print(f"  ⏱ whisper-http: {n_sec:.1f}s audio -> {time.time() - t0:.2f}s -> {text!r}")
            return text
            
        except requests.RequestException as e:
            print(f"  ✗ Whisper request failed: {e}")
            return ""


# Test
if __name__ == "__main__":
    print("Testing Whisper HTTP client...")
    
    # Create test audio (sine wave)
    duration = 2.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    try:
        client = WhisperClient()
        text = client.transcribe(audio)
        print(f"Result: {text!r}")
    except Exception as e:
        print(f"Error: {e}")
        print("\nStart the server first:")
        print("  python3 whisper_server.py --model small.en")