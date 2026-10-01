#!/usr/bin/env python3
"""
Interrupt Handler
=================
Handles physical button and voice interrupt commands.
"""

# GPIO is optional (Hailo HAT may block pins)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO = None
    GPIO_AVAILABLE = False
from typing import Callable, Optional


class InterruptHandler:
    """Handle interrupt from button or voice."""
    
    def __init__(
        self,
        button_pin: int = 4,
        interrupt_words: list = None
    ):
        """
        Initialize interrupt handler.
        
        Args:
            button_pin: GPIO pin for physical button
            interrupt_words: List of voice interrupt words
        """
        self.button_pin = button_pin
        self.interrupt_words = interrupt_words or ["stop", "cut it", "enough"]
        self.callback: Optional[Callable] = None
        self.interrupted = False
        self.gpio_available = False
        
        # Set up GPIO
        self._setup_gpio()
        
    def _setup_gpio(self):
        """Configure GPIO for button."""
        if not GPIO_AVAILABLE:
            print("⚠ GPIO not available - voice interrupt only (say 'STOP!')")
            return
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Add interrupt (falling edge = button pressed)
            GPIO.add_event_detect(
                self.button_pin,
                GPIO.FALLING,
                callback=self._button_callback,
                bouncetime=200
            )
            print("✓ Button configured on GPIO", self.button_pin)
            self.gpio_available = True
            
        except Exception as e:
            print(f"⚠ GPIO not available: {e}")
            print("  Voice interrupt only (say 'STOP!')")
            
    def _button_callback(self, channel):
        """GPIO button callback."""
        print("  🛑 Button pressed!")
        self.interrupted = True
        if self.callback:
            self.callback()
            
    def setup_button(self, callback: Callable):
        """Set callback for button press."""
        self.callback = callback
        
    def check_word(self, text: str) -> bool:
        """
        Check if text contains interrupt word.
        
        Args:
            text: User input text
            
        Returns:
            True if interrupt word detected
        """
        text_lower = text.lower()
        for word in self.interrupt_words:
            if word in text_lower:
                print(f"  🛑 Interrupt word detected: '{word}'")
                self.interrupted = True
                return True
        return False
        
    def reset(self):
        """Reset interrupt state."""
        self.interrupted = False
        
    def cleanup(self):
        """Clean up GPIO."""
        if self.gpio_available and GPIO_AVAILABLE:
            GPIO.cleanup(self.button_pin)


# Test
if __name__ == "__main__":
    import time
    
    print("Interrupt Handler Test")
    print("Press button or say 'STOP!'")
    
    handler = InterruptHandler()
    handler.setup_button(lambda: print("Button callback!"))
    
    try:
        while True:
            text = input("Say something: ")
            if handler.check_word(text):
                print("Interrupted!")
                handler.reset()
    except KeyboardInterrupt:
        handler.cleanup()
        print("\nStopped")