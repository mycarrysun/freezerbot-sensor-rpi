#!/bin/bash
# Factory reset script for Freezerbot sensors
# Can be run directly on a device or on a mounted SD card image
# Usage:
#   On device: ./factory-reset.sh
#   On mounted image: ./factory-reset.sh /mnt/freezerbot-sd-card

set -e  # Exit on error

# Check if script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Base directories
FREEZERBOT_DIR="/home/pi/freezerbot"
PI_DIR="/home/pi"

# If a mount point is provided, use it as a prefix
if [ $# -eq 1 ]; then
  MOUNT_POINT="$1"
  echo "Using mount point: $MOUNT_POINT"
else
  MOUNT_POINT=""
  echo "Running factory reset on current system"
fi

# Preserve model name if it exists
ENV_FILE="${MOUNT_POINT}${FREEZERBOT_DIR}/.env"
if [ -f "$ENV_FILE" ] && grep -q "MODEL_NAME=" "$ENV_FILE"; then
  MODEL_NAME=$(grep "MODEL_NAME=" "$ENV_FILE" | cut -d "=" -f 2)
  echo "Preserving MODEL_NAME: $MODEL_NAME"
else
  MODEL_NAME="Unknown"
  echo "Using default MODEL_NAME: $MODEL_NAME"
fi

echo "Performing factory reset..."

# Remove configuration files
rm -f "${MOUNT_POINT}${FREEZERBOT_DIR}/config.json"
rm -f "${MOUNT_POINT}${FREEZERBOT_DIR}/.env"
rm -f "${MOUNT_POINT}${FREEZERBOT_DIR}/device_info.json"

# Remove logs and backups
rm -rf "${MOUNT_POINT}${PI_DIR}/freezerbot-logs/"*
rm -rf "${MOUNT_POINT}${PI_DIR}/freezerbot-backups/"*

# Remove NetworkManager connections (WiFi configurations)
rm -f "${MOUNT_POINT}/etc/NetworkManager/system-connections/"*
rm -f "${MOUNT_POINT}/etc/ssl/certs/freezerbot-"*

# Clean systemd files that are created outside the repo
rm -f "${MOUNT_POINT}/etc/systemd/system/freezerbot-"*
rm -f "${MOUNT_POINT}"/etc/systemd/system/*/freezerbot-*

# Remove hostapd and dnsmasq configs
rm -f "${MOUNT_POINT}/etc/hostapd/hostapd.conf"
rm -f "${MOUNT_POINT}/etc/dnsmasq.conf"

# Clean bash history
rm -f "${MOUNT_POINT}${PI_DIR}/.bash_history"

# Clean system logs
rm -rf "${MOUNT_POINT}/var/log/journal/"*
rm -f "${MOUNT_POINT}/var/log/"*.log
rm -f "${MOUNT_POINT}/var/log/"*.gz

# Restore the MODEL_NAME to .env file
echo "MODEL_NAME=${MODEL_NAME//\"/}" > "${MOUNT_POINT}${FREEZERBOT_DIR}/.env"
echo "freezerbot" > "$MOUNT_POINT"/etc/hostname

if [ -z "$MOUNT_POINT" ]
then
  # if running on a machine we can clear the crontab
  echo "Removing users crontab"
  echo "" | crontab -u pi -
fi

echo "Factory reset completed successfully."
