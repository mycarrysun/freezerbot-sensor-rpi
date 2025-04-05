#!/usr/bin/env python3
import logging
import os
import traceback
from datetime import datetime
from time import sleep
import sh
from sh import ErrorReturnCode


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
        try:
            # Configure sudo cp command with logging
            sudo_cp = sh.sudo.bake("cp", _err_to_out=True,
                                   _out=lambda line: self.logger.info(f"Backup: {line.strip()}"))
            sudo_cp("-r", f"{self.base_directory}/.", backup_path)
            return backup_path
        except ErrorReturnCode as e:
            self.logger.error(f"Backup failed with exit code {e.exit_code}")
            return None

    def updates_are_available(self):
        """Check if firmware updates are available from the repository"""
        self.logger.info("Checking for updates from git")
        current_directory = os.getcwd()

        try:
            os.chdir(self.base_directory)

            # Configure git command with logging
            git = sh.git.bake(_err_to_out=True, _out=lambda line: self.logger.info(f"Git: {line.strip()}"))

            # Fetch latest changes
            git.fetch("origin")

            # Get current and remote commit hashes
            current_commit = git("rev-parse", "HEAD").strip()
            remote_commit = git("rev-parse", "origin/main").strip()

            os.chdir(current_directory)

            has_updates = current_commit != remote_commit
            if has_updates:
                self.logger.info(f"Update available: {current_commit} -> {remote_commit}")
            else:
                self.logger.info("No updates available")

            return has_updates
        except ErrorReturnCode as e:
            self.logger.error(f"Git command failed: {traceback.format_exc()}")
            os.chdir(current_directory)
            return False
        except Exception as error:
            self.logger.error(f"Failed to check for updates: {traceback.format_exc()}")
            os.chdir(current_directory)
            return False

    def apply_update(self, backup_path):
        """Download and apply firmware update"""
        current_directory = os.getcwd()
        try:
            os.chdir(self.base_directory)

            # Configure git and sudo commands with logging
            git = sh.git.bake(_err_to_out=True, _out=lambda line: self.logger.info(f"Git update: {line.strip()}"))
            sudo = sh.sudo.bake(_err_to_out=True, _out=lambda line: self.logger.info(f"Install: {line.strip()}"))

            # Pull latest changes
            self.logger.info("Pulling latest changes")
            git.reset("--hard", "origin/main")

            # Run install script
            self.logger.info('Running install script after pulling new changes')
            sudo(f"{self.base_directory}/install.sh")

            sleep(5)

            # Check service status
            sudo_systemctl = sh.sudo.bake("systemctl", _err_to_out=False)
            try:
                monitor_status = sudo_systemctl("status", "freezerbot-monitor.service", _ok_code=[0, 3])
                self.logger.info(f"Monitor status: {monitor_status}")
            except ErrorReturnCode as e:
                monitor_status = e.stdout
                self.logger.warning(f"Monitor status check returned non-zero: {traceback.format_exc()}")

            try:
                setup_status = sudo_systemctl("status", "freezerbot-setup.service", _ok_code=[0, 3])
                self.logger.info(f"Setup status: {setup_status}")
            except ErrorReturnCode as e:
                setup_status = e.stdout
                self.logger.warning(f"Setup status check returned non-zero: {traceback.format_exc()}")

            # Check if either service is running
            if 'active (running)' not in str(monitor_status) and 'active (running)' not in str(setup_status):
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

            # Configure sudo commands with logging
            sudo = sh.sudo.bake(_err_to_out=True, _out=lambda line: self.logger.info(f"Rollback: {line.strip()}"))

            # Move backup to base directory
            sudo("mv", "-T", backup_path, self.base_directory)

            self.logger.info('Running install script after rollback')
            sudo(f"{self.base_directory}/install.sh")

            return True
        except ErrorReturnCode as e:
            self.logger.error(f"Rollback failed with exit code {traceback.format_exc()}")
            return False
        except Exception as error:
            self.logger.error(f"Rollback failed: {traceback.format_exc()}")
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
