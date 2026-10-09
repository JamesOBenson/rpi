#!/usr/bin/env python3
"""
LED Controller
==============
Controls RGB LED ring for visual feedback.
GPIO is optional - works with console output if GPIO unavailable.
"""

# GPIO is optional (Hailo HAT may block pins)
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    GPIO = None
    GPIO_AVAILABLE = False
import time
from enum import Enum


class LEDState(Enum):
    """LED states for different assistant states."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class LEDController:
    """Control RGB LED for visual feedback."""

    # LED colors (RGB values 0-255)
    COLORS = {
        LEDState.IDLE: (0, 0, 0),  # Off
        LEDState.LISTENING: (0, 0, 255),  # Blue
        LEDState.THINKING: (255, 255, 0),  # Yellow
        LEDState.SPEAKING: (0, 255, 0),  # Green
        LEDState.INTERRUPTED: (255, 0, 0),  # Red
        LEDState.ERROR: (255, 0, 128),  # Magenta
    }

    # Console colors (ANSI codes)
    CONSOLE_COLORS = {
        LEDState.IDLE: "\033[0m",
        LEDState.LISTENING: "\033[34m",  # Blue
        LEDState.THINKING: "\033[33m",  # Yellow
        LEDState.SPEAKING: "\033[32m",  # Green
        LEDState.INTERRUPTED: "\033[31m",  # Red
        LEDState.ERROR: "\033[35m",  # Magenta
    }

    def __init__(
        self,
        red_pin: int = 17,
        green_pin: int = 27,
        blue_pin: int = 22,
        enabled: bool = True,
    ):
        """
        Initialize LED controller.

        Args:
            red_pin: GPIO pin for red LED
            green_pin: GPIO pin for green LED
            blue_pin: GPIO pin for blue LED
            enabled: Enable LED control
        """
        self.enabled = enabled
        self.current_state = LEDState.IDLE
        self.gpio_available = False

        if not self.enabled:
            print("⚠ LED disabled (console mode)")
            return

        if not GPIO_AVAILABLE:
            print("⚠ GPIO not available - LED in console mode")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(red_pin, GPIO.OUT)
            GPIO.setup(green_pin, GPIO.OUT)
            GPIO.setup(blue_pin, GPIO.OUT)

            self.red_pwm = GPIO.PWM(red_pin, 100)
            self.green_pwm = GPIO.PWM(green_pin, 100)
            self.blue_pwm = GPIO.PWM(blue_pin, 100)

            self.red_pwm.start(0)
            self.green_pwm.start(0)
            self.blue_pwm.start(0)

            self.gpio_available = True
            print("✓ LED controller initialized")

        except Exception as e:
            print(f"⚠ LED not available (Hailo HAT may cover pins): {e}")
            print("  Using console output instead")
            self.gpio_available = False

    def set_state(self, state: LEDState):
        """
        Set LED state.

        Args:
            state: LEDState enum value
        """
        self.current_state = state

        if self.gpio_available:
            color = self.COLORS.get(state, (0, 0, 0))
            self._set_color(*color)
        else:
            # Console fallback
            color_code = self.CONSOLE_COLORS.get(state, "\033[0m")
            print(f"{color_code}[{state.value.upper()}]{'\033[0m'}")

    def _set_color(self, red: int, green: int, blue: int):
        """Set RGB color (0-255 each)."""
        if not self.gpio_available:
            return

        self.red_pwm.ChangeDutyCycle(red / 255 * 100)
        self.green_pwm.ChangeDutyCycle(green / 255 * 100)
        self.blue_pwm.ChangeDutyCycle(blue / 255 * 100)

    def blink(self, state: LEDState, times: int = 3, duration: float = 0.2):
        """Blink LED in a state."""
        if not self.gpio_available:
            print(f"  Blinking: {state.value}")
            return

        for _ in range(times):
            self.set_state(state)
            time.sleep(duration)
            self.set_state(LEDState.IDLE)
            time.sleep(duration)

    def pulse(self, state: LEDState, cycles: int = 10):
        """Pulse LED brightness."""
        if not self.gpio_available:
            print(f"  Pulsing: {state.value}")
            return

        color = self.COLORS.get(state, (0, 0, 0))

        for i in range(cycles):
            duty = (i / cycles) * 100
            self.red_pwm.ChangeDutyCycle(color[0] / 255 * duty)
            self.green_pwm.ChangeDutyCycle(color[1] / 255 * duty)
            self.blue_pwm.ChangeDutyCycle(color[2] / 255 * duty)
            time.sleep(0.05)

    def turn_off(self):
        """Turn off LED."""
        if self.gpio_available:
            self.set_state(LEDState.IDLE)
        else:
            print("[OFFLINE]")

    def cleanup(self):
        """Clean up GPIO."""
        if self.gpio_available:
            self.red_pwm.stop()
            self.green_pwm.stop()
            self.blue_pwm.stop()
            GPIO.cleanup()


# Test
if __name__ == "__main__":
    print("LED Test")
    led = LEDController()

    states = [
        LEDState.LISTENING,
        LEDState.THINKING,
        LEDState.SPEAKING,
        LEDState.INTERRUPTED,
    ]

    for state in states:
        print(f"Setting: {state.value}")
        led.set_state(state)
        time.sleep(1)

    led.turn_off()
    led.cleanup()
