#!/usr/bin/env python3
import subprocess

from config import Config


def determine_mode():
    """Determine which mode to start in based on configuration"""
    config = Config()

    # Ensure firmware updater is always enabled
    ensure_updater_is_active()

    # restart services in this file to also handle when we start from the firmware updater script
    # and the services are already running
    if config.is_configured:
        print('Configuration valid, starting freezerbot-monitor.service')
        subprocess.run(["sudo", "systemctl", "disable", "freezerbot-setup.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-setup.service"])
        subprocess.run(["sudo", "systemctl", "enable", "freezerbot-monitor.service"])
        subprocess.run(["sudo", "systemctl", "restart", "freezerbot-monitor.service"])
    else:
        print('Configuration invalid, starting freezerbot-setup.service')
        subprocess.run(["sudo", "systemctl", "disable", "freezerbot-monitor.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-monitor.service"])
        subprocess.run(["sudo", "systemctl", "enable", "freezerbot-setup.service"])
        subprocess.run(["sudo", "systemctl", "restart", "freezerbot-setup.service"])


def ensure_updater_is_active():
    """Make sure the firmware updater service and timer are enabled"""
    subprocess.run(["sudo", "systemctl", "enable", "freezerbot-updater.timer"])
    subprocess.run(["sudo", "systemctl", "restart", "freezerbot-updater.timer"])


if __name__ == "__main__":
    determine_mode()
