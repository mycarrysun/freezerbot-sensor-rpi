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

# Capture the output of git pull
GIT_OUTPUT=$(git pull 2>&1) || {
  echo "Git pull failed, unmounting without shrinking"
  echo "Git output: $GIT_OUTPUT"
  cd -
  "$SCRIPT_DIR/unmount-image.sh" "$IMAGE_FILE"
  exit 1
}

cd -

# Check if there were changes
if [[ "$GIT_OUTPUT" == *"Already up to date"* ]]; then
  echo "No changes detected from git pull, unmounting without shrinking"
  "$SCRIPT_DIR/unmount-image.sh" "$IMAGE_FILE"
else
  echo "$GIT_OUTPUT"
  echo "Changes successfully pulled, unmounting and shrinking"
  "$SCRIPT_DIR/unmount-and-shrink.sh" "$IMAGE_FILE"
fi