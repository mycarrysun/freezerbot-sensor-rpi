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


def get_wifi_signal_strength() -> int:
    """
    Get WiFi signal strength as a percentage (0-100).
    Returns 0 if not connected or unable to read signal strength.
    """
    try:
        # First check if connected
        if not connected_to_wifi():
            return -100
        
        # Get signal strength using nmcli
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "SIGNAL", "device", "wifi", "list", "--rescan", "no"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Get the first line (current connection)
            lines = result.stdout.strip().split('\n')
            if lines:
                # Parse signal strength (should be a number 0-100)
                try:
                    signal = int(lines[0].strip())
                    return max(0, min(100, signal)) * -1  # Clamp to 0-100
                except ValueError:
                    pass
        
        # Fallback: if connected but can't get signal, return a default value
        return -50
    except Exception as e:
        # If anything goes wrong, return 0
        return -100


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


def get_current_wifi_ssid() -> str:
    """
    Get the SSID of the currently connected WiFi network.
    Returns None if not connected or unable to retrieve SSID.
    """
    try:
        # Try to get SSID from active connection
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Look for wlan0 connection
            for line in result.stdout.strip().split('\n'):
                if ':wlan0' in line:
                    ssid = line.split(':')[0]
                    return ssid
        
        # Fallback: try getting SSID from wifi list
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Get the first line (current connection should have highest signal)
            lines = result.stdout.strip().split('\n')
            if lines:
                parts = lines[0].split(':')
                if len(parts) >= 1:
                    ssid = parts[0].strip()
                    if ssid:
                        return ssid
        
        return None
    except Exception as e:
        return None


def get_ip_address() -> str:
    """
    Get the IP address of wlan0 interface.
    Returns None if not available or unable to retrieve.
    """
    try:
        # Try using nmcli first
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", "wlan0"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            ip_line = result.stdout.strip().split('\n')[0]
            if ip_line:
                # Format is usually "192.168.1.1/24" - extract just the IP
                ip = ip_line.split('/')[0].strip()
                if ip:
                    return ip
        
        # Fallback: use ip addr command
        result = subprocess.run(
            ["/bin/ip", "addr", "show", "wlan0"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if 'inet ' in line and not 'inet6' in line:
                    # Extract IP address (format: inet 192.168.1.1/24 ...)
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip = parts[1].split('/')[0]
                        return ip
        
        return None
    except Exception as e:
        return None


def get_mac_address() -> str:
    """
    Get the MAC address of wlan0 interface.
    Returns None if not available or unable to retrieve.
    """
    try:
        # Try using nmcli first
        result = subprocess.run(
            ["/usr/bin/nmcli", "-t", "-f", "GENERAL.HWADDR", "device", "show", "wlan0"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            mac = result.stdout.strip()
            if mac:
                return mac
        
        # Fallback: use ip addr command
        result = subprocess.run(
            ["/bin/ip", "addr", "show", "wlan0"],
            capture_output=True, text=True, timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                if 'link/ether' in line:
                    # Extract MAC address (format: link/ether aa:bb:cc:dd:ee:ff ...)
                    parts = line.strip().split()
                    for part in parts:
                        if ':' in part and len(part) == 17:  # MAC address format
                            return part
        
        return None
    except Exception as e:
        return None


def get_configured_wifi_networks() -> list:
    """
    Get a list of configured WiFi network SSIDs from config.json.
    Returns an empty list if config doesn't exist or has no networks.
    Does not include passwords for security.
    """
    try:
        # Get the base directory (same logic as Config class)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(base_dir, 'config.json')
        
        if not os.path.exists(config_file):
            return []
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        networks = config.get('networks', [])
        ssids = []
        
        for network in networks:
            ssid = network.get('ssid')
            if ssid:
                ssids.append(ssid)
        
        return ssids
    except Exception as e:
        return []