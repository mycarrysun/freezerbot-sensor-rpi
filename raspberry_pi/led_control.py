import RPi.GPIO as GPIO
import time
import sys

LED_PIN = 27


def setup_led():
    """Configure GPIO for the button's built-in LED"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LED_PIN, GPIO.OUT)
    return GPIO.PWM(LED_PIN, 1)  # Default 1 Hz


def set_led_mode(mode):
    """Set the LED to different patterns based on mode"""
    pwm = setup_led()

    if mode == "setup":
        # Blinking blue in setup mode (1 Hz)
        pwm.start(50)
        while True:
            time.sleep(1)
    elif mode == "running":
        # Solid on in normal operation
        GPIO.output(LED_PIN, GPIO.HIGH)
        while True:
            time.sleep(1)
    elif mode == "error":
        # Fast blinking in error state (5 Hz)
        pwm.ChangeFrequency(5)
        pwm.start(50)
        while True:
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            set_led_mode(sys.argv[1])
        except KeyboardInterrupt:
            GPIO.cleanup()
        except Exception as e:
            print(f"Error: {str(e)}")
            GPIO.cleanup()