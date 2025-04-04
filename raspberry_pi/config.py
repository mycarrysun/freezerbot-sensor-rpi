import os
import json

from api import api_token_exists

class Config:
    def __init__(self, filename='config.json'):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_file = os.path.join(self.base_dir, filename)
        self.configuration_exists = os.path.exists(self.config_file)
        self.config = {}
        if self.configuration_exists:
            with open(self.config_file, "r") as f:
                self.config = json.load(f)
        self.is_configured = 'email' in self.config and 'password' in self.config or api_token_exists()

    def clear_config(self):
        if os.path.exists(self.config_file):
            os.remove(self.config_file)

    def save_new_config(self, new_config):
        with open(self.config_file, "w") as f:
            json.dump(new_config, f, indent=2)
        self.config = new_config

    def clear_creds_from_config(self):
        del self.config['email']
        del self.config['password']
        self.save_new_config(self.config)

    def add_config_error(self, error):
        self.config['error'] = error
        self.save_new_config(self.config)