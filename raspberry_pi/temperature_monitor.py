import os
import time
import json
import requests
import RPi.GPIO as GPIO
import subprocess
from led_control import LedControl
from w1thermsensor import W1ThermSensor
from datetime import datetime

from raspberry_pi.api import make_api_request


class TemperatureMonitor:
    def __init__(self):
        """Initialize the temperature monitoring application"""
        self.config_file = "/home/pi/freezerbot/config.json"
        self.network_failure_count = 0
        self.consecutive_errors = []
        self.config = None

        self.led_control = LedControl()

        self.led_control.set_state("running")

        self.load_configuration()

    def load_configuration(self):
        """Load the configuration file"""
        if not os.path.exists(self.config_file):
            print("Configuration file not found. Will restart in setup mode.")
            self.restart_in_setup_mode()
            return False

        with open(self.config_file, "r") as f:
            self.config = json.load(f)
        return True

    def restart_in_setup_mode(self):
        """Remove config and restart in setup mode - only used when button is explicitly held"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

        self.led_control.set_state("reset")
        time.sleep(2)
        subprocess.Popen(["systemctl", "disable", "freezerbot-monitor.service"])
        subprocess.Popen(["systemctl", "enable", "freezerbot-setup.service"])
        subprocess.Popen(["systemctl", "start", "freezerbot-setup.service"])

    def read_temperature(self):
        """Read temperature from sensor"""
        sensor = W1ThermSensor()
        degrees_c = sensor.get_temperature()
        return degrees_c

    def connected_to_wifi(self):
        nm_status = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "DEVICE,STATE", "device", "status"],
            capture_output=True, text=True
        ).stdout.strip()

        return 'wlan0:connected' in nm_status

    def send_temperature(self, temperature):
        """Send temperature reading to API"""
        try:
            payload = {
                "degrees_c": temperature,
                "timestamp": datetime.utcnow().isoformat()+'Z'
            }

            response = make_api_request('sensors/readings', json=payload)

            if response.status_code != 201:
                print(f"API error: {response.status_code} - {response.text}")
                self.led_control.set_state("error")
                return False

            return True
        except requests.exceptions.RequestException as e:
            # Network error
            print(f"Network error sending data: {str(e)}")
            self.led_control.set_state("wifi_issue")
            return False
        except Exception as e:
            print(f"Error sending data: {str(e)}")
            self.led_control.set_state("error")

            return False

    def run(self):
        """Main monitoring loop with resilient error handling"""
        print("Starting temperature monitoring")

        # Initial configuration and connection attempt
        if self.load_configuration():
            self.led_control.set_state("running")
        else:
            print("No valid configuration found. Will continue monitoring with default settings.")
            self.led_control.set_state("error")

        # Main monitoring loop - continue indefinitely
        while True:
            try:
                temperature = self.read_temperature()

                try:
                    payload = {
                        "degrees_c": temperature,
                        "timestamp": datetime.utcnow().isoformat() + 'Z'
                    }

                    response = make_api_request('sensors/readings', json=payload)

                    if response.status_code == 201:
                        self.consecutive_errors = []
                    else:
                        self.led_control.set_state("error")
                        self.consecutive_errors.append(f'API error: {response.status_code} - {response.text}')

                except requests.exceptions.RequestException as e:
                    # Network error
                    print(f"Network error sending data: {str(e)}")
                    self.led_control.set_state("wifi_issue")
                    self.consecutive_errors.append(str(e))
                except Exception as e:
                    print(f"Error sending data: {str(e)}")
                    self.led_control.set_state("error")
                    self.consecutive_errors.append(str(e))

                if len(self.consecutive_errors) > 0:
                    response = make_api_request('sensors/errors', json={
                        'errors': self.consecutive_errors
                    })

                    if response.status_code == 200:
                        self.consecutive_errors = []

                time.sleep(60)

            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                self.consecutive_errors += 1
                self.led_control.set_state("error")
                time.sleep(5)

                # Switch back to appropriate state based on connectivity
                if self.connected_to_wifi:
                    self.led_control.set_state("running")
                else:
                    self.led_control.set_state("wifi_issue")

                # Still wait before next attempt
                time.sleep(30)

    def cleanup(self):
        """Clean up GPIO on exit"""
        self.led_control.cleanup()
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
        print(f"Error in monitoring initialization: {str(e)}")
        # Try to clean up GPIO
        try:
            GPIO.cleanup()
        except:
            pass