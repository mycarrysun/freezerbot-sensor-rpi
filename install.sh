#!/bin/bash
# Installation script for Freezerbot setup system with virtual environment

set -e  # Exit on error

# Make sure script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

echo "We have a new line in the install.sh buddy"
echo "Beginning Freezerbot installation..."

# Install system packages
echo "Installing system packages..."
apt-get update
apt-get install -y python3-venv python3-pip git hostapd dnsmasq

# Create directory structure
echo "Setting up directory structure..."
FREEZERBOT_DIR="/home/pi/freezerbot"
mkdir -p $FREEZERBOT_DIR
mkdir -p $FREEZERBOT_DIR/backup
mkdir -p $FREEZERBOT_DIR/logs

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

# Create JSON file with model name and firmware version
cat > $FREEZERBOT_DIR/device_info.json << EOF
{
  "model_name": "${MODEL_NAME}",
  "firmware_version": "$GIT_SHA",
  "serial": "$SERIAL"
}
EOF

# Set proper ownership
chown -R pi:pi $FREEZERBOT_DIR

# Create virtual environment
echo "Setting up Python virtual environment..."
cd $FREEZERBOT_DIR
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy service files
echo "Installing systemd service files..."
cp $FREEZERBOT_DIR/system/freezerbot-setup.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-monitor.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-updater.service /etc/systemd/system/
cp $FREEZERBOT_DIR/system/freezerbot-updater.timer /etc/systemd/system/

# Set up permissions
chmod 644 /etc/systemd/system/freezerbot-setup.service
chmod 644 /etc/systemd/system/freezerbot-monitor.service
chmod 644 /etc/systemd/system/freezerbot-updater.service
chmod 644 /etc/systemd/system/freezerbot-updater.timer

# Enable services
systemctl daemon-reload
$FREEZERBOT_DIR/.venv/bin/python $FREEZERBOT_DIR/raspberry_pi/start.py

echo "Installation complete! Freezerbot is now running."
