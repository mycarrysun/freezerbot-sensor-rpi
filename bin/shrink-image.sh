#!/bin/bash
set -euo pipefail

# Check if script is being run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

function display_usage {
  echo "Usage: $0 <input file> <output file>"
}

if [[ $# -ne 2 ]]
then
  display_usage
  exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"

function ensure_pishrink {
  if ! command -v pishrink.sh &> /dev/null; then
    echo "Installing PiShrink..."
    wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
    chmod +x pishrink.sh
    sudo mv pishrink.sh /usr/local/bin/
  fi
}

ensure_pishrink

# Shrink the image file
echo "Shrinking image file..."

rm -rf "$OUTPUT_FILE"

pishrink.sh -za "$INPUT_FILE" "$OUTPUT_FILE"