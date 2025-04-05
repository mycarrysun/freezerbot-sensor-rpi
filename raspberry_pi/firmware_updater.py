#!/usr/bin/env python3
import logging
import os
import subprocess
import traceback
import json
from datetime import datetime
from time import sleep
from config import Config
from api import api_token_exists
from api import make_api_request
from temperature_monitor import TemperatureMonitor


class FirmwareUpdater:
    """
    Handles automatic firmware updates for Freezerbot devices with recovery capability

    CAUTION: Be very careful when updating this file or the install.sh script!!
    Bugs will cause a rollback on the first 2 attempts, but on the third attempt no backup is created and will be rolled
    forward without verification of success. This is to allow bug fixes to be pulled when they exist in this script or
    the install.sh script. See: Updater Bootstrapping Problem
    """

    def __init__(self):
        self.initialize_paths()
        self.setup_logging()
        self.config = Config()
        self.ensure_backup_directory_exists()

        # Load update history
        self.update_history = self.load_update_history()

        self.logger.info(f"Firmware updater initialized. Device configured: {self.config.is_configured}")
        self.logger.info(f"Update attempt count: {len(self.update_history['attempts'])}")

    def setup_logging(self):
        """Configure logging for the updater service"""
        log_file_path = f"/home/pi/freezerbot-logs/freezerbot-updater.log"
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
        self.update_history_path = "/home/pi/freezerbot-logs/update_history.json"

    def load_update_history(self):
        """Load history of update attempts"""
        try:
            if os.path.exists(self.update_history_path):
                with open(self.update_history_path, 'r') as f:
                    return json.load(f)
            else:
                return {"attempts": [], "last_success": 0}
        except Exception as e:
            self.logger.error(f"Failed to load update history: {traceback.format_exc()}")
            return {"attempts": [], "last_success": 0}

    def save_update_history(self):
        """Save update history to file"""
        try:
            os.makedirs(os.path.dirname(self.update_history_path), exist_ok=True)
            with open(self.update_history_path, 'w') as f:
                json.dump(self.update_history, f)
        except Exception as e:
            self.logger.error(f"Failed to save update history: {traceback.format_exc()}")

    def add_error_to_update_attempt(self, error: str):
        # Ensure attempts is a list and not empty
        if not isinstance(self.update_history.get('attempts'), list) or not self.update_history['attempts']:
            # Create an initial attempt entry if none exists
            self.update_history['attempts'] = [{
                "timestamp": datetime.now().timestamp(),
                "failure_count": 0
            }]
            self.save_update_history()

        # Now we can safely check and modify the last attempt
        last_attempt = self.update_history['attempts'][-1]
        if not isinstance(last_attempt, dict):
            # Handle case where last attempt isn't a dictionary
            last_attempt = {
                "timestamp": datetime.now().timestamp(),
                "failure_count": 0
            }
            self.update_history['attempts'][-1] = last_attempt

        # Add the errors list if it doesn't exist
        if 'errors' not in last_attempt:
            last_attempt['errors'] = []

        # Append the error and save
        last_attempt['errors'].append(error)
        self.save_update_history()

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
            error_text = f"Backup command failed: {traceback.format_exc()}"
            self.logger.error(error_text)
            self.add_error_to_update_attempt(error_text)
            return None
        except Exception as e:
            error_text = f"Backup failed: {traceback.format_exc()}"
            self.logger.error(error_text)
            self.add_error_to_update_attempt(error_text)
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
        """Apply update with recovery strategies based on attempt count"""
        current_directory = os.getcwd()
        failure_count = len(self.update_history["attempts"])

        # Record this attempt
        self.update_history["attempts"].append({
            "timestamp": datetime.now().timestamp(),
            "failure_count": failure_count
        })
        self.save_update_history()

        self.logger.info(f"Attempting update with recovery level {min(failure_count, 2)}")

        try:
            os.chdir(self.base_directory)

            # Always reset to latest version
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

            # LEVEL 0: Standard update with full verification
            if failure_count < 2:
                return self.verify_and_handle_rollback(backup_path, current_directory)

            # LEVEL 2: No rollback
            else:  # recovery_level >= 2
                self.logger.warning("Recovery Level 2: Skip verification and disable rollback")
                # Consider it successful regardless of service status
                self.clear_update_history()
                return True

        except Exception as error:
            error_text = f"Update failed with recovery level {failure_count}: {traceback.format_exc()}"
            self.logger.error(error_text)

            self.add_error_to_update_attempt(error_text)

            # Only rollback for levels 0-1
            if failure_count < 2 and backup_path:
                os.chdir(current_directory)
                self.rollback_to_backup(backup_path)

            return False

    def verify_and_handle_rollback(self, backup_path, current_directory):
        """Level 0: Full verification with rollback"""
        sleep(5)  # give services time to start or crash

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

        # Check if either service is running
        if 'active (running)' not in monitor_status.stdout and 'active (running)' not in setup_status.stdout:
            error_text = 'Neither monitor nor setup service is running after applying updates. Rolling back.'
            self.logger.error(error_text)
            self.add_error_to_update_attempt(error_text+f"\n\n{monitor_status.stdout}\n\n{setup_status.stdout}")
            os.chdir(current_directory)
            self.rollback_to_backup(backup_path)
            return False

        # Success - clear history
        self.clear_update_history()
        return True

    def clear_update_history(self):
        """Clear update history on successful update"""
        self.update_history = {
            "attempts": [],
            "last_success": datetime.now().timestamp()
        }
        self.save_update_history()
        self.logger.info("Update successful - history cleared")

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
            error_text = f"Rollback failed: {traceback.format_exc()}"
            self.logger.error(error_text)
            self.add_error_to_update_attempt(error_text)
            return False

    def run(self):
        """Main entry point for the updater service with tiered recovery"""
        self.logger.info("Starting firmware update check")

        if not self.updates_are_available():
            self.logger.info("No updates available or error checking. Exiting.")
            return

        # Determine if we should create a backup based on recovery level
        failure_count = len(self.update_history["attempts"])
        if failure_count < 2:  # Only create backups for levels 0-1
            backup_path = self.create_timestamped_backup()
            if not backup_path and failure_count < 2:  # Skip backup check for level 2+
                self.logger.error("Backup failed. Aborting update for safety.")
                return
        else:
            self.logger.warning("Recovery level 2+: Skipping backup creation")
            backup_path = None

        success = self.apply_update(backup_path)

        if success:
            self.logger.info("Firmware update completed successfully")
        else:
            self.logger.error('Firmware update failed')
            if self.config.is_configured and len(self.update_history['attempts']) > 0:
                self.logger.info('Trying to send errors to api')
                if not api_token_exists():
                    self.logger.info('Obtaining new api token')
                    TemperatureMonitor().obtain_api_token()
                errors = []
                if 'errors' in self.update_history['attempts'][-1]:
                    errors = self.update_history['attempts'][-1]['errors']
                self.logger.info(f'Sending api request with:\n'+'\n'.join(errors))
                response = make_api_request('sensors/errors', json={
                    'errors': [
                        'Errors updating firmware',
                        *errors
                    ]
                })
                if response.status_code != 200:
                    self.logger.error(f'Error sending api request: {response.status_code} - {response.status_text}')
                else:
                    self.logger.info('Successfully sent errors to api')


if __name__ == "__main__":
    updater = FirmwareUpdater()
    updater.run()
