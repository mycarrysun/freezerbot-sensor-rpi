import os
import time
import json
import traceback

import requests
import RPi.GPIO as GPIO
import subprocess
from led_control import LedControl
from w1thermsensor import W1ThermSensor, NoSensorFoundError
from datetime import datetime
from gpiozero import CPUTemperature

from api import make_api_request, api_token_exists, set_api_token, make_api_request_with_creds
from freezerbot_setup import FreezerBotSetup
from config import Config
from pisugar import PiSugarMonitor


class TemperatureMonitor:
    def __init__(self):
        """Initialize the temperature monitoring application"""
        self.config = Config()
        self.device_info_file = "/home/pi/freezerbot/device_info.json"
        self.consecutive_errors = []

        self.led_control = LedControl()
        self.freezerbot_setup = FreezerBotSetup()
        self.pisugar = PiSugarMonitor()

        self.validate_config()

    def validate_config(self):
        """Check for a valid config file"""
        if not self.config.configuration_exists:
            print("Configuration file not found. Will restart in setup mode.")
            self.freezerbot_setup.restart_in_setup_mode()
            exit(0)
        if not self.config.is_configured:
            print("Configuration file is invalid. Restarting in setup mode.")
            self.freezerbot_setup.restart_in_setup_mode()
            exit(0)

    def obtain_api_token(self):
        if not api_token_exists():
            device_info = {}
            if not os.path.exists(self.device_info_file):
                print("Device info file not found. Continuing.")
            else:
                with open(self.device_info_file, "r") as f:
                    device_info = json.load(f)
            response = make_api_request_with_creds(
                {
                    'email': self.config.config['email'],
                    'password': self.config.config['password'],
                },
                'sensors/configure',
                json={**device_info, **{
                    'name': self.config.config['device_name'],
                    'configured_at': datetime.utcnow().isoformat() + 'Z'
                }}
            )

            if response.status_code == 401 or response.status_code == 403:
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
        print('Reading temperature')
        try:
            sensor = W1ThermSensor()
        except NoSensorFoundError as e:
            make_api_request('sensors/reportError', json={
                'errors': [traceback.format_exc()]
            })
            raise
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
                try:
                    self.obtain_api_token()

                    temperature = self.read_temperature()

                    payload = {
                        "degrees_c": temperature,
                        "cpu_degrees_c": CPUTemperature().temperature,
                        "taken_at": datetime.utcnow().isoformat() + 'Z',
                        'battery_level': self.pisugar.get_battery_level(),
                        'battery_amps': self.pisugar.get_current(),
                        'battery_volts': self.pisugar.get_voltage(),
                        'is_charging': self.pisugar.is_charging(),
                        'is_plugged_in': self.pisugar.is_power_plugged(),
                        'is_allowed_to_charge': self.pisugar.is_charging_allowed()
                    }

                    response = make_api_request('sensors/readings', json=payload)

                    if response.status_code == 201:
                        print('Successfully sent reading')
                        self.consecutive_errors = []
                        self.led_control.set_state('running')
                    else:
                        self.led_control.set_state("error")
                        self.consecutive_errors.append(f'API error: {response.status_code} - {response.text}')

                except requests.exceptions.RequestException as e:
                    # Network error
                    print(f"Network error sending data: {str(e)}")
                    self.led_control.set_state("wifi_issue")
                    self.consecutive_errors.append(traceback.format_exc())
                except Exception as e:
                    print(f"Error sending data: {str(e)}")
                    self.led_control.set_state("error")
                    self.consecutive_errors.append(traceback.format_exc())

                if len(self.consecutive_errors) > 0:
                    print(f'Consecutive errors: {len(self.consecutive_errors)}')
                    print("\n\n".join(self.consecutive_errors))
                    self.report_consecutive_errors()

                time.sleep(60)

            except Exception as e:
                print(f"Error in main loop: {traceback.format_exc()}")
                self.consecutive_errors.append(traceback.format_exc())
                self.led_control.set_state("error")
                self.report_consecutive_errors()
                time.sleep(5)

                # Switch back to appropriate state based on connectivity
                if self.connected_to_wifi():
                    self.led_control.set_state("running")
                else:
                    self.led_control.set_state("wifi_issue")

                # Still wait before next attempt
                time.sleep(30)

    def report_consecutive_errors(self):
        response = make_api_request('sensors/reportError', json={
            'errors': self.consecutive_errors
        })

        if response.status_code == 200:
            self.consecutive_errors = []

    def cleanup(self):
        """Clean up GPIO on exit"""
        self.led_control.cleanup()
        GPIO.cleanup()


# Main entry point when run directly
if __name__ == "__main__":
    try:
        monitor = TemperatureMonitor()
        monitor.led_control.set_state('running')
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