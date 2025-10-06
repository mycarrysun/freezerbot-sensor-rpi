#!/usr/bin/env bash

# This file is only used in firmware_updater.py to install new system dependencies that were added after initial launch

sudo apt-get update
# install some libs for the i2c oled screen
sudo apt-get install -y \
  libopenjp2-7 \
  libtiff6 \
  libatlas-base-dev
