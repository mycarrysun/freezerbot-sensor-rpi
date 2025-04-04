#!/usr/bin/env python3
import logging
import os
import subprocess
from datetime import datetime


class FirmwareUpdater:
    """Handles automatic firmware updates for Freezerbot devices"""

    def __init__(self):
        self.setup_logging()
        self.initialize_paths()
        self.device_is_configured = os.path.exists(self.config_file_path)
        self.ensure_backup_directory_exists()

        self.logger.info(f"Firmware updater initialized. Device configured: {self.device_is_configured}")

    def setup_logging(self):
        """Configure logging for the updater service"""
        log_file_path = "/var/log/freezerbot-updater.log"
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
        self.backup_directory = os.path.join(self.base_directory, "backup")
        self.repository_url = "https://github.com/mycarrysun/freezerbot-sensor-rpi.git"
        self.system_directory = os.path.join(self.base_directory, "system")

    def ensure_backup_directory_exists(self):
        """Create backup directory if it doesn't exist"""
        if not os.path.exists(self.backup_directory):
            os.makedirs(self.backup_directory)

    def create_timestamped_backup(self):
        """Back up current installation before applying updates"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.backup_directory, f"backup_{timestamp}")

            self.logger.info(f"Creating backup at {backup_path}")
            os.makedirs(backup_path, exist_ok=True)

            # Copy the entire directory contents recursively
            self.logger.info(f"Backing up all files from {self.base_directory} to {backup_path}")
            subprocess.run(["cp", "-r", f"{self.base_directory}/.", backup_path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            return True, backup_path
        except Exception as error:
            self.logger.error(f"Backup failed: {str(error)}")
            return False, None

    def updates_are_available(self):
        """Check if firmware updates are available from the repository"""
        try:
            git_directory = os.path.join(self.base_directory, ".git")

            if not os.path.exists(git_directory):
                return self.initialize_git_repository()

            return self.check_git_for_updates()
        except Exception as error:
            self.logger.error(f"Error checking for updates: {str(error)}")
            return False

    def initialize_git_repository(self):
        """Set up git repository for first-time use"""
        self.logger.info("Git repository not found. Setting up new repository.")
        current_directory = os.getcwd()

        try:
            os.chdir(self.base_directory)

            # Initialize git and set up remote
            subprocess.run(["git", "init"])
            subprocess.run(["git", "remote", "add", "origin", self.repository_url])
            subprocess.run(["git", "fetch"])
            subprocess.run(["git", "checkout", "-f", "main"])  # or your default branch

            os.chdir(current_directory)
            return True
        except Exception as error:
            self.logger.error(f"Failed to initialize git repository: {str(error)}")
            os.chdir(current_directory)
            return False

    def check_git_for_updates(self):
        """Compare local and remote git repositories for changes"""
        self.logger.info("Checking for updates")
        current_directory = os.getcwd()

        try:
            os.chdir(self.base_directory)

            # Fetch latest changes
            subprocess.run(["git", "fetch", "origin"])

            # Get current and remote commit hashes
            current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
            remote_commit = subprocess.check_output(["git", "rev-parse", "origin/main"]).decode().strip()

            os.chdir(current_directory)

            has_updates = current_commit != remote_commit
            if has_updates:
                self.logger.info(f"Update available: {current_commit} -> {remote_commit}")
            else:
                self.logger.info("No updates available")

            return has_updates
        except Exception as error:
            self.logger.error(f"Failed to check for updates: {str(error)}")
            os.chdir(current_directory)
            return False

    def apply_update(self):
        """Download and apply firmware update"""
        try:
            current_directory = os.getcwd()
            os.chdir(self.base_directory)

            self.logger.info("Pulling latest changes")
            subprocess.run(["git", "pull", "origin", "main"])

            self.install_dependencies()
            self.update_system_services()

            os.chdir(current_directory)
            return True
        except Exception as error:
            self.logger.error(f"Update failed: {str(error)}")
            os.chdir(current_directory)
            return False

    def install_dependencies(self):
        """Install any new dependencies from requirements.txt"""
        requirements_file = os.path.join(self.base_directory, "requirements.txt")
        if os.path.exists(requirements_file):
            self.logger.info("Installing dependencies")
            subprocess.run(["pip3", "install", "-r", requirements_file])

    def update_system_services(self):
        """Update systemd service files if there are changes"""
        if os.path.exists(self.system_directory):
            self.logger.info("Updating system services")

            for file in os.listdir(self.system_directory):
                if file.endswith('.service') or file.endswith('.timer'):
                    source_path = os.path.join(self.system_directory, file)
                    destination_path = f"/etc/systemd/system/{file}"
                    subprocess.run(["cp", source_path, destination_path])

            # Reload systemd to recognize changes
            subprocess.run(["systemctl", "daemon-reload"])

    def restart_appropriate_service(self):
        """Restart the service based on device's current mode"""
        try:
            if self.device_is_configured:
                self.logger.info("Restarting monitoring service")
                subprocess.run(["systemctl", "restart", "freezerbot-monitor.service"])
            else:
                self.logger.info("Restarting setup service")
                subprocess.run(["systemctl", "restart", "freezerbot-setup.service"])

            return True
        except Exception as error:
            self.logger.error(f"Service restart failed: {str(error)}")
            return False

    def rollback_to_backup(self, backup_path):
        """Restore previous version if update failed"""
        if not backup_path or not os.path.exists(backup_path):
            self.logger.error("No backup path provided or backup not found")
            return False

        try:
            self.logger.info(f"Rolling back to backup: {backup_path}")

            self.restore_main_files(backup_path)
            self.restore_system_files(backup_path)

            return True
        except Exception as error:
            self.logger.error(f"Rollback failed: {str(error)}")
            return False

    def restore_main_files(self, backup_path):
        """Restore main directory files from backup"""
        for file in os.listdir(backup_path):
            if file == "system":
                continue

            source_path = os.path.join(backup_path, file)
            destination_path = os.path.join(self.base_directory, file)
            subprocess.run(["cp", source_path, destination_path])

    def restore_system_files(self, backup_path):
        """Restore system service files from backup"""
        system_backup_path = os.path.join(backup_path, "system")
        if os.path.exists(system_backup_path):
            for file in os.listdir(system_backup_path):
                source_path = os.path.join(system_backup_path, file)

                # Restore to project directory
                project_destination = os.path.join(self.base_directory, "system", file)
                subprocess.run(["cp", source_path, project_destination])

                # Also update systemd files
                if file.endswith('.service') or file.endswith('.timer'):
                    system_destination = f"/etc/systemd/system/{file}"
                    subprocess.run(["cp", source_path, system_destination])

            # Reload systemd
            subprocess.run(["systemctl", "daemon-reload"])

    def run(self):
        """Main entry point for the updater service"""
        self.logger.info("Starting firmware update check")

        if not self.updates_are_available():
            self.logger.info("No updates available or error checking. Exiting.")
            return

        backup_success, backup_path = self.create_timestamped_backup()
        if not backup_success:
            self.logger.error("Backup failed. Aborting update for safety.")
            return

        update_success = self.apply_update()
        if not update_success:
            self.logger.error("Update failed. Rolling back.")
            self.rollback_to_backup(backup_path)
            return

        restart_success = self.restart_appropriate_service()
        if not restart_success:
            self.logger.error("Service restart failed. Rolling back.")
            self.rollback_to_backup(backup_path)
            return

        self.logger.info("Firmware update completed successfully")


if __name__ == "__main__":
    updater = FirmwareUpdater()
    updater.run()
