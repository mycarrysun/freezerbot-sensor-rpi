#!/usr/bin/env python3
import logging
import os
import subprocess
import traceback
from datetime import datetime
from time import sleep


class FirmwareUpdater:
    """Handles automatic firmware updates for Freezerbot devices"""

    def __init__(self):

        self.initialize_paths()
        self.setup_logging()
        self.device_is_configured = os.path.exists(self.config_file_path)
        self.ensure_backup_directory_exists()

        self.logger.info(f"Firmware updater initialized. Device configured: {self.device_is_configured}")

    def setup_logging(self):
        """Configure logging for the updater service"""
        log_file_path = f"{self.base_directory}/logs/freezerbot-updater.log"
        logging_format = '%(asctime)s - %(levelname)s - %(message)s'

        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=logging_format
        )
        self.logger = logging.getLogger('freezerbot-updater')

    def initialize_paths(self):
        """Set up all file and directory paths used by the updater"""
        self.base_directory = "/home/pi/freezerbot"
        self.config_file_path = os.path.join(self.base_directory, "config.json")
        self.backup_directory = "/home/pi/freezerbot-backups"
        self.repository_url = "https://github.com/mycarrysun/freezerbot-sensor-rpi.git"
        self.system_directory = os.path.join(self.base_directory, "system")

    def ensure_backup_directory_exists(self):
        """Create backup directory if it doesn't exist"""
        if not os.path.exists(self.backup_directory):
            os.makedirs(self.backup_directory)

    def create_timestamped_backup(self):
        """Back up current installation before applying updates"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_directory, f"backup_{timestamp}")

        self.logger.info(f"Creating backup at {backup_path}")
        os.makedirs(backup_path, exist_ok=True)

        # Copy the entire directory contents recursively
        self.logger.info(f"Backing up all files from {self.base_directory} to {backup_path}")
        subprocess.run(["/usr/bin/sudo", "/usr/bin/cp", "-r", f"{self.base_directory}/.", backup_path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        return backup_path

    def updates_are_available(self):
        """Check if firmware updates are available from the repository"""
        self.logger.info("Checking for updates from git")
        current_directory = os.getcwd()

        try:
            os.chdir(self.base_directory)

            # Fetch latest changes
            subprocess.run(["/usr/bin/git", "fetch", "origin"],
                           capture_output=True, text=True, check=True)

            # Get current and remote commit hashes
            current_commit = subprocess.run(["/usr/bin/git", "rev-parse", "HEAD"],
                                            capture_output=True, text=True, check=True).stdout.strip()
            remote_commit = subprocess.run(["/usr/bin/git", "rev-parse", "origin/main"],
                                           capture_output=True, text=True, check=True).stdout.strip()

            os.chdir(current_directory)

            has_updates = current_commit != remote_commit
            if has_updates:
                self.logger.info(f"Update available: {current_commit} -> {remote_commit}")
            else:
                self.logger.info("No updates available")

            return has_updates
        except subprocess.CalledProcessError as error:
            self.logger.error(f"Git command failed: {error.cmd} (exit code {error.returncode})")
            self.logger.error(f"Error output: {error.stderr}")
            os.chdir(current_directory)
            return False
        except Exception as error:
            self.logger.error(f"Failed to check for updates: {str(error)}")
            os.chdir(current_directory)
            return False

    def apply_update(self, backup_path):
        """Download and apply firmware update"""
        current_directory = os.getcwd()
        try:
            os.chdir(self.base_directory)

            self.logger.info("Pulling latest changes")
            subprocess.run(["/usr/bin/git", "reset", "--hard", "origin/main"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.logger.info('Running install script after pulling new changes')
            subprocess.run(["/usr/bin/sudo", f"{self.base_directory}/install.sh"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            sleep(5)

            monitor_status = subprocess.run(["/usr/bin/sudo", '/usr/bin/systemctl', 'status', 'freezerbot-monitor.service'], capture_output=True, text=True, check=True)
            setup_status = subprocess.run(["/usr/bin/sudo", '/usr/bin/systemctl', 'status', 'freezerbot-setup.service'], capture_output=True, text=True, check=True)

            if 'active (running)' not in monitor_status or setup_status:
                self.logger.error('Monitor or setup service is not running after applying updates. Rolling back.')
                os.chdir(current_directory)
                self.rollback_to_backup(backup_path)
                return False
            return True
        except Exception as error:
            self.logger.error(f"Rolling back because the update failed: \n\n{traceback.format_exc()}")
            os.chdir(current_directory)
            self.rollback_to_backup(backup_path)
            return False

    def rollback_to_backup(self, backup_path):
        """Restore previous version if update failed"""
        if not backup_path or not os.path.exists(backup_path):
            self.logger.error("No backup path provided or backup not found")
            return False

        try:
            self.logger.info(f"Rolling back to backup: {backup_path}")

            subprocess.run(["/usr/bin/sudo", "/usr/bin/mv", backup_path, self.base_directory], check=True)

            self.logger.info('Running install script after rollback')
            subprocess.run(["/usr/bin/sudo", f'{self.base_directory}/install.sh'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            return True
        except Exception as error:
            self.logger.error(f"Rollback failed: {str(error)}")
            return False

    def run(self):
        """Main entry point for the updater service"""
        self.logger.info("Starting firmware update check")

        if not self.updates_are_available():
            self.logger.info("No updates available or error checking. Exiting.")
            return

        backup_path = self.create_timestamped_backup()
        if not backup_path:
            self.logger.error("Backup failed. Aborting update for safety.")
            return

        success = self.apply_update(backup_path)

        if success:
            self.logger.info("Firmware update completed successfully")
        else:
            self.logger.error('Firmware update failed')


if __name__ == "__main__":
    updater = FirmwareUpdater()
    updater.run()
