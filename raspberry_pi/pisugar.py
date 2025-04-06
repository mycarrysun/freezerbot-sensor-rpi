import socket
import json
import traceback


class PiSugarMonitor:
    """Interface for monitoring PiSugar battery status using TCP socket connection"""

    def __init__(self, host="127.0.0.1", port=8423):
        """
        Initialize the PiSugar monitor

        Args:
            host: PiSugar server hostname or IP
            port: PiSugar server port
        """
        self.host = host
        self.port = port

    def _send_command(self, command):
        """
        Send a command to the PiSugar server via TCP socket

        Args:
            command: Command string to send

        Returns:
            Response data as a dictionary or None if error
        """
        try:
            # Create a TCP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout

            # Connect to the server
            sock.connect((self.host, self.port))

            # Send command with newline
            sock.sendall(f"{command}\n".encode('utf-8'))

            # Read response
            response = sock.recv(4096).decode('utf-8').strip()
            sock.close()

            # Parse JSON response if possible
            if response:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # If not JSON, return as text
                    return {"text": response}
            return None

        except Exception:
            print(f"Error communicating with PiSugar server: {traceback.format_exc()}")
            return None

    def get_battery_level(self):
        """
        Get battery level percentage

        Returns:
            Float percentage (0-100) or None if error
        """
        response = self._send_command("get battery")
        if response:
            try:
                # PiSugar might return level as a decimal (0.0-1.0) or directly
                level = response.get("level", 0)
                # Check if the level is already a percentage or needs conversion
                if isinstance(level, (int, float)) and level <= 1.0:
                    return float(level) * 100
                else:
                    return float(level)
            except (ValueError, TypeError):
                # Try text parsing if JSON parsing failed
                if isinstance(response, dict) and "text" in response:
                    text = response["text"]
                    # Try to extract percentage from text like "battery: 85%"
                    if "battery" in text and "%" in text:
                        try:
                            percentage = float(text.split("%")[0].split(":")[-1].strip())
                            return percentage
                        except (ValueError, IndexError):
                            pass
                print(f"Error parsing battery level: {response}")
                return None
        return None

    def is_charging(self):
        """
        Check if battery is currently charging

        Returns:
            Boolean or None if error
        """
        response = self._send_command("get battery_charging")
        if response:
            # Handle both JSON and text responses
            if isinstance(response, dict):
                if "charging" in response:
                    return bool(response["charging"])
                elif "text" in response:
                    return "true" in response["text"].lower()
            return False
        return None

    def get_battery_voltage(self):
        """
        Get battery voltage in volts

        Returns:
            Float voltage or None if error
        """
        response = self._send_command("get battery_voltage")
        if response:
            try:
                # Try JSON first
                if "voltage" in response:
                    return float(response["voltage"])
                # Try text parsing
                elif "text" in response:
                    text = response["text"]
                    if "voltage" in text and "v" in text.lower():
                        try:
                            voltage = float(text.split("v")[0].split(":")[-1].strip())
                            return voltage
                        except (ValueError, IndexError):
                            pass
            except (ValueError, TypeError):
                print(f"Error parsing battery voltage: {response}")
                return None
        return None

    def get_model(self):
        """
        Get PiSugar model information

        Returns:
            Model string or None if error
        """
        response = self._send_command("get model")
        if response:
            if "model" in response:
                return response["model"]
            elif "text" in response:
                text = response["text"]
                if "model" in text.lower():
                    try:
                        model = text.split(":")[-1].strip()
                        return model
                    except (ValueError, IndexError):
                        pass
        return None

    def get_full_status(self):
        """
        Get comprehensive battery status

        Returns:
            Dictionary with battery status or None if error
        """
        # Get individual values to build status
        level = self.get_battery_level()
        charging = self.is_charging()
        voltage = self.get_battery_voltage()
        model = self.get_model()

        # Check if we got at least one valid response
        if level is not None or charging is not None or voltage is not None or model is not None:
            return {
                "level": level,
                "charging": charging,
                "voltage": voltage,
                "model": model
            }
        return None


# Example usage
if __name__ == "__main__":
    monitor = PiSugarMonitor()

    # Try to get individual values
    level = monitor.get_battery_level()
    charging = monitor.is_charging()
    voltage = monitor.get_battery_voltage()
    model = monitor.get_model()

    print(f"Individual queries:")
    print(f"Battery Level: {level}%")
    print(f"Charging: {'Yes' if charging else 'No'}")
    print(f"Voltage: {voltage} V")
    print(f"Model: {model}")
    print()

    # Try the full status method
    print(f"Full status query:")
    status = monitor.get_full_status()
    if status:
        print(f"Battery Level: {status.get('level')}%")
        print(f"Charging: {'Yes' if status.get('charging') else 'No'}")
        print(f"Voltage: {status.get('voltage')} V")
        print(f"Model: {status.get('model')}")
    else:
        print("Could not get PiSugar status. Is the PiSugar server installed and running?")
        print("To install the PiSugar server, run:")
        print("wget https://cdn.pisugar.com/release/pisugar-power-manager.sh")
        print("bash pisugar-power-manager.sh -c release")