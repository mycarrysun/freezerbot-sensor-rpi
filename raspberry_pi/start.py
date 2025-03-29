import os
import subprocess


def determine_mode():
    """Determine which mode to start in based on configuration"""
    config_file = "/home/pi/freezerbot/config.json"
    is_configured = os.path.exists(config_file)

    if is_configured:
        # Start in monitor mode
        subprocess.run(["sudo", "systemctl", "start", "freezerbot-monitor.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-setup.service"])
    else:
        # Start in setup mode
        subprocess.run(["sudo", "systemctl", "start", "freezerbot-setup.service"])
        subprocess.run(["sudo", "systemctl", "stop", "freezerbot-monitor.service"])


if __name__ == "__main__":
    determine_mode()
