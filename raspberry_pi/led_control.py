import os

import RPi.GPIO as GPIO
import time
import sys
import threading
import traceback

from dotenv import load_dotenv

LED_DISABLED = 'LED_DISABLED'

class LedControl:
    """Class for controlling the button's built-in LED"""

    def __init__(self):
        """Initialize the LED control with the specified pin"""
        load_dotenv(override=True)
        self.disabled = os.getenv(LED_DISABLED) == 'true'

        self.BUTTON_PIN = 17
        self.LED_PIN = 27
        self.pattern_thread = None
        self.pwm = None
        self.running = False
        self.current_state = None

        self.setup()

    def setup(self):
        """Configure GPIO pin for button"""
        if self.disabled:
            return

        # Setup GPIO mode only once
        if not LedControl._is_initialized:
            GPIO.setmode(GPIO.BCM)
            LedControl._is_initialized = True

        # Configure pins
        GPIO.setup(self.LED_PIN, GPIO.OUT)
        GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        try:
            # Check if event detection is already set for this pin
            try:
                # Remove any existing event detection first
                GPIO.remove_event_detect(self.BUTTON_PIN)
            except:
                # Ignore errors when trying to remove event detection
                pass

            # Now add the event detection
            GPIO.add_event_detect(self.BUTTON_PIN, GPIO.FALLING,
                                  callback=self.button_pressed_callback,
                                  bouncetime=300)
        except Exception:
            self.disabled = True
            print(f"Disabling LedControl because button event detection setup failed: {traceback.format_exc()}")
            # Additional diagnostic information
            print(f"Current GPIO function for BUTTON_PIN ({self.BUTTON_PIN}): {GPIO.gpio_function(self.BUTTON_PIN)}")

    def button_pressed_callback(self, channel):
        """Handle button press events"""
        if self.disabled:
            return
        # Check how long the button is held
        start_time = time.time()
        while GPIO.input(self.BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.1)
            if time.time() - start_time > 10:  # 10-second hold
                self.restart_in_setup_mode()
                break

    def set_state(self, state):
        """Set the LED to different states based on mode"""
        if self.disabled:
            return
        # Stop any existing pattern thread
        self.stop_pattern_thread()

        # Set the current state
        self.current_state = state

        if state == "setup":
            # Blinking blue in setup mode (1 Hz)
            if self.pwm:
                self.pwm.stop()
            self.pwm = GPIO.PWM(self.LED_PIN, 1)
            self.pwm.start(50)  # 50% duty cycle - half on, half off
        elif state == "running":
            # Solid on in normal operation
            if self.pwm:
                self.pwm.stop()
                self.pwm = None
            GPIO.output(self.LED_PIN, GPIO.HIGH)
        elif state == "error":
            # Fast blinking in error state (5 Hz)
            if self.pwm:
                self.pwm.stop()
            self.pwm = GPIO.PWM(self.LED_PIN, 5)
            self.pwm.start(50)
        elif state == "wifi_issue":
            # Double-blink pattern for WiFi connectivity issues
            self.start_pattern_thread(self.wifi_issue_pattern)
        elif state == "reset":
            # Three quick flashes
            if self.pwm:
                self.pwm.stop()
                self.pwm = None
            for _ in range(3):
                GPIO.output(self.LED_PIN, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(self.LED_PIN, GPIO.LOW)
                time.sleep(0.2)

    def wifi_issue_pattern(self):
        """LED pattern for WiFi connectivity issues: double-blink with pause"""
        if self.disabled:
            return
        while self.running and self.current_state == "wifi_issue":
            # Double blink
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.LED_PIN, GPIO.LOW)
            time.sleep(0.2)
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.LED_PIN, GPIO.LOW)

            # Longer pause
            time.sleep(1.0)

    def start_pattern_thread(self, pattern_function):
        """Start a thread to run a custom LED pattern"""
        if self.disabled:
            return
        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        self.running = True
        self.pattern_thread = threading.Thread(target=pattern_function)
        self.pattern_thread.daemon = True
        self.pattern_thread.start()

    def stop_pattern_thread(self):
        """Stop any running pattern thread"""
        if self.pattern_thread and self.pattern_thread.is_alive():
            self.current_state = None
            self.pattern_thread.join(timeout=0.5)
            self.pattern_thread = None

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.pwm:
            self.pwm.stop()
        self.stop_pattern_thread()
        if self.disabled:
            return
        GPIO.output(self.LED_PIN, GPIO.LOW)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            LedControl().set_state(sys.argv[1])
        except KeyboardInterrupt:
            GPIO.cleanup()
        except Exception as e:
            print(f"Error: {str(e)}")
            GPIO.cleanup()