#!/bin/bash
set -euo pipefail

function usage {
    echo "Usage: $0 <image_file> <new model name>"
    echo "  <image_file>     - Path to the Raspbian image file"
    echo "  <new model name> - Model name to use instead of whats in the image"
    exit 1
}

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

if [ $# -ne 2 ]; then
    usage
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_FILE="$1"
MODEL_NAME="$2"

MOUNT_POINT="$SCRIPT_DIR/../mnt"
OUTPUT_DIR="$SCRIPT_DIR/../images"
CURRENT_DATE=$(date +%Y%m%d)
OUTPUT_NAME="$OUTPUT_DIR/${MODEL_NAME// /-}-$CURRENT_DATE"
OUTPUT_FILE="$OUTPUT_NAME.img"
PISHRINK_OUTPUT_FILE="$OUTPUT_NAME.pishrink.img.gz"
FREEZERBOT_DIR="/home/pi/freezerbot"

# Validate the image file exists
if [ ! -f "$IMAGE_FILE" ]; then
    echo "Error: Image file '$IMAGE_FILE' not found"
    exit 1
fi

"$SCRIPT_DIR"/mount-image.sh "$IMAGE_FILE" "$MOUNT_POINT"

echo "Overwriting MODEL_NAME from factory reset with: MODEL_NAME=${MODEL_NAME//\"/}"
echo "MODEL_NAME=${MODEL_NAME//\"/}" > "${MOUNT_POINT}/rootfs${FREEZERBOT_DIR}/.env"

"$SCRIPT_DIR"/unmount-image.sh "$IMAGE_FILE"

cp "$IMAGE_FILE" "$OUTPUT_FILE"

"$SCRIPT_DIR/shrink-image.sh" "$OUTPUT_FILE" "$PISHRINK_OUTPUT_FILE"
