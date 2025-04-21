#!/usr/bin/env python3
"""
Simple test Flask application for the Freezerbot setup interface.
Run this on your development machine to test the web interface before deploying to Raspberry Pi.
"""

import os

from flask import Flask, request, render_template, redirect, jsonify
from config import Config


class TestFreezerBotSetup:
    """Test implementation of the Freezerbot setup interface"""

    def __init__(self):

        # Find the directory where this script is located
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))

        self.config = Config('test_config.json')

        self.mock_wifi_networks = ["Home-WiFi", "Office-Net", "FreeWiFi", "Cafe-Guest", "Neighbors-5G"]

        # Initialize Flask app
        # For testing, we'll just serve the static files directly
        self.app = Flask(__name__,
                         static_url_path='',
                         static_folder=os.path.join(self.base_dir, 'static'),
                         template_folder=os.path.join(self.base_dir, 'templates'))

        # Debug output to help troubleshoot template location
        print(f"Template folder: {self.app.template_folder}")

        # Set up the Flask routes
        self.setup_routes()

    def setup_routes(self):
        """Set up the web routes for the configuration portal"""
        self.app.route("/")(self.index)
        self.app.route("/api/scan-wifi")(self.scan_wifi)
        self.app.route("/api/get-config")(self.get_current_config)
        self.app.route("/api/setup", methods=["POST"])(self.save_config)
        self.app.route('/api/create-account', methods=['POST'])(self.create_account)

        # Special routes for captive portal detection (just return success for testing)
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
        return jsonify({'success': True})

    def scan_wifi(self):
        """Mock WiFi scanning functionality"""
        print("[TEST] Scanning for WiFi networks")
        return jsonify({"networks": self.mock_wifi_networks})

    def save_config(self):
        """Process and save the configuration to a test file"""
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


            # Save configuration to test file
            config = {
                "networks": networks,
                "email": email,
                "password": password,
                "device_name": device_name
            }

            self.config.save_new_config(config)

            return jsonify({"success": True})
        except Exception as e:
            print(f"[TEST] Error saving configuration: {str(e)}")
            return jsonify({"success": False, "error": str(e)})

    def captive_portal_redirect(self):
        """Mock captive portal detection"""
        return redirect("/")

    def run(self):
        """Run the test application"""
        print("=" * 80)
        print("Freezerbot Setup Test Server")
        print("=" * 80)
        print("Access the web interface at http://localhost:5000")
        print("To test WiFi scanning, visit http://localhost:5000/api/scan-wifi")
        print("Test configuration will be saved to 'test_config.json'")
        print("=" * 80)

        self.app.run(host="0.0.0.0", port=5000, debug=True)


# Main entry point when run directly
if __name__ == "__main__":
    test_app = TestFreezerBotSetup()
    test_app.run()
