import subprocess


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