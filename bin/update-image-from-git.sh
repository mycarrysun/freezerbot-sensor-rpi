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
if [ $# -lt 1 ]; then
    usage
fi

IMAGE_FILE="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/mount-image.sh" "$IMAGE_FILE"

cd "$SCRIPT_DIR/../mnt/rootfs/home/pi/freezerbot"

git pull

cd -

"$SCRIPT_DIR/unmount-and-shrink.sh" "$IMAGE_FILE"
