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

    def run_command_with_logging(self, command, log_prefix="Command", check=True):
        """Run a command and log its output"""
        self.logger.info(f"Running: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )

            # Log stdout if present
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    self.logger.info(f"{log_prefix} stdout: {line}")

            # Log stderr if present (as info if command succeeded, as error if it failed)
            if result.stderr.strip():
                log_level = logging.ERROR if result.returncode != 0 else logging.INFO
                for line in result.stderr.strip().split('\n'):
                    self.logger.log(log_level, f"{log_prefix} stderr: {line}")

            # Raise if check=True and command failed
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, command, result.stdout, result.stderr
                )

            return result

        except subprocess.CalledProcessError as e:
            self.logger.error(f"{log_prefix} failed with exit code {e.returncode}")
            raise

    def create_timestamped_backup(self):
        """Back up current installation before applying updates"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_directory, f"backup_{timestamp}")

        self.logger.info(f"Creating backup at {backup_path}")
        os.makedirs(backup_path, exist_ok=True)

        # Copy the entire directory contents recursively
        self.logger.info(f"Backing up all files from {self.base_directory} to {backup_path}")
        try:
            self.run_command_with_logging(
                ["/usr/bin/sudo", "/usr/bin/cp", "-r", f"{self.base_directory}/.", backup_path],
                log_prefix="Backup"
            )
            return backup_path
        except subprocess.CalledProcessError:
            self.logger.error(f"Backup command failed: {traceback.format_exc()}")
            return None
        except Exception as e:
            self.logger.error(f"Backup failed: {traceback.format_exc()}")
            return None

    def updates_are_available(self):
        """Check if firmware updates are available from the repository"""
        self.logger.info("Checking for updates from git")
        current_directory = os.getcwd()

        try:
            os.chdir(self.base_directory)

            # Fetch latest changes
            self.run_command_with_logging(["/usr/bin/git", "fetch", "origin"], log_prefix="Git fetch")

            # Get current commit hash
            current_result = self.run_command_with_logging(
                ["/usr/bin/git", "rev-parse", "HEAD"],
                log_prefix="Git current"
            )
            current_commit = current_result.stdout.strip()

            # Get remote commit hash
            remote_result = self.run_command_with_logging(
                ["/usr/bin/git", "rev-parse", "origin/main"],
                log_prefix="Git remote"
            )
            remote_commit = remote_result.stdout.strip()

            os.chdir(current_directory)

            has_updates = current_commit != remote_commit
            if has_updates:
                self.logger.info(f"Update available: {current_commit} -> {remote_commit}")
            else:
                self.logger.info("No updates available")

            return has_updates
        except subprocess.CalledProcessError:
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

            # Pull latest changes
            self.logger.info("Pulling latest changes")
            self.run_command_with_logging(
                ["/usr/bin/git", "reset", "--hard", "origin/main"],
                log_prefix="Git reset"
            )

            # Run install script
            self.logger.info('Running install script after pulling new changes')
            self.run_command_with_logging(
                ["/usr/bin/sudo", f"{self.base_directory}/install.sh"],
                log_prefix="Install"
            )

            sleep(5)

            # Check service status
            monitor_status = self.run_command_with_logging(
                ["/usr/bin/sudo", "/usr/bin/systemctl", "status", "freezerbot-monitor.service"],
                log_prefix="Monitor status",
                check=False  # Don't raise exception on non-zero exit
            )

            setup_status = self.run_command_with_logging(
                ["/usr/bin/sudo", "/usr/bin/systemctl", "status", "freezerbot-setup.service"],
                log_prefix="Setup status",
                check=False  # Don't raise exception on non-zero exit
            )

            # TODO remove before actually using on real devices
            raise Exception('test exception')

            # Check if either service is running
            if 'active (running)' not in monitor_status.stdout and 'active (running)' not in setup_status.stdout:
                self.logger.error('Neither monitor nor setup service is running after applying updates. Rolling back.')
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
            self.run_command_with_logging(
                ['/usr/bin/rm', '-rf', self.base_directory],
                log_prefix='Remove freezerbot'
            )
            # Move backup to base directory
            self.run_command_with_logging(
                ["/usr/bin/sudo", "/usr/bin/mv", backup_path, self.base_directory],
                log_prefix="Rollback mv"
            )

            self.logger.info('Running install script after rollback')
            self.run_command_with_logging(
                ["/usr/bin/sudo", f"{self.base_directory}/install.sh"],
                log_prefix="Rollback install"
            )

            return True
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
