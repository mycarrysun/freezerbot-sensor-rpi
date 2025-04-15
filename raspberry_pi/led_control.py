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
BUTTON_PIN = 17
LED_PIN = 27

class LedControl:
    """Class for controlling the button's built-in LED with singleton pattern"""

    # Class variable to track the single instance
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure only one instance of LedControl exists"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LedControl, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize the LED control with the specified pin"""
        # Skip initialization if already done
        if self._initialized:
            return

        self._initialized = True

        load_dotenv(override=True)
        self.module_disabled = os.getenv(LED_CONTROL_DISABLED) == 'true'
        self.led_disabled = False
        self.button_disabled = False
        self.config = Config()

        self.BUTTON_PIN = BUTTON_PIN
        self.LED_PIN = LED_PIN
        self.pattern_thread = None
        self.pwm = None
        self.running = False
        self.current_state = None
        self.button_thread = None

        # Action trigger flags
        self.reboot_triggered = False
        self.setup_mode_triggered = False
        self.factory_reset_triggered = False

        # Ensure we're starting with a clean state
        self.cleanup()

        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)

        self.setup_led()
        self.setup_button()

        print("LedControl initialized - ID: " + str(id(self)))

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

            # Make sure we don't have an existing thread running
            if self.button_thread is not None and self.button_thread.is_alive():
                print("Button thread already running - not starting a new one")
                return

            self.button_thread = threading.Thread(target=self.poll_button_state)
            self.button_thread.daemon = True
            self.button_thread.start()
            print(f"Button pin {self.BUTTON_PIN} configured in polling mode - Thread ID: {self.button_thread.ident}")
        except Exception as e:
            print(f"Button setup failed: {traceback.format_exc()}")
            print("Button functionality will be disabled")
            self.button_disabled = True

    def poll_button_state(self):
        """Poll the button state instead of using event detection"""
        thread_id = threading.get_ident()
        print(f"Starting button polling thread - Thread ID: {thread_id}")

        button_pressed = False
        press_start_time = 0
        two_second_mark_reached = False
        ten_second_mark_reached = False
        thirty_second_mark_reached = False

        while self.running and not self.button_disabled:
            try:
                if GPIO.getmode() != GPIO.BCM:
                    GPIO.setmode(GPIO.BCM)

                current_function = GPIO.gpio_function(self.BUTTON_PIN)
                if current_function != GPIO.IN:
                    GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    print(f"Button pin {self.BUTTON_PIN} reconfigured as input with pull-up")
                    time.sleep(0.1)  # Short delay to allow hardware to stabilize

                current_time = time.time()
                current_state = GPIO.input(self.BUTTON_PIN)

                # Button pressed (LOW when pressed with pull-up resistor)
                if current_state == GPIO.LOW and not button_pressed:
                    button_pressed = True
                    press_start_time = time.time()
                    two_second_mark_reached = False
                    ten_second_mark_reached = False
                    thirty_second_mark_reached = False
                    self.reboot_triggered = False
                    self.setup_mode_triggered = False
                    self.factory_reset_triggered = False
                    print(f"[Thread {thread_id}] Button pressed")

                # Button still pressed - check for 2 second mark
                elif current_state == GPIO.LOW and button_pressed and not two_second_mark_reached and time.time() - press_start_time > 2:
                    print(f"[Thread {thread_id}] 2 second press detected - preparing for reboot")
                    two_second_mark_reached = True
                    self.signal_reboot_preparation()

                # Check for 10 second press while button is still pressed
                elif current_state == GPIO.LOW and button_pressed and not ten_second_mark_reached and time.time() - press_start_time > 10:
                    print(f"[Thread {thread_id}] Long press detected (10 seconds) - preparing for reset mode")
                    ten_second_mark_reached = True
                    self.signal_reset_mode()

                # Check for 30 second press while button is still pressed
                elif current_state == GPIO.LOW and button_pressed and not thirty_second_mark_reached and time.time() - press_start_time > 30:
                    print(f"[Thread {thread_id}] Extra long press detected (30 seconds) - preparing for factory reset")
                    thirty_second_mark_reached = True
                    self.signal_factory_reset()

                # Button released
                elif current_state == GPIO.HIGH and button_pressed:
                    button_pressed = False
                    duration = time.time() - press_start_time
                    print(f"[Thread {thread_id}] Button released after {duration:.1f} seconds")

                    if thirty_second_mark_reached and not self.factory_reset_triggered:
                        print(f"[Thread {thread_id}] Factory resetting system...")
                        self.factory_reset_triggered = True
                        self.perform_factory_reset()
                    # If we have passed the 10 second mark but not the 30 second mark, reset to setup mode
                    elif ten_second_mark_reached and duration < 30 and not self.setup_mode_triggered:
                        print(f"[Thread {thread_id}] Resetting to setup mode...")
                        self.setup_mode_triggered = True
                        # clear just the api token so we still have the current config to allow editing
                        # the user will just have to re-enter their email/password
                        clear_api_token()
                        self.config.clear_creds_from_config()
                        restart_in_setup_mode()
                    # If we have passed the 2 second mark but not the 10 second mark, reboot
                    elif two_second_mark_reached and duration < 10 and not self.reboot_triggered:
                        print(f"[Thread {thread_id}] Rebooting system...")
                        self.reboot_triggered = True
                        self.reboot_system()

                    two_second_mark_reached = False
                    ten_second_mark_reached = False
                    thirty_second_mark_reached = False

                # Small sleep to prevent CPU hogging
                time.sleep(0.1)

            except Exception as e:
                print(f"[Thread {thread_id}] Error in button polling: {traceback.format_exc()}")
                time.sleep(1)  # Longer sleep on error

        print(f"[Thread {thread_id}] Button polling thread exiting")

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
        elif state == "factory_reset":
            # Very fast blinking pattern for factory reset (10 Hz)
            if self.pwm:
                self.pwm.stop()
            self.pwm = GPIO.PWM(self.LED_PIN, 10)
            self.pwm.start(50)

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

    def signal_factory_reset(self):
        """Visual indication that the system is preparing for factory reset (10 rapid blinks)"""
        if self.module_disabled or self.led_disabled:
            return

        # Stop any current patterns
        self.stop_pattern_thread()

        # Blink 10 times rapidly to indicate factory reset
        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        for _ in range(10):
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(self.LED_PIN, GPIO.LOW)
            time.sleep(0.05)

        # Set to factory reset state (very fast blinking)
        self.set_state("factory_reset")

    def signal_successful_transmission(self):
        """Visual indication that a temperature reading was successfully sent (2 fast blinks)"""
        if self.module_disabled or self.led_disabled:
            return

        # Store the current state
        previous_state = self.current_state

        # Stop any current patterns
        self.stop_pattern_thread()

        # Blink twice very quickly to indicate successful transmission
        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        for _ in range(2):
            GPIO.output(self.LED_PIN, GPIO.HIGH)
            time.sleep(0.05)  # Very short on time (50ms)
            GPIO.output(self.LED_PIN, GPIO.LOW)
            time.sleep(0.05)  # Very short off time (50ms)

        # Restore previous state
        if previous_state:
            self.set_state(previous_state)

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

    def perform_factory_reset(self):
        """Perform a factory reset of the device using the factory-reset.sh script"""
        try:
            print("Performing factory reset...")
            # Set LED to indicate factory reset in progress
            self.set_state("factory_reset")

            # Path to the factory reset script
            script_path = "/home/pi/freezerbot/bin/factory-reset.sh"

            # Check if script exists and is executable
            if not os.path.exists(script_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(os.path.dirname(script_dir), 'bin', "factory-reset.sh")

                if not os.path.exists(script_path):
                    print(f"Factory reset script not found at {script_path}")
                    self.set_state("error")
                    return

            # Make sure the script is executable
            subprocess.run(["/usr/bin/sudo", "/usr/bin/chmod", "+x", script_path], check=True)

            # Run the factory reset script with sudo
            result = subprocess.run(["/usr/bin/sudo", script_path], check=True)

            if result.returncode != 0:
                print(f"Factory reset script failed with exit code {result.returncode}")
                self.set_state("error")
                return

            print("Factory reset completed. Rebooting...")
            self.reboot_system()

        except Exception as e:
            print(f"Error during factory reset: {traceback.format_exc()}")
            self.set_state("error")

    def reboot_system(self):
        """Reboot the system"""
        try:
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/reboot"], check=True)
        except Exception as e:
            print(f"Error rebooting system: {traceback.format_exc()}")

    def cleanup(self):
        """Clean up resources"""
        self.running = False

        if hasattr(self, 'button_thread') and self.button_thread and self.button_thread.is_alive():
            self.button_thread.join(timeout=0.5)

        if self.pwm:
            self.pwm.stop()
            self.pwm = None

        self.stop_pattern_thread()

        try:
            GPIO.cleanup()
        except Exception:
            pass  # Ignore errors during cleanup


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            LedControl().set_state(sys.argv[1])
        except KeyboardInterrupt:
            LedControl().cleanup()
        except Exception as e:
            print(f"Error: {str(e)}")
            try:
                GPIO.cleanup()
            except:
                pass