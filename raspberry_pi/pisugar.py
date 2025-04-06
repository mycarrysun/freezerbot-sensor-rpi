import socket
import json
import traceback
import os


class PiSugarMonitor:
    """Interface for monitoring PiSugar battery status using the official PiSugar server"""

    def __init__(self, socket_path="/tmp/pisugar-server.sock"):
        """
        Initialize the PiSugar monitor

        Args:
            socket_path: Path to the PiSugar server socket
        """
        self.socket_path = socket_path

    def _send_command(self, command):
        """
        Send a command to the PiSugar server via Unix socket

        Args:
            command: Command string to send

        Returns:
            Response data as a dictionary or None if error
        """
        try:
            if not os.path.exists(self.socket_path):
                print(f"PiSugar socket not found at {self.socket_path}. Is the PiSugar server installed and running?")
                return None

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)

            # Send command
            sock.sendall(command.encode('utf-8'))

            # Read response
            response = sock.recv(4096).decode('utf-8').strip()
            sock.close()

            # Parse JSON response
            if response:
                return json.loads(response)
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
        if response and "level" in response:
            try:
                # PiSugar returns level as a decimal (0.0-1.0), convert to percentage
                return float(response["level"]) * 100
            except (ValueError, TypeError):
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
        if response and "charging" in response:
            return bool(response["charging"])
        return None

    def get_battery_voltage(self):
        """
        Get battery voltage in volts

        Returns:
            Float voltage or None if error
        """
        response = self._send_command("get battery_voltage")
        if response and "voltage" in response:
            try:
                return float(response["voltage"])
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
        if response and "model" in response:
            return response["model"]
        return None

    def get_full_status(self):
        """
        Get comprehensive battery status

        Returns:
            Dictionary with battery status or None if error
        """
        result = {}

        # Get battery level
        level = self.get_battery_level()
        if level is not None:
            result["level"] = level

        # Get charging status
        charging = self.is_charging()
        if charging is not None:
            result["charging"] = charging

        # Get voltage
        voltage = self.get_battery_voltage()
        if voltage is not None:
            result["voltage"] = voltage

        # Get model
        model = self.get_model()
        if model is not None:
            result["model"] = model

        return result if result else None


# Example usage
if __name__ == "__main__":
    # For testing
    monitor = PiSugarMonitor()
    status = monitor.get_full_status()
    if status:
        print(f"Battery Level: {status.get('level', 'Unknown')}%")
        print(f"Charging: {'Yes' if status.get('charging') else 'No'}")
        print(f"Voltage: {status.get('voltage', 'Unknown')} V")
        print(f"Model: {status.get('model', 'Unknown')}")
    else:
        print("Could not get PiSugar status. Is the PiSugar server installed and running?")
        print("To install the PiSugar server, run:")
        print("wget https://cdn.pisugar.com/release/pisugar-power-manager.sh")
        print("bash pisugar-power-manager.sh -c release")