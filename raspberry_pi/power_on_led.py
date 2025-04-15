import RPi.GPIO as GPIO
from led_control import LED_PIN

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# Turn on the LED
GPIO.output(LED_PIN, GPIO.HIGH)

# Don't cleanup so the LED stays on
# The LED control will be taken over by the main application when it starts
# which will reset the GPIO mode and settings
