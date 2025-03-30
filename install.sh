#!/bin/bash
# Installation script for Freezerbot setup system with virtual environment

set -e  # Exit on error

# Make sure script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

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

# Set proper ownership
chown -R pi:pi $FREEZERBOT_DIR

# Copy all files to installation directory
echo "Copying files to installation directory..."
cp -r ./* $FREEZERBOT_DIR/

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
echo "Enabling systemd services..."
systemctl daemon-reload
systemctl enable freezerbot-setup.service
systemctl enable freezerbot-updater.timer
systemctl start freezerbot-updater.timer

# Set up startup script to run at boot
echo "Setting up startup script..."
echo "@reboot $FREEZERBOT_DIR/.venv/bin/python $FREEZERBOT_DIR/start.py" | crontab -u pi -

echo "Installation complete! Reboot to start in setup mode."
echo "Run 'sudo reboot' to start the Freezerbot setup process."