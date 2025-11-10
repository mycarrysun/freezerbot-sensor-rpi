#!/usr/bin/env bash

# This file is only used in firmware_updater.py to install new system dependencies that were added after initial launch
# Note: This script is run with sudo by firmware_updater.py, so we don't need sudo commands here

set -e  # Exit on any error
set -u  # Exit on undefined variables

apt-get update
# install some libs for the i2c oled screen
apt-get install -y \
  libopenjp2-7 \
  libtiff6 \
  libatlas-base-dev
