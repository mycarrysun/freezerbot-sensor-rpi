import json
import os


class DeviceInfo:
    def __init__(self):
        self.device_info_file = "/home/pi/freezerbot/device_info.json"
        self.device_info = {}
        if not os.path.exists(self.device_info_file):
            print("Device info file not found. Continuing.")
        else:
            with open(self.device_info_file, "r") as f:
                self.device_info = json.load(f)

    def update_firmware_version(self, version):
        self.device_info['firmware_version'] = version
        self.save_device_info(self.device_info)

    def save_device_info(self, new_json):
        with open(self.device_info_file, 'w') as f:
            json.dump(new_json, f, indent=2)