import os
import time
import json
import traceback
from pydoc import classname

import RPi.GPIO as GPIO
import subprocess
from led_control import LedControl
from w1thermsensor import W1ThermSensor, NoSensorFoundError, SensorNotReadyError
from datetime import datetime
from gpiozero import CPUTemperature

from api import make_api_request, api_token_exists, set_api_token, make_api_request_with_creds
from freezerbot_setup import FreezerBotSetup
from config import Config
from battery import PiSugarMonitor
from network import test_internet_connectivity, load_network_status, save_network_status, reset_network_status
from device_info import DeviceInfo
from restarts import restart_in_setup_mode


class TemperatureMonitor:
    def __init__(self):
        """Initialize the temperature monitoring application"""
        self.config = Config()
        self.consecutive_errors = []

        self.led_control = LedControl()
        self.freezerbot_setup = FreezerBotSetup()
        self.pisugar = PiSugarMonitor()
        self.device_info = DeviceInfo()
        self.sensor = None
        self.consecutive_sensor_errors = 0
        self.max_errors_before_sensor_reset = 3

        self.validate_config()

    def validate_config(self):
        """Check for a valid config file"""
        if not self.config.configuration_exists:
            print("Configuration file not found. Will restart in setup mode.")
            restart_in_setup_mode()
            exit(0)
        if not self.config.is_configured:
            print("Configuration file is invalid. Restarting in setup mode.")
            restart_in_setup_mode()
            exit(0)

    def obtain_api_token(self):
        if not api_token_exists():
            response = make_api_request_with_creds(
                {
                    'email': self.config.config['email'],
                    'password': self.config.config['password'],
                },
                'sensors/configure',
                json={**self.device_info.device_info, **{
                    'name': self.config.config['device_name'],
                    'configured_at': datetime.utcnow().isoformat() + 'Z'
                }}
            )

            if response.status_code == 401 or response.status_code == 403:
                print('Deleting email and password and restarting in setup mode')
                self.config.add_config_error('Email or password is incorrect. Please provide the email and password you use to login to the Freezerbot app.')
                self.config.clear_creds_from_config()
                restart_in_setup_mode()
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
        """Read temperature with escalating recovery methods"""
        print('Reading temperature')

        if self.sensor is None:
            try:
                self.sensor = W1ThermSensor()
            except Exception as e:
                self.consecutive_errors.append(f'Error creating sensor instance: {traceback.format_exc()}')
                raise

        if self.consecutive_sensor_errors >= self.max_errors_before_sensor_reset:
            print(f"Resetting 1-Wire modules after {self.consecutive_sensor_errors} failures")
            try:
                subprocess.run(["/usr/sbin/modprobe", "-r", "w1_gpio", "w1_therm"])
                time.sleep(1)
                subprocess.run(["/usr/sbin/modprobe", "w1_gpio", "w1_therm"])
                time.sleep(2)  # Give system time to detect sensors

                self.sensor = W1ThermSensor()
            except Exception as e:
                self.consecutive_errors.append(f"Error after module reset: {traceback.format_exc()}")
                raise

        if self.sensor is not None:
            try:
                temperature = self.sensor.get_temperature()
                self.consecutive_sensor_errors = 0
                return temperature
            except Exception as e:
                self.consecutive_sensor_errors += 1
                self.consecutive_errors.append(f"Error reading from existing sensor: {traceback.format_exc()}")
                raise

    def run(self):
        """Main monitoring loop with resilient error handling"""
        print("Starting temperature monitoring")

        network_status = load_network_status()
        network_failure_count = network_status.get('network_failure_count', 0)
        reboot_count = network_status.get('reboot_count', 0)
        recovery_attempted = False
        api_failure_count = 0

        print(f"Starting with network_failure_count: {network_failure_count}, reboot_count: {reboot_count}")

        # Main monitoring loop - continue indefinitely
        while True:
            try:
                # Test actual internet connectivity, not just WiFi connection
                internet_connected = test_internet_connectivity()

                if not internet_connected:
                    self.led_control.set_state("wifi_issue")
                    network_failure_count += 1

                    # Save updated failure count immediately
                    network_status['network_failure_count'] = network_failure_count
                    save_network_status(network_status)

                    print(f"Network failure #{network_failure_count}, reboot_count: {reboot_count}")

                    # Network recovery logic with escalating actions
                    if network_failure_count >= 3 and not recovery_attempted:
                        print("Attempting network recovery by restarting NetworkManager")
                        subprocess.run(["/usr/bin/systemctl", "restart", "NetworkManager.service"])
                        recovery_attempted = True
                    elif network_failure_count >= 10 and reboot_count < 2:
                        print(
                            f"Critical network failure (failure: {network_failure_count}, reboots: {reboot_count}), performing system reboot")
                        # Increment reboot count before reboot
                        reboot_count += 1
                        network_status['reboot_count'] = reboot_count
                        save_network_status(network_status)

                        # Report critical network failure to API if possible
                        try:
                            self.consecutive_errors.append(
                                f"Critical network failure triggering reboot #{reboot_count}. Total failures: {network_failure_count}")
                            self.report_consecutive_errors()
                        except Exception:
                            print("Failed to report network failure before reboot")

                        subprocess.run(["/usr/bin/systemctl", "reboot", "-i"])
                    elif network_failure_count >= 10 and reboot_count >= 2:
                        print(
                            f"Excessive network failures ({network_failure_count}) after {reboot_count} reboots. Continuing to monitor without further reboots.")
                        # Add to consecutive errors but don't reboot
                        if len(self.consecutive_errors) == 0 or "Excessive network failures" not in \
                                self.consecutive_errors[-1]:
                            self.consecutive_errors.append(
                                f"Excessive network failures ({network_failure_count}) after {reboot_count} reboots. Continuing without further reboots.")

                    continue

                # Reset network failure counter if we have internet
                if network_failure_count > 0:
                    print(
                        f"Network connectivity restored after {network_failure_count} failures and {reboot_count} reboots")
                    network_failure_count = 0
                    reboot_count = 0
                    reset_network_status()

                recovery_attempted = False

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
                        self.led_control.signal_successful_transmission()
                        self.led_control.set_state('running')
                        self.report_consecutive_errors()
                        api_failure_count = 0
                        response_json = response.json()
                        possible_name = response_json.get('name')
                        if possible_name and self.config.config['device_name'] != possible_name:
                            self.config.save_device_name(possible_name)
                    else:
                        api_failure_count += 1
                        self.consecutive_errors.append(f'API error: {response.status_code} - {response.text}')

                        # Only change LED state after persistent API failures
                        if api_failure_count >= 3:
                            self.led_control.set_state("error")

                except Exception as e:
                    print(f"Error in API communication: {traceback.format_exc()}")
                    self.consecutive_errors.append(traceback.format_exc())
                    api_failure_count += 1

                    # Only change LED state after persistent API failures
                    if api_failure_count >= 3:
                        self.led_control.set_state("error")

                if len(self.consecutive_errors) > 0:
                    self.report_consecutive_errors()

            except Exception as e:
                print(f"Error in main loop: {traceback.format_exc()}")
                self.consecutive_errors.append(traceback.format_exc())
                self.led_control.set_state("error")
                try:
                    self.report_consecutive_errors()
                except Exception:
                    print(f'Error when sending logs: {traceback.format_exc()}')

            finally:
                time.sleep(60)

    def report_consecutive_errors(self):
        if len(self.consecutive_errors) > 0:
            response = make_api_request('sensors/errors', json={
                'errors': self.consecutive_errors
            })

            if response.status_code == 200:
                self.consecutive_errors = []
            else:
                print(f'Error reporting errors: {response.status_code} - {response.text}')

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