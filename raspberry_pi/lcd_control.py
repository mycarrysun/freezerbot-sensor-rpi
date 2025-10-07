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
        self.base_font = None

        # Synchronization for drawing and animation
        self._draw_lock = threading.Lock()

        # Marquee state
        self.default_marquee: Optional[str] = None  # Default message (e.g., device name)
        self.marquee_text: Optional[str] = None  # Custom override message
        self.marquee_offset: int = 0
        self.marquee_speed_px: int = 2  # pixels per frame
        self._marquee_thread: Optional[threading.Thread] = None
        self._marquee_stop = threading.Event()

        # Display state
        self.temperature_f = None
        self.battery_percent = None
        self.is_charging = False
        self.is_plugged_in = False
        self.wifi_connected = False
        self.wifi_strength = 0  # WiFi signal strength 0-100
        self.api_status = False  # True if successfully sending to API
        self.error_status = False  # True if there are errors/issues
        self.showing_critical_message = False  # True when showing persistent critical message
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
            self.image = Image.new('1', (self.display.width, self.display.height)).rotate(180)
            self.draw = ImageDraw.Draw(self.image)

            # Use default 8px font for serial and marquee
            self.base_font = ImageFont.load_default()
            self.small_font = self.base_font
            
            # Create 16px font for temperature using truetype
            try:
                # Try common system fonts
                for font_path in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                                  '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                                  '/usr/share/fonts/truetype/freefont/FreeSans.ttf']:
                    try:
                        self.temp_font = ImageFont.truetype(font_path, 16)
                        break
                    except:
                        continue
                else:
                    # Fallback to default if no truetype found
                    self.temp_font = self.base_font
            except:
                self.temp_font = self.base_font

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

    def update_wifi(self, connected: bool, signal_strength: int = 0):
        """Update WiFi connection status and signal strength display
        
        Args:
            connected: Whether WiFi is connected
            signal_strength: Signal strength as percentage (0-100)
        """
        self.wifi_connected = connected
        self.wifi_strength = signal_strength
        self._refresh_display()

    def update_api_status(self, sending: bool):
        """Update API communication status
        
        Args:
            sending: True if successfully sending data to API
        """
        self.api_status = sending
        self._refresh_display()

    def update_error_status(self, has_error: bool):
        """Update error/issue status
        
        Args:
            has_error: True if there are errors or issues
        """
        self.error_status = has_error
        self._refresh_display()

    def set_default_marquee(self, text: Optional[str]):
        """Set the default marquee message (e.g., device name) that shows when no custom message is active"""
        if not self.display_available:
            return
        self.default_marquee = text
        # Start marquee thread if not already running
        if text and (self._marquee_thread is None or not self._marquee_thread.is_alive()):
            self._marquee_stop.clear()
            self._marquee_thread = threading.Thread(target=self._marquee_loop, daemon=True)
            self._marquee_thread.start()
        self._refresh_display()

    def _stop_marquee(self):
        """Stop the marquee animation if it's currently running"""
        self._marquee_stop.set()
        if self._marquee_thread is not None:
            self._marquee_thread.join(timeout=0.5)
            self._marquee_thread = None

    def _show_two_line_message(self, top_line: str, bottom_line: str):
        """Display a two-line message with top line in large font and bottom line in base font
        
        Args:
            top_line: Text for the top line (will use temp_font - 16px)
            bottom_line: Text for the bottom line (will use base_font - 8px)
        """
        if not self.display_available or self.display is None:
            return

        try:
            self._stop_marquee()

            with self._draw_lock:
                # Clear image buffer
                self.draw.rectangle((0, 0, 128, 32), outline=0, fill=0)

                # Top line: large font (16px) at position (0, 0)
                self._draw_text(0, 0, top_line, font=self.temp_font)

                # Bottom line: base font (8px) at position (0, 18)
                self._draw_text(0, 18, bottom_line, font=self.base_font)

                # Push to display
                self.display.image(self.image)
                self.display.show()

        except Exception as e:
            print(f"Error showing two-line message: {traceback.format_exc()}")

    def _show_centered_message(self, message: str):
        """Display a single-line centered message in large font
        
        Args:
            message: Text to display
        """
        if not self.display_available or self.display is None:
            return

        try:
            self._stop_marquee()

            with self._draw_lock:
                # Clear image buffer
                self.draw.rectangle((0, 0, 128, 32), outline=0, fill=0)

                # Center text vertically in large font (16px) at position (0, 8)
                self._draw_text(0, 8, message, font=self.temp_font)

                # Push to display
                self.display.image(self.image)
                self.display.show()

        except Exception as e:
            print(f"Error showing centered message: {traceback.format_exc()}")

    def show_entering_setup_message(self):
        """Display 'Entering setup' message when transitioning to setup mode"""
        self._show_centered_message("Entering setup")

    def show_setup_mode(self):
        """Display setup mode screen with WiFi hotspot information"""
        # Get last 4 digits of serial number
        serial_suffix = self.serial[-4:] if len(self.serial) >= 4 else self.serial
        wifi_text = f"Freezerbot-Setup-{serial_suffix}"
        self._show_two_line_message("Setup Mode Wifi", wifi_text)

    def show_configuring_message(self):
        """Display 'Configuring...' message during setup"""
        self._show_centered_message("Configuring...")

    def show_wifi_found_message(self, network_name: str):
        """Display 'Wifi found' with network name
        
        Args:
            network_name: The SSID of the connected network
        """
        self._show_two_line_message("Wifi found", network_name)

    def show_no_wifi_message(self):
        """Display 'No wifi connection' message"""
        self._show_two_line_message("No wifi", "connection")

    def show_configuration_successful_message(self):
        """Display 'Configuration successful' message"""
        self._show_two_line_message("Configuration", "successful")

    def show_invalid_login_message(self):
        """Display 'Invalid login / enter setup mode' message"""
        self._show_two_line_message("Invalid login", "enter setup mode")

    def show_bad_probe_message(self):
        """Display 'Bad probe / Contact Support' message when temperature sensor errors are detected"""
        self.showing_critical_message = True
        self._show_two_line_message("Bad probe", "Contact Support")

    def clear_critical_message(self):
        """Clear the critical message flag to allow normal display updates to resume"""
        self.showing_critical_message = False
        
        # Restart marquee thread if there's an active marquee message
        active_marquee = self.marquee_text if self.marquee_text else self.default_marquee
        if active_marquee and (self._marquee_thread is None or not self._marquee_thread.is_alive()):
            self._marquee_stop.clear()
            self._marquee_thread = threading.Thread(target=self._marquee_loop, daemon=True)
            self._marquee_thread.start()
        
        self._refresh_display()

    def show_api_error_message(self, status_code: int, response_text: str):
        """Display API error with status code and response text in a marquee
        
        Args:
            status_code: HTTP status code from the API response
            response_text: Response text from the API
        """
        if not self.display_available or self.display is None:
            return

        try:
            # Stop any existing marquee animation
            self._stop_marquee()

            # Format the error message for the marquee
            error_message = f"API Error {status_code}: {response_text}"
            
            # Set this as the marquee text
            self.marquee_text = error_message
            self.marquee_offset = 0
            
            # Start the marquee thread if not already running
            if self._marquee_thread is None or not self._marquee_thread.is_alive():
                self._marquee_stop.clear()
                self._marquee_thread = threading.Thread(target=self._marquee_loop, daemon=True)
                self._marquee_thread.start()

            with self._draw_lock:
                # Clear image buffer
                self.draw.rectangle((0, 0, 128, 32), outline=0, fill=0)

                # Top line: "API Error" in large font (16px)
                self._draw_text(0, 0, "API Error", font=self.temp_font)

                # Bottom line: Start the marquee with status code and response text
                # The marquee will be drawn by the _marquee_loop thread
                msg = error_message
                try:
                    text_w = int(self.draw.textlength(msg, font=self.base_font))
                except Exception:
                    text_w = self.base_font.getsize(msg)[0] if hasattr(self.base_font, 'getsize') else len(msg) * 6
                gap = 8
                y = 16
                x = self.marquee_offset
                # Draw initial copies for seamless looping
                while x < 128:
                    self._draw_text(x, y, msg)
                    x += text_w + gap

                # Push to display
                self.display.image(self.image)
                self.display.show()

        except Exception:
            print(f"Error showing API error message: {traceback.format_exc()}")

    def _refresh_display(self):
        """Redraw the entire display with current state"""
        if not self.display_available or self.display is None:
            return
        
        # Don't refresh if showing a critical message (like bad probe error)
        if self.showing_critical_message:
            return

        try:
            with self._draw_lock:
                # Clear image buffer
                self.draw.rectangle((0, 0, 128, 32), outline=0, fill=0)

                # Top-right: battery at far right
                battery_x = 128 - 22 - 1  # battery body(20 incl. terminal) + 1px margin
                battery_y = 0

                # Icon order from left to right: error, API, WiFi, battery
                # Calculate positions from right to left
                wifi_x = battery_x - 14  # WiFi: 12px icon + 2px gap
                wifi_y = 0
                
                api_x = wifi_x - 16  # API: 12px icon + 4px gap
                api_y = 0
                
                error_x = api_x - 12  # Error: 6px icon + 6px gap
                error_y = 0

                # Draw battery icon only (no percent text or + symbol)
                if self.battery_percent is not None:
                    self._draw_battery_icon(battery_x, battery_y, self.battery_percent, self.is_charging, self.is_plugged_in)

                # Draw Wi‑Fi icon
                self._draw_wifi_icon(wifi_x, wifi_y, self.wifi_connected, self.wifi_strength)

                # Draw API icon (only when sending)
                if self.api_status:
                    self._draw_api_icon(api_x, api_y, self.api_status)

                # Draw error icon (only when there's an error)
                if self.error_status:
                    self._draw_error_icon(error_x, error_y, self.error_status)

                # Draw temperature (left side, prominent) at 16px
                if self.temperature_f is not None:
                    temp_text = f"{self.temperature_f:.1f}F"
                    self._draw_text(0, 0, temp_text, font=self.temp_font)

                # Always show marquee at the bottom (custom message or default device name)
                # Prioritize custom marquee_text over default_marquee
                active_marquee = self.marquee_text if self.marquee_text else self.default_marquee
                if active_marquee:
                    msg = active_marquee
                    # Measure text width
                    try:
                        text_w = int(self.draw.textlength(msg, font=self.base_font))
                    except Exception:
                        text_w = self.base_font.getsize(msg)[0] if hasattr(self.base_font, 'getsize') else len(msg) * 6
                    gap = 8  # pixels between repeats
                    y = 16  # bottom half of the 32px display
                    x = self.marquee_offset
                    # Draw copies for seamless looping
                    while x < 128:
                        self._draw_text(x, y, msg)
                        x += text_w + gap

                # Push to display
                self.display.image(self.image)
                self.display.show()

        except Exception:
            print(f"Error refreshing display: {traceback.format_exc()}")

    def _draw_text(self, x: int, y: int, text: str, font=None):
        """Draw text at position (x, y) using specified font (defaults to base_font)"""
        if font is None:
            font = self.base_font or self.small_font
        try:
            self.draw.text((x, y), text, fill=255, font=font)
        except Exception:
            self.draw.text((x, y), text, fill=255)

    def _draw_battery_icon(self, x: int, y: int, percent: float, charging: bool, plugged_in: bool):
        """Draw battery icon with charge level (no percent text or + sign)."""
        # Battery body (18x8 pixels)
        self.draw.rectangle((x, y, x + 18, y + 7), outline=255, fill=0)
        # Battery terminal
        self.draw.rectangle((x + 18, y + 2, x + 20, y + 5), outline=255, fill=255)

        # Fill level (>=95% fills completely)
        if percent is not None and percent > 0:
            fill_width = 16 if percent >= 95 else int((max(0, min(100, percent)) / 100) * 16)
            if fill_width > 0:
                self.draw.rectangle((x + 1, y + 1, x + 1 + fill_width, y + 6), outline=255, fill=255)

    def _draw_wifi_icon(self, x: int, y: int, connected: bool, signal_strength: int = 0):
        """Draw Wi‑Fi status as ascending RSSI bars based on signal strength.
        
        Args:
            x: X position
            y: Y position
            connected: Whether WiFi is connected
            signal_strength: Signal strength 0-100 (determines number of bars)
        """
        # Icon size ~12x10 (fits next to battery)
        base_y = y + 9  # bottom baseline
        bar_w = 2
        spacing = 1
        heights = [3, 5, 7, 9]
        
        if not connected:
            # Draw outline bars when disconnected
            for i, h in enumerate(heights):
                left = x + i * (bar_w + spacing)
                self.draw.rectangle((left, base_y - h, left + bar_w - 1, base_y), outline=255, fill=0)
            # X overlay
            self.draw.line((x, y, x + 11, y + 9), fill=255)
            self.draw.line((x + 11, y, x, y + 9), fill=255)
        else:
            # Determine number of bars to fill based on signal strength
            # 0-25% = 1 bar, 26-50% = 2 bars, 51-75% = 3 bars, 76-100% = 4 bars
            if signal_strength <= 25:
                filled_bars = 1
            elif signal_strength <= 50:
                filled_bars = 2
            elif signal_strength <= 75:
                filled_bars = 3
            else:
                filled_bars = 4
            
            # Draw bars
            for i, h in enumerate(heights):
                left = x + i * (bar_w + spacing)
                if i < filled_bars:
                    # Filled bar
                    self.draw.rectangle((left, base_y - h, left + bar_w - 1, base_y), fill=255)
                else:
                    # Outline bar (unfilled)
                    self.draw.rectangle((left, base_y - h, left + bar_w - 1, base_y), outline=255, fill=0)

    def _draw_api_icon(self, x: int, y: int, sending: bool):
        """Draw API status icon as an upward arrow (upload symbol).
        Only draws when actively sending to API for clearer status indication.
        
        Args:
            x: X position
            y: Y position
            sending: True if successfully sending to API
        """
        # Icon size ~12x12 (larger, more visible upload arrow)
        if sending:
            # Arrow shaft (vertical line, thicker)
            self.draw.rectangle((x + 5, y + 4, x + 6, y + 11), fill=255)
            # Arrow head (triangle pointing up)
            self.draw.line((x + 5, y + 4, x + 1, y + 8), fill=255)
            self.draw.line((x + 6, y + 4, x + 10, y + 8), fill=255)
            self.draw.line((x + 2, y + 7, x + 5, y + 4), fill=255)
            self.draw.line((x + 6, y + 4, x + 9, y + 7), fill=255)

    def _draw_error_icon(self, x: int, y: int, has_error: bool):
        """Draw error/issue icon as an exclamation mark.
        
        Args:
            x: X position
            y: Y position
            has_error: True if there are errors
        """
        # Icon size ~6x10 (exclamation mark)
        if has_error:
            # Exclamation mark stem
            self.draw.rectangle((x + 2, y, x + 3, y + 6), fill=255)
            # Exclamation mark dot
            self.draw.rectangle((x + 2, y + 8, x + 3, y + 9), fill=255)

    def set_marquee(self, text: Optional[str], speed_px: int = 1):
        """Set a scrolling marquee message at the bottom. Pass None or '' to disable."""
        if not self.display_available:
            return
        if text:
            # Only reset offset if text has changed
            if self.marquee_text != text:
                self.marquee_offset = 0  # start from the left edge
            self.marquee_text = text
            self.marquee_speed_px = max(1, int(speed_px))
            if self._marquee_thread is None or not self._marquee_thread.is_alive():
                self._marquee_stop.clear()
                self._marquee_thread = threading.Thread(target=self._marquee_loop, daemon=True)
                self._marquee_thread.start()
        else:
            self.clear_marquee()

    def clear_marquee(self):
        """Clear custom marquee message and revert to default marquee (device name)."""
        self.marquee_text = None
        # Only stop the animation thread if there's no default marquee to show
        if not self.default_marquee:
            self._marquee_stop.set()
            if self._marquee_thread is not None:
                self._marquee_thread.join(timeout=0.5)
                self._marquee_thread = None
        else:
            # Reset offset for smooth transition back to default
            self.marquee_offset = 0
            self._refresh_display()

    def _marquee_loop(self):
        """Background loop to scroll the marquee while enabled."""
        try:
            import time
            while not self._marquee_stop.is_set():
                # Determine which marquee to display (custom or default)
                active_marquee = self.marquee_text if self.marquee_text else self.default_marquee
                if not active_marquee:
                    # Nothing to show; pause and continue
                    time.sleep(0.2)
                    continue
                # Measure text width
                try:
                    text_w = int(self.draw.textlength(active_marquee, font=self.base_font or self.small_font))
                except Exception:
                    fnt = self.base_font or self.small_font
                    text_w = fnt.getsize(active_marquee)[0] if hasattr(fnt, 'getsize') else len(active_marquee) * 6
                gap = 8  # pixels between repeats

                # Update position
                self.marquee_offset -= self.marquee_speed_px
                if self.marquee_offset < -(text_w + gap):
                    self.marquee_offset = 0

                # Refresh display
                self._refresh_display()
                time.sleep(0.1)
        except Exception:
            # Fail quietly to avoid affecting main process
            pass

    def cleanup(self):
        """Clean up display resources"""
        try:
            self.clear_marquee()
        except Exception:
            pass
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