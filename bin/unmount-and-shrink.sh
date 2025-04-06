#!/bin/bash
# unmount_shrink.sh - Script to unmount and shrink a Raspbian image

set -euo pipefail  # Exit on error

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
OUTPUT_FILE="${IMAGE_FILE%.*}.pishrink.img.gz"

"$SCRIPT_DIR/unmount-image.sh" "$IMAGE_FILE"

echo "Applying PiShrink to image file..."
echo "Input: $IMAGE_FILE"
echo "Output: $OUTPUT_FILE"

ensure_pishrink

"$SCRIPT_DIR/shrink-image.sh" "$IMAGE_FILE" "$OUTPUT_FILE"

echo "Done! Shrunk image saved as: $OUTPUT_FILE"
