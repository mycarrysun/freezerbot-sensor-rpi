import os
import time
import subprocess
import json
import requests
import RPi.GPIO as GPIO
from flask import Flask, request, render_template, redirect, jsonify


class FreezerBotSetup:
    def __init__(self):
        """Initialize the FreezerBot setup application"""
        # Configuration paths
        self.config_file = "/home/pi/freezerbot/config.json"
        self.is_configured = os.path.exists(self.config_file)

        # Set up GPIO for button with built-in LED
        self.BUTTON_PIN = 17  # GPIO pin for the reset button
        self.LED_PIN = 27  # GPIO pin for the button's built-in LED
        self.setup_gpio()

        # Initialize Flask application
        self.app = Flask(__name__,
                         static_url_path='',
                         static_folder='static',
                         template_folder='templates')
        self.setup_routes()

    def setup_gpio(self):
        """Configure GPIO pins for button and built-in LED"""
        GPIO.setmode(GPIO.BCM)

        # Setup button with pull-up resistor
        GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(self.BUTTON_PIN, GPIO.FALLING,
                              callback=self.button_pressed_callback,
                              bouncetime=300)

        # Setup the button's built-in LED
        GPIO.setup(self.LED_PIN, GPIO.OUT)
        self.led_pwm = GPIO.PWM(self.LED_PIN, 1)  # 1 Hz for blinking

    def button_pressed_callback(self, channel):
        """Handle button press events"""
        # Check how long the button is held
        start_time = time.time()
        while GPIO.input(self.BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.1)
            if time.time() - start_time > 10:  # 10-second hold
                self.reset_configuration()
                break

    def reset_configuration(self):
        """Reset the device to setup mode"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        self.set_led_state("reset")
        time.sleep(2)  # Give user visual feedback
        subprocess.Popen(["sudo", "reboot"], shell=True)

    def setup_routes(self):
        """Set up the web routes for the configuration portal"""
        self.app.route("/")(self.index)
        self.app.route("/api/scan-wifi")(self.scan_wifi)
        self.app.route("/api/setup", methods=["POST"])(self.save_config)

        # Special routes for captive portal detection
        self.app.route("/generate_204")(self.captive_portal_redirect)
        self.app.route("/ncsi.txt")(self.captive_portal_redirect)
        self.app.route("/hotspot-detect.html")(self.captive_portal_redirect)
        self.app.route("/success.txt")(self.captive_portal_redirect)
        self.app.route("/connecttest.txt")(self.captive_portal_redirect)

    def index(self):
        """Serve the main Vue application"""
        return render_template('index.html')

    def scan_wifi(self):
        """Scan for available WiFi networks and return as JSON"""
        try:
            result = subprocess.run(["sudo", "iwlist", "wlan0", "scan"],
                                    capture_output=True, text=True)

            networks = []
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    ssid = line.split('ESSID:"')[1].split('"')[0]
                    if ssid and ssid not in networks:
                        networks.append(ssid)

            return jsonify({"networks": networks})
        except Exception as e:
            return jsonify({"error": str(e), "networks": []})

    def save_config(self):
        """Process and save the configuration"""
        try:
            # Get JSON data
            data = request.json
            wifi_ssid = data.get('wifi_ssid')
            wifi_password = data.get('wifi_password')
            api_token = data.get('api_token')
            freezer_name = data.get('freezer_name', 'Unnamed Freezer')

            # Validate inputs
            if not wifi_ssid or not wifi_password or not api_token:
                return jsonify({"success": False, "error": "All fields are required"})

            # Test WiFi connection
            if not self.test_wifi_connection(wifi_ssid, wifi_password):
                return jsonify({"success": False,
                                "error": "Could not connect to WiFi. Please check your network name and password"})

            # Test API token
            if not self.test_api_token(api_token):
                return jsonify({"success": False, "error": "Invalid API token. Please check your token"})

            # Save configuration
            config = {
                "wifi_ssid": wifi_ssid,
                "wifi_password": wifi_password,
                "api_token": api_token,
                "freezer_name": freezer_name
            }

            with open(self.config_file, "w") as f:
                json.dump(config, f)

            # Schedule restart
            subprocess.Popen(["sudo", "systemctl", "enable", "freezerbot-monitor.service"])
            subprocess.Popen(["sudo", "systemctl", "disable", "freezerbot-setup.service"])
            subprocess.Popen(["sleep", "10", "&&", "sudo", "reboot"], shell=True)

            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    def captive_portal_redirect(self):
        """Redirect captive portal detection requests to the setup page"""
        return redirect("/")

    def test_wifi_connection(self, ssid, password):
        """Test connecting to the provided WiFi network"""
        try:
            # Create a temporary wpa_supplicant configuration
            wpa_config = f"""
            network={{
                ssid="{ssid}"
                psk="{password}"
            }}
            """

            with open("/tmp/wpa_test.conf", "w") as f:
                f.write(wpa_config)

            # Try to connect
            subprocess.run(["sudo", "systemctl", "stop", "hostapd", "dnsmasq"])
            subprocess.run(["sudo", "wpa_supplicant", "-i", "wlan0", "-c", "/tmp/wpa_test.conf", "-B"])

            time.sleep(5)

            result = subprocess.run(["iwconfig", "wlan0"], capture_output=True, text=True)
            connected = ssid in result.stdout

            subprocess.run(["sudo", "killall", "wpa_supplicant"])
            subprocess.run(["sudo", "systemctl", "start", "hostapd", "dnsmasq"])

            return connected
        except Exception:
            subprocess.run(["sudo", "systemctl", "start", "hostapd", "dnsmasq"])
            return False

    def test_api_token(self, token):
        """Test the API token with the Freezerbot server"""
        try:
            response = requests.post(
                "https://api.freezerbot.com/v1/devices/verify",
                headers={"Authorization": f"Bearer {token}"},
                json={"device_type": "rpi-zero-w"}
            )
            return response.status_code == 200
        except Exception:
            return False

    def start_hotspot(self):
        """Start the WiFi hotspot for configuration"""
        # Get the device serial for a unique hotspot name
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
            serial = [line.split(":")[-1].strip() for line in cpuinfo.split("\n") if "Serial" in line][0][-4:]
        except:
            serial = "0000"

        hotspot_name = f"Freezerbot-Setup-{serial}"

        # Configure the hostapd.conf file
        hostapd_config = f"""
        interface=wlan0
        driver=nl80211
        ssid={hotspot_name}
        hw_mode=g
        channel=7
        wmm_enabled=0
        macaddr_acl=0
        auth_algs=1
        ignore_broadcast_ssid=0
        """

        with open("/etc/hostapd/hostapd.conf", "w") as f:
            f.write(hostapd_config)

        # Configure dnsmasq for DHCP
        dnsmasq_config = """
        interface=wlan0
        dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
        address=/#/192.168.4.1
        """

        with open("/etc/dnsmasq.conf", "w") as f:
            f.write(dnsmasq_config)

        # Configure static IP
        subprocess.run(["sudo", "ifconfig", "wlan0", "192.168.4.1", "netmask", "255.255.255.0"])

        # Start services
        subprocess.run(["sudo", "systemctl", "start", "hostapd", "dnsmasq"])

    def set_led_state(self, state):
        """Control the status LED"""
        self.led_pwm.stop()

        if state == "setup":
            # Blinking blue (simulate with on/off pattern)
            self.led_pwm.start(50)  # 50% duty cycle - half on, half off
        elif state == "running":
            # Solid on
            GPIO.output(self.LED_PIN, GPIO.HIGH)
        elif state == "error":
            # Fast blinking
            self.led_pwm = GPIO.PWM(self.LED_PIN, 5)  # 5 Hz for faster blinking
            self.led_pwm.start(50)
        elif state == "reset":
            # Three quick flashes
            for _ in range(3):
                GPIO.output(self.LED_PIN, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(self.LED_PIN, GPIO.LOW)
                time.sleep(0.2)

    def run(self):
        """Main entry point"""
        if not self.is_configured:
            # Start in setup mode
            self.start_hotspot()
            # Set LED to blinking
            self.set_led_state("setup")
            # Start the web server
            self.app.run(host="0.0.0.0", port=80)
        else:
            # Already configured, exit
            print("Device already configured, exiting setup mode")

    def cleanup(self):
        """Clean up GPIO on exit"""
        GPIO.cleanup()


# Main entry point when run directly
if __name__ == "__main__":
    try:
        setup = FreezerBotSetup()
        setup.run()
    except KeyboardInterrupt:
        setup.cleanup()
        print("Setup terminated by user")
    except Exception as e:
        print(f"Error in setup: {str(e)}")
        # Try to clean up GPIO
        try:
            GPIO.cleanup()
        except:
            pass