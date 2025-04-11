import socket
import traceback
from pisugar import PiSugarServer, connect_tcp, connect_domain_socket, test_via_tcp


class PiSugarMonitor:
    """Class for accessing PiSugar battery information using the pisugar-server-py library"""

    def __init__(self):
        """Initialize the PiSugar monitoring capabilities through the official library"""
        try:
            # First try domain socket connection, which is the default
            conn, event_conn = connect_domain_socket()
            self.server = PiSugarServer(conn, event_conn)
            print("PiSugar connected via domain socket")
        except Exception:
            # Fall back to TCP if domain socket fails
            try:
                conn, event_conn = connect_tcp()
                self.server = PiSugarServer(conn, event_conn)
                print("PiSugar connected via TCP")
            except Exception as e:
                print(f"Failed to connect to PiSugar: {traceback.format_exc()}")
                self.server = None

    def get_battery_level(self):
        if self.server is not None:
            return self.server.get_battery_level()

    def get_current(self):
        if self.server is not None:
            return self.server.get_battery_current()

    def get_voltage(self):
        if self.server is not None:
            return self.server.get_battery_voltage()

    def is_charging(self):
        if self.server is not None:
            return self.server.get_battery_charging()

    def is_power_plugged(self):
        if self.server is not None:
            return self.server.get_battery_power_plugged()

    def is_charging_allowed(self):
        if self.server is not None:
            return self.server.get_battery_allow_charging()

    # TODO add setter for battery charging range
    # https://github.com/PiSugar/pisugar-server-py/blob/main/pisugar/pisugar.py#L287

# Example usage
if __name__ == "__main__":
    monitor = PiSugarMonitor()
    test_via_tcp()
