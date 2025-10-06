import os
import threading
import traceback
from typing import Optional

# Check if display libraries are available
try:
    import board
    import busio
    from adafruit_ssd1306 import SSD1306_I2C
    from PIL import Image, ImageDraw, ImageFont

    DISPLAY_LIBRARIES_AVAILABLE = True
except ImportError:
    DISPLAY_LIBRARIES_AVAILABLE = False

DISPLAY_DISABLED = 'DISPLAY_DISABLED'


class DisplayControl:
    """
    Singleton class for controlling the OLED display with graceful degradation
    if hardware is not present
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure only one instance exists"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DisplayControl, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize display control with backward compatibility"""
        if self._initialized:
            return

        self._initialized = True

        from dotenv import load_dotenv
        load_dotenv(override=True)

        self.module_disabled = os.getenv(DISPLAY_DISABLED) == 'true'
        self.display_available = DISPLAY_LIBRARIES_AVAILABLE and not self.module_disabled

        self.display = None
        self.image = None
        self.draw = None
        self.temp_font = None
        self.small_font = None

        # Display state
        self.temperature_f = None
        self.battery_percent = None
        self.is_charging = False
        self.is_plugged_in = False
        self.wifi_connected = False
        self.serial = self._get_serial_number()

        if self.display_available:
            self._initialize_display()
        else:
            print("Display control initialized in compatibility mode (no display hardware)")

    def _initialize_display(self):
        """Initialize the physical display hardware"""
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.display = SSD1306_I2C(128, 32, i2c, addr=0x3c)
            self.image = Image.new('1', (self.display.width, self.display.height))
            self.draw = ImageDraw.Draw(self.image)

            # Try to load fonts
            try:
                self.temp_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
                self.small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 8)
            except:
                # Fall back to default font
                self.temp_font = ImageFont.load_default()
                self.small_font = ImageFont.load_default()

            self._clear_display()
            print("Display initialized successfully")
        except Exception:
            print(f"Failed to initialize display: {traceback.format_exc()}")
            self.display_available = False

    def _get_serial_number(self) -> str:
        """Read device serial number from /proc/cpuinfo"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'Serial' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return "Unknown"

    def _clear_display(self):
        """Clear the physical display"""
        if not self.display_available or self.display is None:
            return
        try:
            self.display.fill(0)
            self.display.show()
        except Exception:
            print(f"Error clearing display: {traceback.format_exc()}")

    def update_temperature(self, celsius: float):
        """Update the temperature display (converts to Fahrenheit)"""
        self.temperature_f = celsius * 9 / 5 + 32
        self._refresh_display()

    def update_battery(self, percent: Optional[float], charging: bool = False, plugged_in: bool = False):
        """Update battery status display"""
        self.battery_percent = percent
        self.is_charging = charging
        self.is_plugged_in = plugged_in
        self._refresh_display()

    def update_wifi(self, connected: bool):
        """Update WiFi connection status display"""
        self.wifi_connected = connected
        self._refresh_display()

    def _refresh_display(self):
        """Redraw the entire display with current state"""
        if not self.display_available or self.display is None:
            return

        try:
            # Clear image buffer
            self.draw.rectangle((0, 0, 128, 32), outline=0, fill=0)

            # Draw temperature (left side, prominent)
            if self.temperature_f is not None:
                temp_text = f"{self.temperature_f:.1f}F"
                self.draw.text((2, 4), temp_text, fill=255, font=self.temp_font)

            # Draw battery status (top right)
            if self.battery_percent is not None:
                self._draw_battery_icon(98, 2, self.battery_percent, self.is_charging, self.is_plugged_in)
                battery_text = f"{int(self.battery_percent)}%"
                self.draw.text((98, 12), battery_text, fill=255, font=self.small_font)

            # Draw WiFi status (middle right)
            self._draw_wifi_icon(106, 22, self.wifi_connected)

            # Draw serial number (bottom left)
            serial_display = self.serial[-8:] if len(self.serial) > 8 else self.serial
            serial_text = f"{serial_display}"
            self.draw.text((2, 24), serial_text, fill=255, font=self.small_font)

            # Push to display
            self.display.image(self.image)
            self.display.show()

        except Exception:
            print(f"Error refreshing display: {traceback.format_exc()}")

    def _draw_battery_icon(self, x: int, y: int, percent: float, charging: bool, plugged_in: bool):
        """Draw battery icon with charge level"""
        # Battery body (18x8 pixels)
        self.draw.rectangle((x, y, x + 18, y + 7), outline=255, fill=0)
        # Battery terminal
        self.draw.rectangle((x + 18, y + 2, x + 20, y + 5), outline=255, fill=255)

        # Fill level
        if percent > 0:
            fill_width = int((percent / 100) * 16)
            self.draw.rectangle((x + 1, y + 1, x + 1 + fill_width, y + 6), outline=255, fill=255)

        # Charging indicator
        if charging or plugged_in:
            self.draw.text((x + 22, y - 2), '+', fill=255)

    def _draw_wifi_icon(self, x: int, y: int, connected: bool):
        """Draw WiFi status icon"""
        if connected:
            # WiFi signal bars (simplified)
            self.draw.rectangle((x + 3, y + 6, x + 4, y + 7), fill=255)
            self.draw.rectangle((x + 1, y + 4, x + 2, y + 7), fill=255)
            self.draw.rectangle((x + 5, y + 4, x + 6, y + 7), fill=255)
            self.draw.rectangle((x, y + 2, x + 1, y + 7), fill=255)
            self.draw.rectangle((x + 7, y + 2, x + 8, y + 7), fill=255)
        else:
            # X symbol for disconnected
            self.draw.line((x, y, x + 8, y + 8), fill=255)
            self.draw.line((x + 8, y, x, y + 8), fill=255)

    def cleanup(self):
        """Clean up display resources"""
        if self.display_available and self.display is not None:
            try:
                self._clear_display()
            except:
                pass


if __name__ == "__main__":
    # Test code
    import time

    display = DisplayControl()

    if display.display_available:
        print("Testing display...")

        # Test temperature
        display.update_temperature(20.5)
        time.sleep(2)

        # Test battery
        display.update_battery(75, charging=False, plugged_in=True)
        time.sleep(2)

        # Test WiFi
        display.update_wifi(True)
        time.sleep(2)

        # Test all together
        display.update_temperature(-18.2)
        display.update_battery(45, charging=True, plugged_in=True)
        display.update_wifi(False)
        time.sleep(5)

        display.cleanup()
        print("Display test complete")
    else:
        print("Display not available - running in compatibility mode")