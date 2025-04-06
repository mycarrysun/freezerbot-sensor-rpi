#!/bin/bash
# mount_raspbian.sh - Script to mount a Raspbian image for modification

set -e  # Exit on error

# Function to display usage information
function usage {
    echo "Usage: $0 <image_file> [mount_point]"
    echo "  <image_file>   - Path to the Raspbian image file"
    echo "  [mount_point]  - Optional directory to mount the image (default: ./mnt)"
    exit 1
}

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

# Check arguments
if [ $# -lt 1 ]; then
    usage
fi

IMAGE_FILE="$1"

# Validate the image file exists
if [ ! -f "$IMAGE_FILE" ]; then
    echo "Error: Image file '$IMAGE_FILE' not found"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set mount point
if [ $# -ge 2 ]; then
    MOUNT_POINT="$2"
else
    MOUNT_POINT="$SCRIPT_DIR/../mnt"
fi

# Create mount points if they don't exist
mkdir -p "${MOUNT_POINT}/rootfs"

# Get image info using fdisk
echo "Analyzing image partitions..."
FDISK_OUTPUT=$(fdisk -l "$IMAGE_FILE")
echo "$FDISK_OUTPUT"

# Calculate start sectors for root partition
SECTOR_SIZE=$(fdisk -l "$IMAGE_FILE" | grep "Sector size" | awk '{print $4}')
ROOT_START=$(fdisk -l "$IMAGE_FILE" | grep "img2" | awk '{print $2}')

if [ -z "$ROOT_START" ]; then
    # Try alternative pattern matching
    ROOT_START=$(fdisk -l "$IMAGE_FILE" | grep -A 5 "Device" | grep "2 " | awk '{print $2}')
fi

if [ -z "$ROOT_START" ]; then
    echo "Error: Failed to identify partitions. Please check the image file."
    exit 1
fi

# Calculate offsets in bytes
ROOT_OFFSET=$(( ROOT_START * SECTOR_SIZE ))

echo "Mounting partitions..."
echo "Root partition offset: $ROOT_OFFSET bytes"

# Mount the partitions
mount -o loop,offset=$ROOT_OFFSET "$IMAGE_FILE" "${MOUNT_POINT}/rootfs"

echo "Image mounted successfully:"
echo "- Root filesystem: ${MOUNT_POINT}/rootfs"
echo
echo "After making changes, use the unmount-and-shrink.sh script to unmount and shrink the image."
