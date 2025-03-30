#!/usr/bin/env python3
import os
import subprocess


def determine_mode():
    """Determine which mode to start in based on configuration"""
    config_file = "/home/pi/freezerbot/config.json"
    is_configured = os.path.exists(config_file)

    # Ensure firmware updater is always enabled
    ensure_updater_is_active()

    if is_configured:
        # Start in monitor mode
        subprocess.run(["sudo", "systemctl", "start", "freezerbot-monitor.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-setup.service"])
    else:
        # Start in setup mode
        subprocess.run(["sudo", "systemctl", "start", "freezerbot-setup.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-monitor.service"])


def ensure_updater_is_active():
    """Make sure the firmware updater service and timer are enabled"""
    subprocess.run(["sudo", "systemctl", "enable", "freezerbot-updater.timer"])
    subprocess.run(["sudo", "systemctl", "start", "freezerbot-updater.timer"])


if __name__ == "__main__":
    determine_mode()
