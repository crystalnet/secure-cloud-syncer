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
from pathlib import Path
from typing import Dict, Any, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
                self.manager.reload_config()

class SyncTask:
    """Represents a running sync task."""
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.process: Optional[multiprocessing.Process] = None
        self.start_time: Optional[float] = None
    
    def start(self):
        """Start the sync task."""
        if self.process is not None and self.process.is_alive():
            logger.warning(f"Task {self.name} is already running")
            return
        
        try:
            if self.config["mode"] == "one-way":
                self.process = one_way.sync_directory(
                    self.config["local_dir"],
                    self.config["remote_dir"],
                    self.config["exclude_resource_forks"],
                    background=True
                )
            elif self.config["mode"] == "bidirectional":
                self.process = bidirectional.sync_bidirectional(
                    self.config["local_dir"],
                    self.config["remote_dir"],
                    self.config["exclude_resource_forks"],
                    background=True
                )
            elif self.config["mode"] == "monitor":
                self.process = monitor.start_monitoring(
                    self.config["local_dir"],
                    self.config["remote_dir"],
                    self.config["exclude_resource_forks"],
                    self.config["debounce_time"],
                    background=True
                )
            
            self.start_time = time.time()
            logger.info(f"Started task {self.name}")
        except Exception as e:
            logger.error(f"Error starting task {self.name}: {e}")
            self.process = None
            self.start_time = None
    
    def stop(self):
        """Stop the sync task."""
        if self.process is None or not self.process.is_alive():
            logger.warning(f"Task {self.name} is not running")
            return
        
        try:
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()
            logger.info(f"Stopped task {self.name}")
        except Exception as e:
            logger.error(f"Error stopping task {self.name}: {e}")
        finally:
            self.process = None
            self.start_time = None
    
    def is_running(self) -> bool:
        """Check if the task is running."""
        return self.process is not None and self.process.is_alive()

class SyncManager:
    """Manages sync tasks and handles config updates."""
    def __init__(self):
        self.tasks: Dict[str, SyncTask] = {}
        self.running = False
        self.config_watcher = ConfigWatcher(self)
        self.observer = Observer()
        self.lock = threading.Lock()
    
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
    
    def reload_config(self):
        """Reload the configuration and update tasks."""
        if not self.running:
            return
        
        try:
            # Load new config
            if not os.path.exists(CONFIG_FILE):
                new_config = {"syncs": {}}
            else:
                with open(CONFIG_FILE, 'r') as f:
                    new_config = json.load(f)
            
            with self.lock:
                # Stop removed tasks
                for name in list(self.tasks.keys()):
                    if name not in new_config["syncs"]:
                        self.tasks[name].stop()
                        del self.tasks[name]
                
                # Update existing tasks
                for name, config in new_config["syncs"].items():
                    if name in self.tasks:
                        # Check if config changed
                        if self.tasks[name].config != config:
                            self.tasks[name].stop()
                            self.tasks[name] = SyncTask(name, config)
                            self.tasks[name].start()
                    else:
                        # Start new task
                        self.tasks[name] = SyncTask(name, config)
                        self.tasks[name].start()
            
            logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the status of all tasks."""
        with self.lock:
            return {
                name: {
                    "running": task.is_running(),
                    "start_time": task.start_time,
                    "config": task.config
                }
                for name, task in self.tasks.items()
            }

def save_pid():
    """Save the process ID to the PID file."""
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Error saving PID: {e}")
        sys.exit(1)

def remove_pid():
    """Remove the PID file."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception as e:
        logger.error(f"Error removing PID file: {e}")

def main():
    """Main entry point for the sync manager daemon."""
    # Handle signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        manager.stop()
        remove_pid()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
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