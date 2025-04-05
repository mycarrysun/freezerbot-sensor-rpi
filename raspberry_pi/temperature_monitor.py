import os
import time
import json
import requests
import RPi.GPIO as GPIO
import subprocess
from led_control import LedControl
from w1thermsensor import W1ThermSensor
from datetime import datetime
from gpiozero import CPUTemperature

from api import make_api_request, api_token_exists, set_api_token, make_api_request_with_creds
from freezerbot_setup import FreezerBotSetup
from config import Config


class TemperatureMonitor:
    def __init__(self):
        """Initialize the temperature monitoring application"""
        self.config = Config()
        self.device_info_file = "/home/pi/freezerbot/device_info.json"
        self.consecutive_errors = []

        self.led_control = LedControl()
        self.freezerbot_setup = FreezerBotSetup()

        self.validate_config()

    def validate_config(self):
        """Check for a valid config file"""
        if not self.config.configuration_exists:
            print("Configuration file not found. Will restart in setup mode.")
            self.freezerbot_setup.restart_in_setup_mode()
            return
        if not self.config.is_configured:
            print("Configuration file is invalid. Restarting in setup mode.")
            self.freezerbot_setup.restart_in_setup_mode()
            return

    def obtain_api_token(self):
        if not api_token_exists():
            device_info = {}
            if not os.path.exists(self.device_info_file):
                print("Device info file not found. Continuing.")
            else:
                with open(self.device_info_file, "r") as f:
                    device_info = json.load(f)
            response = make_api_request_with_creds({
                'email': self.config.config['email'],
                'password': self.config.config['password'],
            }, 'sensors/configure', {**device_info, **{
                'name': self.config.config['device_name'],
                'configured_at': datetime.utcnow().isoformat() + 'Z'
            }})

            if response.status_code == 401:
                print('Deleting email and password and restarting in setup mode')
                self.config.add_config_error('Email or password is incorrect. Please provide the email and password you use to login to the Freezerbot app.')
                self.config.clear_creds_from_config()
                self.freezerbot_setup.restart_in_setup_mode()
            elif response.status_code != 201:
                print(f'Error obtaining token: {response.status_code} {response.text}')
            else:
                print('Saving api token')
                data = response.json()
                if 'token' in data:
                    set_api_token(data['token'])
                    self.config.clear_creds_from_config()
                else:
                    print(f'No token in response: {data}')
                    self.led_control.set_state('error')

        else:
            print('Api already token exists')


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

    def run(self):
        """Main monitoring loop with resilient error handling"""
        print("Starting temperature monitoring")

        self.led_control.set_state("running")

        # Main monitoring loop - continue indefinitely
        while True:
            try:
                self.obtain_api_token()

                temperature = self.read_temperature()

                try:
                    payload = {
                        "degrees_c": temperature,
                        "cpu_degrees_c": CPUTemperature().temperature,
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
                self.consecutive_errors.append(str(e))
                self.led_control.set_state("error")
                time.sleep(5)

                # Switch back to appropriate state based on connectivity
                if self.connected_to_wifi():
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