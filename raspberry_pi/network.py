import json
import os
import subprocess
import traceback
from datetime import datetime


def connected_to_wifi() -> bool:
    nm_status = subprocess.run(
        ["/usr/bin/nmcli", "-t", "-f", "DEVICE,STATE", "device", "status"],
        capture_output=True, text=True
    ).stdout.strip()

    return 'wlan0:connected' in nm_status


def test_internet_connectivity() -> bool:
    """Test actual internet connectivity beyond WiFi connection"""
    try:
        if not connected_to_wifi():
            return False
        # Try pinging common DNS servers with short timeout
        result = subprocess.run(
            ["/bin/ping", "-c", "1", "-W", "2", "8.8.8.8"],
            capture_output=True,
            timeout=3
        )
        return result.returncode == 0
    except:
        return False

network_status_file = "/home/pi/freezerbot-logs/network_status.json"

def load_network_status():
    """Load network failure count and reboot count from persistent storage"""
    try:
        if os.path.exists(network_status_file):
            with open(network_status_file, 'r') as f:
                return json.load(f)
        else:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(network_status_file), exist_ok=True)
            # Return default values
            return {
                'network_failure_count': 0,
                'reboot_count': 0,
                'last_updated': datetime.utcnow().isoformat()
            }
    except Exception as e:
        print(f"Error loading network status: {traceback.format_exc()}")
        return {
            'network_failure_count': 0,
            'reboot_count': 0,
            'last_updated': datetime.utcnow().isoformat()
        }

def reset_network_status():
    try:
        save_network_status({
            'network_failure_count': 0,
            'reboot_count': 0,
        })
    except Exception:
        print(f'Failure resetting network status file: {traceback.format_exc()}')

def save_network_status(network_status):
    """Save network failure count and reboot count to persistent storage"""
    try:
        # Update the last_updated timestamp
        network_status['last_updated'] = datetime.utcnow().isoformat()

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(network_status_file), exist_ok=True)

        with open(network_status_file, 'w') as f:
            json.dump(network_status, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving network status: {traceback.format_exc()}")
        return False