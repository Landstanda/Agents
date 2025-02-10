import os
import subprocess
import psutil
from typing import Optional, List, Dict
from pathlib import Path
import logging
from src.utils.logging import get_logger

logger = get_logger(__name__)

class SystemInteractionError(Exception):
    """Custom exception for SystemInteractionModule errors"""
    pass

class SystemInteractionModule:
    """Module for handling system-level operations like opening files and managing processes"""
    
    def __init__(self):
        self.logger = logger
        self._default_applications = {
            '.txt': 'xdg-open',  # Linux default opener
            '.pdf': 'xdg-open',
            '.doc': 'xdg-open',
            '.docx': 'xdg-open',
            '.xls': 'xdg-open',
            '.xlsx': 'xdg-open',
            '.jpg': 'xdg-open',
            '.png': 'xdg-open',
            '.html': 'xdg-open',
            '.htm': 'xdg-open'
        }
        
    def open_file(self, file_path: str, application: Optional[str] = None) -> bool:
        """
        Open a file with the specified application or system default
        
        Args:
            file_path: Path to the file to open
            application: Optional specific application to use
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            SystemInteractionError: If file doesn't exist or can't be opened
        """
        try:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                raise SystemInteractionError(f"File not found: {file_path}")
            
            if application:
                cmd = [application, str(file_path)]
            else:
                extension = file_path.suffix.lower()
                default_app = self._default_applications.get(extension, 'xdg-open')
                cmd = [default_app, str(file_path)]
                
            self.logger.info(f"Opening file {file_path} with command: {cmd}")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait a bit to check for immediate failures
            try:
                process.wait(timeout=1)
                if process.returncode != 0:
                    _, stderr = process.communicate()
                    raise SystemInteractionError(f"Failed to open file: {stderr.decode()}")
            except subprocess.TimeoutExpired:
                # Process is still running, which is usually good
                pass
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error opening file {file_path}: {str(e)}")
            raise SystemInteractionError(f"Failed to open file: {str(e)}")
    
    def list_running_processes(self) -> List[Dict]:
        """
        Get list of running processes with their details
        
        Returns:
            List[Dict]: List of process information dictionaries
        """
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return processes
        except Exception as e:
            self.logger.error(f"Error listing processes: {str(e)}")
            raise SystemInteractionError(f"Failed to list processes: {str(e)}")
    
    def kill_process(self, pid: int) -> bool:
        """
        Kill a process by its PID
        
        Args:
            pid: Process ID to kill
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            SystemInteractionError: If process cannot be killed
        """
        try:
            process = psutil.Process(pid)
            process.kill()
            return True
        except psutil.NoSuchProcess:
            self.logger.error(f"No process found with PID {pid}")
            raise SystemInteractionError(f"No process found with PID {pid}")
        except psutil.AccessDenied:
            self.logger.error(f"Access denied when trying to kill process {pid}")
            raise SystemInteractionError(f"Access denied when trying to kill process {pid}")
        except Exception as e:
            self.logger.error(f"Error killing process {pid}: {str(e)}")
            raise SystemInteractionError(f"Failed to kill process: {str(e)}") 