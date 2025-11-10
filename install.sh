#!/bin/bash
# Installation script for Freezerbot setup system with virtual environment

set -e  # Exit on error

# Make sure script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

add_line_if_missing() {
    local file_path="$1"
    local line_to_add="$2"

    if ! grep -qF "$line_to_add" "$file_path" 2>/dev/null; then
        echo "$line_to_add" >> "$file_path"
        echo "Added to $file_path: $line_to_add"
    fi
}

echo "Beginning Freezerbot installation..."

# Create directory structure
echo "Setting up directory structure..."
PI_DIR=/home/pi
LOGS_DIR="$PI_DIR/freezerbot-logs"
BACKUPS_DIR="$PI_DIR/freezerbot-backups"
FREEZERBOT_DIR="$PI_DIR/freezerbot"
FREEZERBOT_PYTHON_DIR="$FREEZERBOT_DIR/raspberry_pi"

mkdir -p "$BACKUPS_DIR"
mkdir -p "$LOGS_DIR"
mkdir -p $FREEZERBOT_DIR

# Create device info file with model name and firmware version
echo "Creating device information file..."
cd $FREEZERBOT_DIR
GIT_SHA=$(git rev-parse HEAD)

# Check if MODEL_NAME exists in .env file, otherwise use default
if [ -f "$FREEZERBOT_DIR/.env" ] && grep -q "MODEL_NAME=" "$FREEZERBOT_DIR/.env"; then
  MODEL_NAME=$(grep "MODEL_NAME=" "$FREEZERBOT_DIR/.env" | cut -d "=" -f 2)
else
  MODEL_NAME="Unknown Sensor"
fi

# Get Raspberry Pi serial number using the same technique from the setup file
SERIAL=$(grep "Serial" /proc/cpuinfo | cut -d ":" -f 2 | tr -d " ")

# Create JSON file with model name (quotes stripped) and firmware version
cat > $FREEZERBOT_DIR/device_info.json << EOF
{
  "model_name": "${MODEL_NAME//\"/}",
  "firmware_version": "$GIT_SHA",
  "serial": "$SERIAL"
}
EOF

# Set proper ownership
chown -R pi:pi $FREEZERBOT_DIR

# Create virtual environment
echo "Setting up Python virtual environment..."
cd $FREEZERBOT_DIR
# pip install happens in firmware_updater.py

# Copy service files
echo "Installing systemd service files..."
cp $FREEZERBOT_DIR/system/freezerbot-setup.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-monitor.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-updater.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-updater.timer /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-power-led.service /etc/systemd/system/

# Set up permissions
chmod 644 /etc/systemd/system/freezerbot-setup.service
chmod 644 /etc/systemd/system/freezerbot-monitor.service
chmod 644 /etc/systemd/system/freezerbot-updater.service
chmod 644 /etc/systemd/system/freezerbot-updater.timer
chmod 644 /etc/systemd/system/freezerbot-power-led.service

# Disable power hungry services
systemctl disable bluetooth
systemctl disable hciuart
systemctl disable avahi-daemon

# Disable HDMI (saves ~25mA)
add_line_if_missing "/etc/rc.local" "/usr/bin/tvservice -o"

# Put cpu in power saving mode, lives in rc.local cause it doesn't persist across reboots
add_line_if_missing "/etc/rc.local" "echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"

# Disable LEDs
add_line_if_missing "/boot/config.txt" "dtparam=act_led_trigger=none"
add_line_if_missing "/boot/config.txt" "dtparam=act_led_activelow=off"

# Enable services
systemctl daemon-reload
systemctl enable freezerbot-power-led.service
$FREEZERBOT_DIR/.venv/bin/python $FREEZERBOT_PYTHON_DIR/start.py

echo "Setting up startup script..."
echo "@reboot $FREEZERBOT_DIR/.venv/bin/python $FREEZERBOT_PYTHON_DIR/start.py >> $LOGS_DIR/start.log" | crontab -u pi -

echo "Installation complete! Freezerbot is now running"
