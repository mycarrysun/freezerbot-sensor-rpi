#!/bin/bash

# Check if script is being run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root (sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for image in images/*.img;
do
  "$SCRIPT_DIR"/update-image-from-git.sh "$image"
done
