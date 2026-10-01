#!/usr/bin/env python3
"""
Audio Listener
==============
Captures audio from microphone for speech recognition.
"""

import numpy as np
import sounddevice as sd
from typing import Optional


class AudioListener:
    """Capture audio from microphone."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        timeout: float = 10.0
    ):
        """
        Initialize audio listener.
        
        Args:
            sample_rate: Audio sample rate (16kHz recommended)
            channels: Number of audio channels (1 = mono)
            timeout: Maximum listening time in seconds
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.timeout = timeout
        self.silence_threshold = 0.01
        self.silence_duration = 1.5  # seconds
        
    def listen(self) -> str:
        """
        Listen for speech and return transcription.
        
        Returns:
            Transcribed text (empty if no speech detected)
        """
        print("🎤 Listening...")
        
        # Record audio
        audio = self._record_audio()
        
        if audio is None or len(audio) == 0:
            return ""
            
        # TODO: Pass to STT engine
        # For now, return placeholder
        return "placeholder_transcription"
        
    def _record_audio(self) -> Optional[np.ndarray]:
        """
        Record audio until silence or timeout.
        
        Returns:
            NumPy array of audio samples
        """
        import time
        
        audio_chunks = []
        start_time = time.time()
        silence_frames = 0
        frame_duration = 0.1  # seconds
        
        try:
            while time.time() - start_time < self.timeout:
                # Record chunk
                chunk = sd.rec(
                    int(self.sample_rate * frame_duration),
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                    blocking=True
                )
                
                audio_chunks.append(chunk)
                
                # Check for silence
                energy = np.mean(np.abs(chunk))
                if energy < self.silence_threshold:
                    silence_frames += 1
                    if silence_frames > (self.silence_duration / frame_duration):
                        print("  Silence detected")
                        break
                else:
                    silence_frames = 0
                    
        except Exception as e:
            print(f"Recording error: {e}")
            return None
            
        # Combine chunks
        audio = np.concatenate(audio_chunks)
        
        # Trim trailing silence
        audio = self._trim_silence(audio)
        
        return audio
        
    def _trim_silence(self, audio: np.ndarray) -> np.ndarray:
        """Remove leading and trailing silence."""
        # Simple implementation - could be improved
        threshold = self.silence_threshold
        frame_size = int(self.sample_rate * 0.05)  # 50ms frames
        
        # Find start
        start = 0
        for i in range(0, len(audio) - frame_size, frame_size):
            if np.mean(np.abs(audio[i:i+frame_size])) > threshold:
                break
            start = i + frame_size
            
        # Find end
        end = len(audio)
        for i in range(len(audio) - frame_size, start, -frame_size):
            if np.mean(np.abs(audio[i:i+frame_size])) > threshold:
                break
            end = i
            
        return audio[start:end]
        
    def set_sensitivity(self, threshold: float):
        """Adjust silence detection threshold."""
        if 0.0 < threshold < 1.0:
            self.silence_threshold = threshold
            
    def set_timeout(self, timeout: float):
        """Set maximum listening duration."""
        if timeout > 0:
            self.timeout = timeout


# Test
if __name__ == "__main__":
    print("Audio Listener Test")
    listener = AudioListener()
    
    print("Say something...")
    audio = listener._record_audio()
    
    print(f"Recorded {len(audio)} samples")
    print(f"Duration: {len(audio) / listener.sample_rate:.2f}s")