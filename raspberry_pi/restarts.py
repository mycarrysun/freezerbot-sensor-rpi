import subprocess
import time


def restart_in_setup_mode():
    """Restart in setup mode - only used when button is explicitly held"""
    time.sleep(2)
    subprocess.run(["/usr/bin/systemctl", "enable", "freezerbot-setup.service"])
    subprocess.run(["/usr/bin/systemctl", "restart", "freezerbot-setup.service"])
    subprocess.run(["/usr/bin/systemctl", "disable", "freezerbot-monitor.service"])
    subprocess.run(["/usr/bin/systemctl", "stop", "freezerbot-monitor.service"])


def restart_in_sensor_mode():
    subprocess.run(["/usr/bin/systemctl", "stop", "hostapd.service"])
    subprocess.run(["/usr/bin/systemctl", "stop", "dnsmasq.service"])

    # Re-enable NetworkManager control of wlan0
    subprocess.run(["/usr/bin/nmcli", "device", "set", "wlan0", "managed", "yes"])
    subprocess.run(["/usr/bin/systemctl", "restart", "NetworkManager.service"])

    # Wait a moment for NetworkManager to initialize
    time.sleep(5)

    subprocess.run(["/usr/bin/systemctl", "enable", "freezerbot-monitor.service"])
    subprocess.run(["/usr/bin/systemctl", "restart", "freezerbot-monitor.service"])
    subprocess.run(["/usr/bin/systemctl", "disable", "freezerbot-setup.service"])
    subprocess.run(["/usr/bin/systemctl", "stop", "freezerbot-setup.service"])