import os
import time
import json
import requests
import RPi.GPIO as GPIO
import subprocess
from gpiozero import CPUTemperature


class TemperatureMonitor:
    def __init__(self):
        """Initialize the temperature monitoring application"""
        self.config_file = "/home/pi/freezerbot/config.json"
        self.BUTTON_PIN = 17
        self.LED_PIN = 27
        self.API_ENDPOINT = "https://api.freezerbot.com/v1/readings"
        self.SENSOR_PIN = 4  # GPIO pin for temperature sensor

        # Read configuration
        if not os.path.exists(self.config_file):
            print("Configuration file not found. Please run setup.")
            self.restart_in_setup_mode()
            return

        with open(self.config_file, "r") as f:
            self.config = json.load(f)

        # Setup GPIO
        self.setup_gpio()

        # Set LED to running state
        self.set_led_state("running")

    def setup_gpio(self):
        """Configure GPIO pins for button with built-in LED"""
        GPIO.setmode(GPIO.BCM)

        # Setup button with pull-up resistor
        GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.BUTTON_PIN, GPIO.FALLING,
                              callback=self.button_pressed_callback,
                              bouncetime=300)

        # Setup the button's built-in LED
        GPIO.setup(self.LED_PIN, GPIO.OUT)

    def button_pressed_callback(self, channel):
        """Handle button press events"""
        # Check how long the button is held
        start_time = time.time()
        while GPIO.input(self.BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.1)
            if time.time() - start_time > 10:  # 10-second hold
                self.restart_in_setup_mode()
                break

    def restart_in_setup_mode(self):
        """Remove config and restart in setup mode"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

        self.set_led_state("reset")
        time.sleep(2)
        subprocess.Popen(["sudo", "systemctl", "disable", "freezerbot-monitor.service"])
        subprocess.Popen(["sudo", "systemctl", "enable", "freezerbot-setup.service"])
        subprocess.Popen(["sudo", "reboot"], shell=True)

    def set_led_state(self, state):
        """Set the LED state"""
        if state == "running":
            GPIO.output(self.LED_PIN, GPIO.HIGH)
        elif state == "error":
            # Use PWM for blinking in error state
            self.led_pwm = GPIO.PWM(self.LED_PIN, 5)
            self.led_pwm.start(50)
        elif state == "reset":
            # Three quick flashes
            for _ in range(3):
                GPIO.output(self.LED_PIN, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(self.LED_PIN, GPIO.LOW)
                time.sleep(0.2)

    def read_temperature(self):
        """Read temperature from sensor"""
        # This is a placeholder - replace with your actual sensor code
        # For example, if using DS18B20:
        try:
            # For demo, using CPU temp as a stand-in for real sensor
            # In production, replace with actual sensor code
            cpu = CPUTemperature()
            return round(cpu.temperature, 1)
        except Exception as e:
            print(f"Error reading temperature: {str(e)}")
            return None

    def send_temperature(self, temperature):
        """Send temperature reading to API"""
        try:
            payload = {
                "freezer_name": self.config.get("freezer_name", "Unnamed Freezer"),
                "temperature": temperature,
                "timestamp": time.time()
            }

            response = requests.post(
                self.API_ENDPOINT,
                headers={"Authorization": f"Bearer {self.config['api_token']}"},
                json=payload
            )

            if response.status_code != 200:
                print(f"API error: {response.status_code} - {response.text}")
                self.set_led_state("error")
                time.sleep(5)  # Show error state briefly
                self.set_led_state("running")
                return False

            return True
        except Exception as e:
            print(f"Error sending data: {str(e)}")
            self.set_led_state("error")
            time.sleep(5)  # Show error state briefly
            self.set_led_state("running")
            return False

    def run(self):
        """Main monitoring loop"""
        print(f"Starting temperature monitoring for {self.config.get('freezer_name', 'Unnamed Freezer')}")

        while True:
            # Read temperature
            temperature = self.read_temperature()

            # Send to API if reading successful
            if temperature is not None:
                self.send_temperature(temperature)

            # Wait for next reading (60 seconds)
            time.sleep(60)

    def cleanup(self):
        """Clean up GPIO on exit"""
        GPIO.cleanup()


# Main entry point when run directly
if __name__ == "__main__":
    try:
        monitor = TemperatureMonitor()
        monitor.run()
    except KeyboardInterrupt:
        monitor.cleanup()
        print("Monitoring terminated by user")
    except Exception as e:
        print(f"Error in monitoring: {str(e)}")
        # Try to clean up GPIO
        try:
            GPIO.cleanup()
        except:
            pass