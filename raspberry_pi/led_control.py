import os
import subprocess

import RPi.GPIO as GPIO
import time
import sys
import threading
import traceback

from dotenv import load_dotenv

from api import clear_api_token
from restarts import restart_in_setup_mode
from config import Config

LED_CONTROL_DISABLED = 'LED_DISABLED'

class LedControl:
    """Class for controlling the button's built-in LED"""

    def __init__(self):
        """Initialize the LED control with the specified pin"""
        load_dotenv(override=True)
        self.module_disabled = os.getenv(LED_CONTROL_DISABLED) == 'true'
        self.led_disabled = False
        self.button_disabled = False
        self.config = Config()

        self.BUTTON_PIN = 17
        self.LED_PIN = 27
        self.pattern_thread = None
        self.pwm = None
        self.running = False
        self.current_state = None

        # Initialize GPIO
        try:
            # Clean any previous setup
            GPIO.cleanup()
        except:
            pass

        GPIO.setmode(GPIO.BCM)

        self.setup_led()
        self.setup_button()

    def setup_led(self):
        """Set up the LED pin separately from button"""
        if self.module_disabled:
            return

        try:
            GPIO.setup(self.LED_PIN, GPIO.OUT)
            print(f"LED pin {self.LED_PIN} configured successfully")

            # Test the LED by blinking once
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.LED_PIN, GPIO.LOW)
        except Exception as e:
            print(f"LED setup failed: {traceback.format_exc()}")
            self.led_disabled = True

    def setup_button(self):
        """Set up the button separately with fallback"""
        if self.module_disabled:
            return

        try:
            GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Start a separate thread to poll the button state instead of using event detection
            self.running = True
            self.button_thread = threading.Thread(target=self.poll_button_state)
            self.button_thread.daemon = True
            self.button_thread.start()
            print(f"Button pin {self.BUTTON_PIN} configured in polling mode")
        except Exception as e:
            print(f"Button setup failed: {traceback.format_exc()}")
            print("Button functionality will be disabled")
            self.button_disabled = True

    def poll_button_state(self):
        """Poll the button state instead of using event detection"""
        print("Starting button polling thread")
        button_pressed = False
        press_start_time = 0
        two_second_mark_reached = False

        while self.running and not self.button_disabled:
            try:
                if GPIO.getmode() != GPIO.BCM:
                    GPIO.setmode(GPIO.BCM)
                current_state = GPIO.input(self.BUTTON_PIN)

                # Button pressed (LOW when pressed with pull-up resistor)
                if current_state == GPIO.LOW and not button_pressed:
                    button_pressed = True
                    press_start_time = time.time()
                    two_second_mark_reached = False
                    print("Button pressed")

                # Button still pressed - check for 2 second mark
                elif current_state == GPIO.LOW and button_pressed and not two_second_mark_reached and time.time() - press_start_time > 2:
                    print("2 second press detected - preparing for reboot")
                    two_second_mark_reached = True
                    self.signal_reboot_preparation()

                # Check for long press while button is still pressed
                elif current_state == GPIO.LOW and button_pressed and time.time() - press_start_time > 10:
                    print("Long press detected (10 seconds) - triggering reset")
                    button_pressed = False  # Reset so we don't trigger multiple times
                    two_second_mark_reached = False
                    self.signal_reset_mode()
                    # clear just the api token so we still have the current config to allow editing
                    # the user will just have to re-enter their email/password
                    clear_api_token()
                    restart_in_setup_mode()

                # Button released
                elif current_state == GPIO.HIGH and button_pressed:
                    button_pressed = False
                    duration = time.time() - press_start_time
                    print(f"Button released after {duration:.1f} seconds")

                    # If we have passed the 2 second mark but not the 10 second mark, reboot
                    if two_second_mark_reached and duration < 10:
                        print("Rebooting system...")
                        self.reboot_system()

                    two_second_mark_reached = False

                # Small sleep to prevent CPU hogging
                time.sleep(0.1)

            except Exception as e:
                print(f"Error in button polling: {traceback.format_exc()}")
                time.sleep(1)  # Longer sleep on error

    def set_state(self, state):
        """Set the LED to different states based on mode"""
        if self.module_disabled or self.led_disabled:
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

    def wifi_issue_pattern(self):
        """LED pattern for WiFi connectivity issues: double-blink with pause"""
        if self.module_disabled or self.led_disabled:
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

    def signal_reboot_preparation(self):
        """Visual indication that the system is preparing to reboot (2 blinks)"""
        if self.module_disabled or self.led_disabled:
            return

        # Store the current state
        previous_state = self.current_state

        # Stop any current patterns
        self.stop_pattern_thread()

        # Blink twice to indicate reboot preparation
        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        for _ in range(2):
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(self.LED_PIN, GPIO.LOW)
            time.sleep(0.1)

        time.sleep(3)

        # Restore previous state
        if previous_state:
            self.set_state(previous_state)

    def signal_reset_mode(self):
        """Visual indication that the system is resetting to setup mode (5 blinks)"""
        if self.module_disabled or self.led_disabled:
            return

        # Stop any current patterns
        self.stop_pattern_thread()

        # Blink 5 times to indicate reset to setup mode
        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        for _ in range(5):
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(self.LED_PIN, GPIO.LOW)
            time.sleep(0.2)

    def start_pattern_thread(self, pattern_function):
        """Start a thread to run a custom LED pattern"""
        if self.module_disabled:
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

    def reboot_system(self):
        """Reboot the system"""
        try:
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/reboot"], check=True)
        except Exception as e:
            print(f"Error rebooting system: {traceback.format_exc()}")

    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if hasattr(self, 'button_thread') and self.button_thread.is_alive():
            self.button_thread.join(timeout=0.5)
        if self.pwm:
            self.pwm.stop()
        self.stop_pattern_thread()
        if not self.led_disabled:
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