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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.rclone/scs_manager.log"))
    ]
)
logger = logging.getLogger("secure_cloud_syncer.manager")

# Add a rotating file handler for better log management
rotating_handler = RotatingFileHandler(
    os.path.expanduser("~/.rclone/scs_manager.log"),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(rotating_handler)

# Set up error logging to a separate file
error_handler = RotatingFileHandler(
    os.path.expanduser("~/.rclone/scs_manager.error.log"),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(message)s'))
logger.addHandler(error_handler)

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
    """Represents a running sync task."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.process: Optional[multiprocessing.Process] = None
        self.start_time: Optional[float] = None
        self.last_error: Optional[str] = None
        self.error_count: int = 0
        self.restart_count: int = 0
        self.max_restarts: int = 5
        self.restart_delay: int = 30  # seconds
    
    def start(self):
        """Start the sync task."""
        if self.process is not None and self.process.is_alive():
            logger.warning(f"Task {self.name} is already running")
            return
        try:
            logger.info(f"Starting task {self.name} with config: {self.config}")
            # Start monitoring with the appropriate direction
            self.process = monitor.start_monitoring(
                self.config["local_dir"],
                self.config["remote_dir"],
                self.config["exclude_resource_forks"],
                self.config["debounce_time"],
                background=True,
                direction=self.config["mode"]  # Use the mode as the direction
            )
            self.start_time = time.time()
            self.last_error = None
            self.error_count = 0
            self.restart_count = 0
            logger.info(f"Task {self.name} started successfully")
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            logger.error(f"Error starting task {self.name}: {e}")
            raise
    
    def stop(self):
        """Stop the sync task."""
        if self.process is None or not self.process.is_alive():
            logger.warning(f"Task {self.name} is not running")
            return
        
        try:
            logger.info(f"Stopping task {self.name} (PID: {self.process.pid})")
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                logger.warning(f"Task {self.name} did not terminate gracefully, forcing kill")
                self.process.kill()
                self.process.join()
            logger.info(f"Stopped task {self.name}")
        except Exception as e:
            logger.error(f"Error stopping task {self.name}: {e}", exc_info=True)
        finally:
            self.process = None
            self.start_time = None
    
    def is_running(self) -> bool:
        """Check if the task is running."""
        if self.process is None:
            return False
        if not self.process.is_alive():
            logger.warning(f"Task {self.name} process is not alive")
            return False
        return True
    
    def check_health(self):
        """Check the health of the task and restart if necessary."""
        if not self.is_running():
            if self.restart_count < self.max_restarts:
                logger.warning(f"Task {self.name} is not running, attempting restart ({self.restart_count + 1}/{self.max_restarts})")
                time.sleep(self.restart_delay)
                self.restart_count += 1
                self.start()
            else:
                logger.error(f"Task {self.name} failed to start after {self.max_restarts} attempts")
                logger.error(f"Last error: {self.last_error}")
                logger.error(f"Total errors: {self.error_count}")

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
    
    def start(self):
        """Start the sync manager."""
        if self.running:
            logger.warning("Sync manager is already running")
            return
        
        # Start watching the config file
        self.observer.schedule(self.config_watcher, os.path.dirname(CONFIG_FILE), recursive=False)
        self.observer.start()
        
        # Load initial config
        self.reload_config()
        
        # Start health check thread
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        
        # Start watchdog thread
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()
        
        self.running = True
        logger.info("Sync manager started")
    
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
            
            # Start new service process
            subprocess.Popen([sys.executable, "-m", "secure_cloud_syncer.manager"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
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
                            self.tasks[name] = SyncTask(name, config)
                            self.tasks[name].start()
                    else:
                        # Start new task
                        logger.info(f"Starting new task {name}")
                        self.tasks[name] = SyncTask(name, config)
                        self.tasks[name].start()
            
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of all tasks."""
        with self.lock:
            return {
                name: {
                    "running": task.is_running(),
                    "start_time": task.start_time,
                    "config": task.config,
                    "error_count": task.error_count,
                    "restart_count": task.restart_count,
                    "last_error": task.last_error
                }
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