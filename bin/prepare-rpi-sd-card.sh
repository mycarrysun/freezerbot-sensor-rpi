#!/bin/bash

# Freezerbot Sensor SD Card Cleanup Script
# This script cleans a Raspbian SD card of all Freezerbot-specific data
# before creating an image that can be used for new devices.

set -e  # Exit on error

# Check if script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Function to display usage information
function display_usage {
  echo "Usage: $0 <device> <model name>"
  echo "Example: $0 /dev/sdb 'Freezerbot Sensor Pro'"
  echo "WARNING: Be careful to specify the correct device!"
}

# Check if device argument was provided
if [ $# -ne 2 ]; then
  display_usage
  exit 1
fi

DEVICE=$1
MODEL_NAME=$2

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_POINT="/mnt/freezerbot-sd-card"
OUTPUT_DIR="$SCRIPT_DIR/../images"
CURRENT_DATE=$(date +%Y%m%d)
OUTPUT_FILE="$OUTPUT_DIR/${MODEL_NAME// /-}-$CURRENT_DATE.img"
PISHRINK_OUTPUT_FILE="$OUTPUT_DIR/${MODEL_NAME// /-}-$CURRENT_DATE.pishrink.img.gz"
FREEZERBOT_DIR="/home/pi/freezerbot"
PI_DIR="/home/pi"

mkdir -p "$OUTPUT_DIR"



# Function to check if argument is a valid block device
function check_block_device {
  if [ ! -b "$1" ]; then
    echo "Error: $1 is not a valid block device."
    display_usage
    exit 1
  fi
}

# Function to install pishrink if needed
function ensure_pishrink {
  if ! command -v pishrink.sh &> /dev/null; then
    echo "Installing PiShrink..."
    wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
    chmod +x pishrink.sh
    sudo mv pishrink.sh /usr/local/bin/
  fi
}

# Function to safely unmount partitions if already mounted
function ensure_unmounted {
    local device=$1

    # Check if any partitions from this device are mounted
    if mount | grep -q "${device}"; then
        echo "Device ${device} has mounted partitions. Unmounting..."

        # Unmount specific partitions if mounted
        if mount | grep -q "${device}1"; then
            umount "${device}1" || umount -l "${device}1"
        fi

        if mount | grep -q "${device}2"; then
            umount "${device}2" || umount -l "${device}2"
        fi

        # Unmount mount point if anything is mounted there
        if mount | grep -q "$MOUNT_POINT"; then
            umount "$MOUNT_POINT" || umount -l "$MOUNT_POINT"
        fi

        if mount | grep -q "$MOUNT_POINT/boot"; then
            umount "$MOUNT_POINT/boot" || umount -l "$MOUNT_POINT/boot"
        fi

        # Sleep briefly to ensure unmounting is complete
        sleep 2
    fi
}

check_block_device "$DEVICE"

echo "WARNING: This will clean the SD card at $DEVICE for imaging."
echo "All dynamic files will be removed."
echo "An image will be created at: ${OUTPUT_FILE}"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Operation cancelled."
  exit 0
fi

# Create mount point if it doesn't exist
mkdir -p "$MOUNT_POINT"

# Call this function before attempting to mount
ensure_unmounted "$DEVICE"

# Mount the boot partition and root filesystem
echo "Mounting partitions..."
mount "${DEVICE}2" "$MOUNT_POINT"  # Root filesystem
mkdir -p "$MOUNT_POINT/boot"
mount "${DEVICE}1" "$MOUNT_POINT/boot"  # Boot partition

echo "Cleaning up Freezerbot dynamic files..."

# Remove configuration files
rm -rf "$MOUNT_POINT/$FREEZERBOT_DIR/config.json"
rm -rf "$MOUNT_POINT/$FREEZERBOT_DIR/.env"
rm -rf "$MOUNT_POINT/$FREEZERBOT_DIR/device_info.json"

# Remove logs and backups
rm -rf "$MOUNT_POINT/$PI_DIR/freezerbot-logs/"*
rm -rf "$MOUNT_POINT/$PI_DIR/freezerbot-backups/"*

# Remove NetworkManager connections (WiFi configurations)
rm -f "$MOUNT_POINT/etc/NetworkManager/system-connections/"*

# Clean systemd files that are created outside the repo
rm -f "$MOUNT_POINT/etc/systemd/system/freezerbot-*"
rm -f "$MOUNT_POINT/etc/systemd/system/*/freezerbot-*"

# Remove hostapd and dnsmasq configs
rm -f "$MOUNT_POINT/etc/hostapd/hostapd.conf"
rm -f "$MOUNT_POINT/etc/dnsmasq.conf"

# Clean bash history
rm -rf "$MOUNT_POINT/home/pi/.bash_history"

# Clean system logs
rm -rf "$MOUNT_POINT/var/log/journal/"*
rm -f "$MOUNT_POINT/var/log/"*.log
rm -f "$MOUNT_POINT/var/log/"*.gz

# Setup files with contents
echo "MODEL_NAME=$MODEL_NAME" >> "$MOUNT_POINT/$FREEZERBOT_DIR/.env"
echo "freezerbot" > "$MOUNT_POINT/etc/hostname"

echo "Unmounting partitions..."
umount "$MOUNT_POINT/boot"
umount "$MOUNT_POINT"

# Ensure pishrink is available
ensure_pishrink

# Create the image file
echo "Creating image file from SD card..."
dd if="$DEVICE" of="$OUTPUT_FILE" bs=4M status=progress

# Shrink the image file
echo "Shrinking image file..."
pishrink.sh -z "$OUTPUT_FILE" "$PISHRINK_OUTPUT_FILE"

echo "SD card image has been created and shrunk successfully."
echo "Image location: $OUTPUT_FILE"
echo
echo "Done!"