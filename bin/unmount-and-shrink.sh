#!/bin/bash
# unmount_shrink.sh - Script to unmount and shrink a Raspbian image

set -euo pipefail  # Exit on error

# Function to display usage information
function usage {
    echo "Usage: $0 <image_file> [mount_point] [output_file]"
    echo "  <image_file>   - Path to the Raspbian image file"
    echo "  [mount_point]  - Optional directory where the image is mounted (default: ./mnt)"
    echo "  [output_file]  - Optional output file name for the shrunk image (default: original_name.shrunk.img)"
    exit 1
}

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

function ensure_pishrink {
  if ! command -v pishrink.sh &> /dev/null; then
    echo "Installing PiShrink..."
    wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
    chmod +x pishrink.sh
    sudo mv pishrink.sh /usr/local/bin/
  fi
}

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

# Set output file
if [ $# -ge 3 ]; then
    OUTPUT_FILE="$3"
else
    OUTPUT_FILE="${IMAGE_FILE%.*}.pishrink.img.gz"
fi

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

echo "Applying PiShrink to image file..."
echo "Input: $IMAGE_FILE"
echo "Output: $OUTPUT_FILE"

ensure_pishrink

"$SCRIPT_DIR/shrink-image.sh" "$IMAGE_FILE" "$OUTPUT_FILE"

echo "Done! Shrunk image saved as: $OUTPUT_FILE"
