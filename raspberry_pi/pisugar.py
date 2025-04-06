import socket
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
            Response string or None if error
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

            return response

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
        if response and "battery:" in response:
            try:
                # Extract the value part after "battery:"
                value_str = response.split("battery:")[1].strip()
                # Convert to float
                return float(value_str)
            except (ValueError, IndexError):
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
        if response and "battery_charging:" in response:
            charging_str = response.split("battery_charging:")[1].strip()
            return charging_str.lower() == "true"
        return None

    def get_voltage(self):
        """
        Get battery voltage in volts

        Returns:
            Float voltage or None if error
        """
        response = self._send_command("get battery_v")
        if response and "battery_v:" in response:
            try:
                value_str = response.split("battery_v:")[1].strip()
                return float(value_str)
            except (ValueError, IndexError):
                print(f"Error parsing battery voltage: {response}")
                return None
        return None

    def get_current(self):
        """
        Get battery current in amps (PiSugar 2 only)

        Returns:
            Float current in amps or None if error
        """
        response = self._send_command("get battery_i")
        if response and "battery_i:" in response:
            try:
                value_str = response.split("battery_i:")[1].strip()
                return float(value_str)
            except (ValueError, IndexError):
                print(f"Error parsing battery current: {response}")
                return None
        return None

    def is_power_plugged(self):
        """
        Check if power is plugged in (new model only)

        Returns:
            Boolean or None if error/not supported
        """
        response = self._send_command("get battery_power_plugged")
        if response and "battery_power_plugged:" in response:
            plugged_str = response.split("battery_power_plugged:")[1].strip()
            return plugged_str.lower() == "true"
        return None

    def is_charging_allowed(self):
        """
        Check if charging is allowed when USB is plugged (new model only)

        Returns:
            Boolean or None if error/not supported
        """
        response = self._send_command("get battery_allow_charging")
        if response and "battery_allow_charging:" in response:
            allowed_str = response.split("battery_allow_charging:")[1].strip()
            return allowed_str.lower() == "true"
        return None

    def get_model(self):
        """
        Get PiSugar model information

        Returns:
            Model string or None if error
        """
        response = self._send_command("get model")
        if response and "model:" in response:
            return response.split("model:")[1].strip()
        return None

    def get_led_amount(self):
        """
        Get charging LED amount (2 is for new model, 4 is for old model)

        Returns:
            Integer (2 or 4) or None if error
        """
        response = self._send_command("get battery_led_amount")
        if response and "battery_led_amount:" in response:
            try:
                led_amount_str = response.split("battery_led_amount:")[1].strip()
                return int(led_amount_str)
            except (ValueError, IndexError):
                return None
        return None

    def get_charging_range(self):
        """
        Get charging range restart_point% stop_point% (new model only)

        Returns:
            Tuple of (restart_point, stop_point) or None if error/not supported
        """
        response = self._send_command("get battery_charging_range")
        if response and "battery_charging_range:" in response:
            try:
                range_str = response.split("battery_charging_range:")[1].strip()
                # Parse the range which is in format "number, number"
                if "," in range_str:
                    parts = range_str.split(",")
                    restart_point = float(parts[0].strip())
                    stop_point = float(parts[1].strip())
                    return (restart_point, stop_point)
            except (ValueError, IndexError):
                return None
        return None

    def get_full_status(self):
        """
        Get comprehensive battery status

        Returns:
            Dictionary with battery status or None if error
        """
        result = {}

        # Basic battery info
        level = self.get_battery_level()
        if level is not None:
            result["level"] = level

        charging = self.is_charging()
        if charging is not None:
            result["charging"] = charging

        voltage = self.get_voltage()
        if voltage is not None:
            result["voltage"] = voltage

        current = self.get_current()
        if current is not None:
            result["current"] = current

        # Model info
        model = self.get_model()
        if model is not None:
            result["model"] = model

        led_amount = self.get_led_amount()
        if led_amount is not None:
            result["led_amount"] = led_amount

        # Advanced charging info (new models)
        power_plugged = self.is_power_plugged()
        if power_plugged is not None:
            result["power_plugged"] = power_plugged

        charging_allowed = self.is_charging_allowed()
        if charging_allowed is not None:
            result["charging_allowed"] = charging_allowed

        charging_range = self.get_charging_range()
        if charging_range is not None:
            result["charging_range_restart"] = charging_range[0]
            result["charging_range_stop"] = charging_range[1]

        return result if result else None


# Example usage
if __name__ == "__main__":
    monitor = PiSugarMonitor()

    # Try the full status method
    print("\nPiSugar Battery Status:")
    print("-----------------------")
    status = monitor.get_full_status()

    if status:
        if "level" in status:
            print(f"Battery Level: {status['level']}%")
        if "charging" in status:
            print(f"Charging: {'Yes' if status['charging'] else 'No'}")
        if "voltage" in status:
            print(f"Voltage: {status['voltage']} V")
        if "current" in status:
            print(f"Current: {status['current']} A")
        if "model" in status:
            print(f"Model: {status['model']}")
        if "led_amount" in status:
            print(f"LED Amount: {status['led_amount']}")
        if "power_plugged" in status:
            print(f"Power Plugged: {'Yes' if status['power_plugged'] else 'No'}")
        if "charging_allowed" in status:
            print(f"Charging Allowed: {'Yes' if status['charging_allowed'] else 'No'}")
        if "charging_range_restart" in status and "charging_range_stop" in status:
            print(f"Charging Range: {status['charging_range_restart']}% - {status['charging_range_stop']}%")
    else:
        print("Could not get PiSugar status. Is the PiSugar server installed and running?")