#!/bin/bash
set -euo pipefail

# Function to display usage information
function usage {
    echo "Usage: $0 <image_file>"
    echo "  <image_file>   - Path to the Raspbian image file"
    exit 1
}

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

# Check arguments
if [ $# -ne 1 ]; then
    usage
fi

IMAGE_FILE="$1"

# Validate the image file exists
if [ ! -f "$IMAGE_FILE" ]; then
    echo "Error: Image file '$IMAGE_FILE' not found"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOUNT_POINT="$SCRIPT_DIR/../mnt"

# Check if mount points exist
if [ ! -d "${MOUNT_POINT}/rootfs" ]; then
    echo "Error: Mount points not found. Please specify the correct mount point."
    exit 1
fi

if ! mount | grep -q "${MOUNT_POINT}/rootfs"; then
    echo "Warning: Root filesystem not mounted."
fi

echo "Unmounting partitions..."
# Unmount with various fallbacks to ensure it works
umount "${MOUNT_POINT}/rootfs" 2>/dev/null || umount -l "${MOUNT_POINT}/rootfs" 2>/dev/null || true

# Verify unmount was successful
if mount | grep -q "${MOUNT_POINT}/rootfs"; then
    echo "Error: Failed to unmount partitions. Please check if any files are open in the mounted directories."
    exit 1
fi