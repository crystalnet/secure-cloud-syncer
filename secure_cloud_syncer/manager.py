#!/usr/bin/env python3
"""
Sync Manager Daemon for Secure Cloud Syncer.
This module provides a daemon that manages sync tasks and handles config updates.
"""

import os
import sys
import json
import time
import signal
import logging
import threading
import multiprocessing
import subprocess
import psutil
from pathlib import Path
from typing import Dict, Any, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from logging.handlers import RotatingFileHandler

from .sync import one_way, bidirectional, monitor
print(f"DEBUG: monitor module: {monitor}")  # This will show us what we're actually importing

def setup_logging():
    """
    Set up logging configuration for the manager process.
    This should be called once at startup.
    """
    # Create log directory if it doesn't exist
    log_dir = os.path.expanduser("~/.rclone")
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "scs_manager.log"))
        ],
        force=True  # Force reconfiguration
    )
    
    # Get the logger for this module
    logger = logging.getLogger("secure_cloud_syncer.manager")
    
    # Add a rotating file handler for better log management
    rotating_handler = RotatingFileHandler(
        os.path.join(log_dir, "scs_manager.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(rotating_handler)
    
    # Set up error logging to a separate file
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "scs_manager.error.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(message)s'))
    logger.addHandler(error_handler)
    
    return logger

# Set up logging at module level
logger = setup_logging()

CONFIG_FILE = os.path.expanduser("~/.rclone/scs_config.json")
SOCKET_FILE = os.path.expanduser("~/.rclone/scs.sock")
PID_FILE = os.path.expanduser("~/.rclone/scs_manager.pid")

class ConfigWatcher(FileSystemEventHandler):
    """Watch for changes to the config file."""
    def __init__(self, manager):
        self.manager = manager
        self.last_modified = 0
    
    def on_modified(self, event):
        if event.src_path == CONFIG_FILE:
            # Debounce config changes
            current_time = time.time()
            if current_time - self.last_modified > 1:  # 1 second debounce
                self.last_modified = current_time
                logger.info(f"Config file modified: {event.src_path}")
                self.manager.reload_config()

class SyncTask:
    """
    Represents a sync task with its configuration and process.
    """
    def __init__(self, config):
        """
        Initialize a sync task.
        
        Args:
            config (dict): Task configuration
        """
        self.config = config
        self.observer = None
        self.start_time = None
        self.last_error = None
        self.error_count = 0
        self.restart_count = 0
        self.logger = logging.getLogger("secure_cloud_syncer.manager.task")
    
    def start(self):
        """
        Start the sync task.
        
        Returns:
            bool: True if the task started successfully, False otherwise
        """
        try:
            self.logger.info(f"Starting task with config: {self.config}")
            
            # Validate required fields
            required_fields = ['local_dir', 'remote_dir']
            for field in required_fields:
                if field not in self.config:
                    self.logger.error(f"Missing required field: {field}")
                    return False
            
            # Get configuration values with defaults
            local_dir = self.config['local_dir']
            remote_dir = self.config.get('remote_dir', 'gdrive_encrypted:')
            exclude_resource_forks = self.config.get('exclude_resource_forks', False)
            debounce_time = self.config.get('debounce_time', 5)
            direction = self.config.get('direction', 'bidirectional')
            
            self.logger.info(f"Starting monitor for {local_dir}")
            self.observer = monitor.start_monitoring(
                local_dir=local_dir,
                remote_dir=remote_dir,
                exclude_resource_forks=exclude_resource_forks,
                debounce_time=debounce_time,
                direction=direction
            )
            
            if not isinstance(self.observer, Observer):
                self.logger.error("Failed to create observer")
                return False
            
            self.start_time = time.time()
            self.last_error = None
            self.error_count = 0
            self.restart_count = 0
            
            self.logger.info(f"Task started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting task: {e}", exc_info=True)
            self.last_error = str(e)
            self.error_count += 1
            return False
    
    def stop(self):
        """
        Stop the sync task.
        
        Returns:
            bool: True if the task was stopped successfully, False otherwise
        """
        try:
            if self.observer and self.observer.is_alive():
                self.logger.info("Stopping task")
                self.observer.stop()
                self.observer.join()
                self.observer = None
                self.logger.info("Task stopped successfully")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error stopping task: {e}", exc_info=True)
            return False
    
    def is_running(self):
        """
        Check if the task is running.
        
        Returns:
            bool: True if the task is running, False otherwise
        """
        return self.observer is not None and self.observer.is_alive()
    
    def get_status(self):
        """
        Get the current status of the task.
        
        Returns:
            dict: Task status information
        """
        return {
            'running': self.is_running(),
            'start_time': self.start_time,
            'uptime': time.time() - self.start_time if self.start_time else None,
            'last_error': self.last_error,
            'error_count': self.error_count,
            'restart_count': self.restart_count
        }

class SyncManager:
    """Manages sync tasks and handles config updates."""
    def __init__(self):
        self.tasks: Dict[str, SyncTask] = {}
        self.running = False
        self.config_watcher = ConfigWatcher(self)
        self.observer = Observer()
        self.lock = threading.Lock()
        self.health_check_thread = None
        self.watchdog_thread = None
        self.last_activity = time.time()
    
    def initialize(self):
        """Initialize the sync manager (setup without starting)."""
        if self.running:
            logger.warning("Sync manager is already running")
            return
        
        # Start watching the config file
        self.observer.schedule(self.config_watcher, os.path.dirname(CONFIG_FILE), recursive=False)
        self.observer.start()
        
        # Start health check thread
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        
        # Start watchdog thread
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()
        
        logger.info("Sync manager initialized")
    
    def start(self):
        """Start the sync manager and load initial config."""
        if self.running:
            logger.warning("Sync manager is already running")
            return
        
        # Mark as running before loading config
        self.running = True
        logger.info("Sync manager started")
        
        # Load initial config
        self.reload_config()
    
    def stop(self):
        """Stop the sync manager."""
        if not self.running:
            logger.warning("Sync manager is not running")
            return
        
        # Stop watching the config file
        self.observer.stop()
        self.observer.join()
        
        # Stop all tasks
        with self.lock:
            for task in self.tasks.values():
                task.stop()
            self.tasks.clear()
        
        self.running = False
        logger.info("Sync manager stopped")
    
    def _watchdog_loop(self):
        """Watchdog thread to ensure the service stays alive."""
        while self.running:
            try:
                # Check if the main process is still running
                if not os.path.exists(PID_FILE):
                    logger.error("PID file not found, service may have crashed")
                    self._restart_service()
                    break
                
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                
                try:
                    os.kill(pid, 0)  # Check if process exists
                except OSError:
                    logger.error("Service process not found, restarting...")
                    self._restart_service()
                    break
                
                # Update last activity time
                self.last_activity = time.time()
                
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _restart_service(self):
        """Restart the service process."""
        try:
            # Remove stale PID file
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            
            # Start new service process with stdout/stderr preserved
            subprocess.Popen([sys.executable, "-m", "secure_cloud_syncer.manager"],
                           stdout=sys.stdout,
                           stderr=sys.stderr)
            logger.info("Service restarted by watchdog")
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
    
    def _health_check_loop(self):
        """Periodically check the health of all tasks."""
        while self.running:
            with self.lock:
                for task in self.tasks.values():
                    task.check_health()
            time.sleep(60)  # Check every minute
    
    def reload_config(self):
        """Reload the configuration and update tasks."""
        if not self.running:
            logger.warning("Sync manager is not running, skipping config reload")
            return
        
        try:
            # Load new config
            if not os.path.exists(CONFIG_FILE):
                new_config = {"syncs": {}}
                logger.warning(f"Config file not found: {CONFIG_FILE}")
            else:
                with open(CONFIG_FILE, 'r') as f:
                    new_config = json.load(f)
                logger.info(f"Loaded config with {len(new_config['syncs'])} syncs")
            
            with self.lock:
                # Stop removed tasks
                for name in list(self.tasks.keys()):
                    if name not in new_config["syncs"]:
                        logger.info(f"Removing task {name}")
                        self.tasks[name].stop()
                        del self.tasks[name]
                
                # Update existing tasks
                for name, config in new_config["syncs"].items():
                    if name in self.tasks:
                        # Check if config changed
                        if self.tasks[name].config != config:
                            logger.info(f"Updating task {name} with new config")
                            self.tasks[name].stop()
                            self.tasks[name] = SyncTask(config)
                            self.tasks[name].start()
                    else:
                        # Start new task
                        logger.info(f"Starting new task {name}")
                        self.tasks[name] = SyncTask(config)
                        self.tasks[name].start()
            
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of all tasks."""
        with self.lock:
            return {
                name: task.get_status()
                for name, task in self.tasks.items()
            }

def save_pid():
    """Save the process ID to the PID file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        
        # Use a temporary file to ensure atomic write
        temp_pid_file = f"{PID_FILE}.tmp"
        with open(temp_pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        # Atomically rename the temporary file
        os.rename(temp_pid_file, PID_FILE)
        
        # Set proper permissions
        os.chmod(PID_FILE, 0o644)
    except Exception as e:
        logger.error(f"Error saving PID: {e}")
        sys.exit(1)

def remove_pid():
    """Remove the PID file."""
    try:
        if os.path.exists(PID_FILE):
            # Use a temporary file to ensure atomic removal
            temp_pid_file = f"{PID_FILE}.tmp"
            if os.path.exists(temp_pid_file):
                os.remove(temp_pid_file)
            os.rename(PID_FILE, temp_pid_file)
            os.remove(temp_pid_file)
    except Exception as e:
        logger.error(f"Error removing PID file: {e}")

def check_pid_file():
    """Check if the PID file is valid and the process is running."""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists and is our service
        try:
            process = psutil.Process(pid)
            if process.name().startswith('python') and 'secure_cloud_syncer.manager' in ' '.join(process.cmdline()):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # If we get here, either the process doesn't exist or it's not our service
        remove_pid()
        return False
    except Exception:
        remove_pid()
        return False

def main():
    """Main entry point for the sync manager daemon."""
    # Handle signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        if signum == signal.SIGHUP:
            logger.info("Reloading configuration...")
            manager.reload_config()
        else:
            logger.info("Shutting down...")
            manager.stop()
            remove_pid()
            sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    
    # Save PID
    save_pid()
    
    # Start manager
    manager = SyncManager()
    manager.initialize()
    manager.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()
        remove_pid()
        sys.exit(0)

if __name__ == "__main__":
    main() 