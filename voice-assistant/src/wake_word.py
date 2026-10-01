#!/usr/bin/env python3
"""
Wake Word Detection Module
==========================
Detects "Hey Buddy" wake word for STEM Buddy assistant.

Uses simple audio energy detection for demo purposes.
Production: Replace with Porcupine or Hailo-accelerated model.
"""

import asyncio
import numpy as np
import sounddevice as sd


class WakeWordDetector:
    """Simple wake word detector (energy-based for demo)."""
    
    def __init__(self, wake_word: str = "hey buddy"):
        self.wake_word = wake_word
        self.running = False
        self.sample_rate = 16000
        self.frame_length = 512
        self.threshold = 0.01  # Adjust based on environment
        
    async def wait_for_wake_word(self) -> bool:
        """
        Listen for wake word.
        
        Returns:
            True if wake word detected
        """
        self.running = True
        
        # Start audio stream
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32
        )
        
        with stream:
            while self.running:
                frame, overflowed = stream.read(self.frame_length)
                
                # Calculate audio energy
                energy = np.mean(np.abs(frame))
                
                # Simple voice activity detection
                # In production, use ML model to detect "hey buddy"
                if energy > self.threshold:
                    print(f"  Audio detected (energy: {energy:.4f})")
                    # For demo: any significant sound triggers
                    if energy > self.threshold * 3:
                        self.running = False
                        return True
                        
                await asyncio.sleep(0.001)
                
        return False
        
    def stop(self):
        """Stop listening."""
        self.running = False
        
    def set_sensitivity(self, sensitivity: float):
        """Adjust detection threshold."""
        if 0.0 <= sensitivity <= 1.0:
            self.threshold = 0.001 + (0.05 - 0.001) * (1 - sensitivity)


# Test
if __name__ == "__main__":
    async def test():
        print("Wake Word Test - Say something loud...")
        detector = WakeWordDetector()
        result = await detector.wait_for_wake_word()
        print(f"Detected: {result}")
        
    asyncio.run(test())