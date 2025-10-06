import subprocess
import threading
import time
import traceback
from time import sleep

import RPi.GPIO as GPIO
from flask import Flask, request, render_template, redirect, jsonify

from config import Config, clear_nm_connections
from led_control import LedControl
from restarts import restart_in_sensor_mode
from lcd_control import DisplayControl
from battery import PiSugarMonitor


class FreezerBotSetup:
    def __init__(self):
        """Initialize the FreezerBot setup application"""
        # Configuration paths
        self.config = Config()

        # Initialize LED control
        self.led_control = LedControl()

        # Initialize OLED display and battery monitor (safe no-op if hardware unavailable)
        self.display_control = DisplayControl()
        self.pisugar = PiSugarMonitor()

        # Initialize Flask application
        self.app = Flask(__name__,
                         static_url_path='',
                         static_folder='static',
                         template_folder='templates')
        self.setup_routes()

    def setup_routes(self):
        """Set up the web routes for the configuration portal"""
        self.app.route("/")(self.index)
        self.app.route("/api/scan-wifi")(self.scan_wifi)
        self.app.route("/api/get-config")(self.get_current_config)
        self.app.route("/api/setup", methods=["POST"])(self.save_config)
        self.app.route('/api/create-account', methods=['POST'])(self.create_account)

        # Special routes for captive portal detection
        self.app.route("/generate_204")(self.captive_portal_redirect)
        self.app.route("/ncsi.txt")(self.captive_portal_redirect)
        self.app.route("/hotspot-detect.html")(self.captive_portal_redirect)
        self.app.route("/success.txt")(self.captive_portal_redirect)
        self.app.route("/connecttest.txt")(self.captive_portal_redirect)

    def index(self):
        """Serve the main Vue application"""
        return render_template('index.html')

    def get_current_config(self):
        return jsonify(self.config.config)

    def create_account(self):
        # we need to do a quick disconnect so the user can have an internet connection to create their account
        subprocess.run(["/usr/bin/systemctl", "stop", "hostapd.service"])
        sleep(5)
        subprocess.run(["/usr/bin/systemctl", "start", "hostapd.service"])
        return jsonify({'success': True})

    def scan_wifi(self):
        """Scan for available WiFi networks and return as JSON"""
        try:
            result = subprocess.run(["/usr/sbin/iwlist", "wlan0", "scan"],
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
        """Process and save the configuration with multiple WiFi networks"""
        try:
            # Get JSON data
            data = request.json
            networks = data.get('networks', [])
            email = data.get('email')
            password = data.get('password')
            device_name = data.get('device_name')

            # Validate inputs
            if not networks or not any(network.get('ssid') and network.get('password') for network in networks):
                return jsonify({
                    "success": False,
                    "error": "At least one WiFi network with SSID and password is required"
                })

            if not email:
                return jsonify({"success": False, "error": "Email is required"})

            if not password:
                return jsonify({"success": False, "error": "Password is required"})

            if not device_name:
                return jsonify({'success': False, 'error': 'Sensor name is required'})

            # Save configuration
            config = {
                "networks": networks,
                "email": email,
                "password": password,
                "device_name": device_name
            }

            self.config.save_new_config(config)

            self.setup_network_manager(networks)

            restart_thread = threading.Thread(
                target=self.delayed_restart,
                daemon=True
            )
            restart_thread.start()

            return jsonify({"success": True})
        except Exception as e:
            self.led_control.set_state('error')
            return jsonify({"success": False, "error": str(e)})

    def delayed_restart(self):
        """Restart in sensor mode after a delay to allow frontend to show countdown"""
        try:
            # Wait for the countdown to complete (10 seconds)
            time.sleep(10)

            # Then restart in sensor mode
            restart_in_sensor_mode()
        except Exception as e:
            print(f"Error during delayed restart: {traceback.format_exc()}")
            self.led_control.set_state('error')

    def captive_portal_redirect(self):
        """Redirect captive portal detection requests to the setup page"""
        return redirect("/")

    def setup_network_manager(self, networks):
        """Configure NetworkManager with multiple WiFi networks"""
        # Dictionary of known enterprise networks and their configs
        enterprise_defaults = {
        }

        # Delete all existing WiFi connections
        clear_nm_connections()

        for i, network in enumerate(networks):
            ssid = network.get('ssid')
            password = network.get('password')

            if not ssid or not password:
                continue

            priority = len(networks) - i

            # Check if this is an enterprise network
            if network.get('enterprise', False):
                username = network.get('username', '')
                if not username:
                    print(f"Skipping enterprise network {ssid}: username required")
                    continue

                # Get default settings for known networks, or use defaults
                network_defaults = enterprise_defaults.get(ssid.lower(), {
                    'eap_method': 'peap',
                    'phase2_auth': 'mschapv2'
                })

                eap_method = network.get('eap_method', network_defaults['eap_method'])
                phase2_auth = network.get('phase2_auth', network_defaults['phase2_auth'])

                print(f"Adding enterprise WiFi network: {ssid}")

                # Identify if CA cert is needed and where it should be installed
                ca_cert_path = "/etc/ssl/certs/ca-certificates.crt"
                ca_cert_contents = network.get('ca_cert_content', None)
                if ca_cert_contents is not None:
                    ca_cert_path = '/etc/ssl/certs/freezerbot-' + ssid.replace(' ', '-') + '.crt'
                    with open(ca_cert_path, 'w') as file:
                        file.write(ca_cert_contents)

                # Build the nmcli command for enterprise WiFi
                enterprise_cmd = [
                    "/usr/bin/nmcli", "connection", "add",
                    "type", "wifi",
                    "con-name", ssid,
                    "ifname", "wlan0",
                    "ssid", ssid,
                    "wifi-sec.key-mgmt", "wpa-eap"
                ]

                # Add 802.1x settings
                enterprise_cmd.extend([
                    "802-1x.eap", eap_method,
                    "802-1x.phase2-auth", phase2_auth,
                    "802-1x.identity", username,
                    "802-1x.password", password
                ])

                # Add CA cert if available
                if ca_cert_path:
                    enterprise_cmd.extend(["802-1x.ca-cert", ca_cert_path])

                # Add autoconnect settings
                enterprise_cmd.extend([
                    "autoconnect", "yes",
                ])

                # Execute the command
                subprocess.run(enterprise_cmd)

            else:
                # Regular WPA-PSK network configuration
                print(f"Adding regular WiFi network: {ssid}")
                subprocess.run([
                    "/usr/bin/nmcli", "connection", "add",
                    "type", "wifi",
                    "con-name", ssid,
                    "ifname", "wlan0",
                    "ssid", ssid,
                    "wifi-sec.key-mgmt", "wpa-psk",
                    "wifi-sec.psk", password,
                    "autoconnect", "yes"
                ])

            # Enable all advanced connection settings for better reliability
            subprocess.run([
                "/usr/bin/nmcli", "connection", "modify", ssid,
                "connection.autoconnect-retries", "10",  # Retry connection up to 10 times
                "ipv4.dhcp-timeout", "60",  # Longer DHCP timeout
                "ipv4.route-metric", "100"  # Lower metric = higher priority route
            ])

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

        # Tell NetworkManager to release the wlan0 interface temporarily
        subprocess.run(["/usr/bin/nmcli", "device", "set", "wlan0", "managed", "no"])

        # Check if the IP is already assigned and remove it if needed
        ip_check = subprocess.run(["/usr/sbin/ip", "addr", "show", "dev", "wlan0"],
                                  capture_output=True, text=True).stdout
        if "192.168.4.1" in ip_check:
            subprocess.run(["/usr/sbin/ip", "addr", "del", "192.168.4.1/24", "dev", "wlan0"])

        # Ensure wlan0 is up
        subprocess.run(["/usr/sbin/ip", "link", "set", "dev", "wlan0", "up"])

        # Set the static IP
        subprocess.run(["/usr/sbin/ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0"])

        # Unmask hostapd if it's masked
        subprocess.run(["/usr/bin/systemctl", "unmask", "hostapd.service"])

        # Configure hostapd
        hostapd_config = f"""interface=wlan0
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

        # Configure dnsmasq
        dnsmasq_config = """interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
"""

        with open("/etc/dnsmasq.conf", "w") as f:
            f.write(dnsmasq_config)

        for attempt in range(3):
            try:
                # Restart services
                subprocess.run(["/usr/bin/systemctl", "restart", "dnsmasq.service"])
                subprocess.run(["/usr/bin/systemctl", "restart", "hostapd.service"])

                # Verify services are running
                hostapd_status = subprocess.run(["/usr/bin/systemctl", "is-active", "hostapd"],
                                                capture_output=True, text=True).stdout.strip()
                dnsmasq_status = subprocess.run(["/usr/bin/systemctl", "is-active", "dnsmasq"],
                                                capture_output=True, text=True).stdout.strip()

                if hostapd_status == 'active' and dnsmasq_status == 'active':
                    print(f'Hotspot {hotspot_name} started successfully')
                    return
                if hostapd_status != "active" or dnsmasq_status != "active":
                    print(f'Attempt {attempt} not active: hostapd={hostapd_status}, dnsmasq={dnsmasq_status}')
                    sleep(3)
            except:
                print(f'Attempt {attempt} starting dnsmasq and hostapd failed: {traceback.format_exc()}')

        self.led_control.set_state('error')
        raise Exception(f"Failed to start services hostapd and dnsmasq")

    def run(self):
        """Main entry point"""
        if not self.config.configuration_exists or not self.config.is_configured:
            # Set LED to blinking
            try:
                # Start in setup mode
                self.start_hotspot()

                self.led_control.set_state("setup")

                # Update OLED to reflect setup mode (WiFi AP/disconnected) and current battery
                try:
                    self.display_control.update_wifi(False)
                    self.display_control.update_battery(
                        self.pisugar.get_battery_level(),
                        self.pisugar.is_charging(),
                        self.pisugar.is_power_plugged(),
                    )
                except Exception:
                    pass

                # Start the web server only if hotspot is successfully created
                self.app.run(host="0.0.0.0", port=80)
            except Exception as e:
                print(f"Setup mode failed: {str(e)}")
                self.led_control.set_state("error")
                raise
        else:
            print("Device already configured, exiting setup mode")
            restart_in_sensor_mode()

    def cleanup(self):
        """Clean up GPIO on exit"""
        try:
            self.display_control.cleanup()
        except Exception:
            pass
        self.led_control.cleanup()
        GPIO.cleanup()


# Main entry point when run directly
if __name__ == "__main__":
    try:
        setup = FreezerBotSetup()
        setup.run()
    except KeyboardInterrupt:
        setup.cleanup()
        print("Setup terminated by user")
        exit(0)
    except Exception as e:
        print(f"Error in setup: {str(e)}")
        GPIO.cleanup()
        raise