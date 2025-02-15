#!/usr/bin/env python3

import os
import json
import base64
import hashlib
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class BasicAuthModule:
    """Module for handling basic username/password authentication."""
    
    def __init__(self):
        load_dotenv()
        self.credentials_file = os.path.join(
            os.getenv('CREDENTIALS_DIR', '.credentials'),
            'basic_auth.json'
        )
        self._init_encryption()
        self._load_credentials()
        self.sessions = {}
        
    def _init_encryption(self):
        """Initialize encryption key for secure storage."""
        # Get or generate encryption key
        key_file = os.path.join(
            os.getenv('CREDENTIALS_DIR', '.credentials'),
            '.key'
        )
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(self.key)
                
        self.cipher = Fernet(self.key)
        
    def _load_credentials(self):
        """Load encrypted credentials from storage."""
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, 'r') as f:
                    encrypted_data = f.read()
                    if encrypted_data:
                        decrypted_data = self.cipher.decrypt(encrypted_data.encode())
                        self.credentials = json.loads(decrypted_data)
                    else:
                        self.credentials = {}
            else:
                self.credentials = {}
        except Exception as e:
            logger.error(f"Failed to load credentials: {str(e)}")
            self.credentials = {}
            
    def _save_credentials(self):
        """Save encrypted credentials to storage."""
        try:
            os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
            encrypted_data = self.cipher.encrypt(json.dumps(self.credentials).encode())
            with open(self.credentials_file, 'w') as f:
                f.write(encrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to save credentials: {str(e)}")
            
    def _hash_password(self, password: str) -> str:
        """Create secure hash of password."""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return base64.b64encode(salt + key).decode('utf-8')
        
    def _verify_password(self, stored_hash: str, password: str) -> bool:
        """Verify password against stored hash."""
        try:
            decoded = base64.b64decode(stored_hash.encode('utf-8'))
            salt = decoded[:32]
            key = decoded[32:]
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
            return key == new_key
        except Exception:
            return False
            
    def store_credentials(self, service: str, username: str, password: str) -> bool:
        """
        Store credentials for a service securely.
        
        Args:
            service (str): Name of the service
            username (str): Username for the service
            password (str): Password for the service
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if service not in self.credentials:
                self.credentials[service] = {}
                
            self.credentials[service][username] = {
                'hash': self._hash_password(password),
                'created_at': datetime.now().isoformat()
            }
            
            self._save_credentials()
            return True
        except Exception as e:
            logger.error(f"Failed to store credentials: {str(e)}")
            return False
            
    def verify_credentials(self, service: str, username: str, password: str) -> bool:
        """
        Verify credentials for a service.
        
        Args:
            service (str): Name of the service
            username (str): Username to verify
            password (str): Password to verify
            
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        try:
            if service not in self.credentials:
                return False
                
            if username not in self.credentials[service]:
                return False
                
            stored = self.credentials[service][username]
            return self._verify_password(stored['hash'], password)
        except Exception as e:
            logger.error(f"Failed to verify credentials: {str(e)}")
            return False
            
    def create_session(self, service: str, username: str, password: str) -> Optional[str]:
        """
        Create an authenticated session.
        
        Args:
            service (str): Name of the service
            username (str): Username for authentication
            password (str): Password for authentication
            
        Returns:
            str: Session token if successful, None otherwise
        """
        try:
            if not self.verify_credentials(service, username, password):
                return None
                
            # Generate session token
            token = base64.b64encode(os.urandom(32)).decode('utf-8')
            
            # Store session info
            self.sessions[token] = {
                'service': service,
                'username': username,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=24)
            }
            
            return token
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            return None
            
    def verify_session(self, token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify if a session is valid and not expired.
        
        Args:
            token (str): Session token to verify
            
        Returns:
            Tuple[bool, Optional[Dict]]: (is_valid, session_info if valid else None)
        """
        try:
            if token not in self.sessions:
                return False, None
                
            session = self.sessions[token]
            
            # Check if session has expired
            if datetime.now() > session['expires_at']:
                del self.sessions[token]
                return False, None
                
            return True, {
                'service': session['service'],
                'username': session['username'],
                'created_at': session['created_at'].isoformat(),
                'expires_at': session['expires_at'].isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to verify session: {str(e)}")
            return False, None
            
    def end_session(self, token: str) -> bool:
        """
        End a session by removing it.
        
        Args:
            token (str): Session token to end
            
        Returns:
            bool: True if session was ended, False otherwise
        """
        try:
            if token in self.sessions:
                del self.sessions[token]
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to end session: {str(e)}")
            return False
            
    def remove_credentials(self, service: str, username: str) -> bool:
        """
        Remove stored credentials for a service.
        
        Args:
            service (str): Name of the service
            username (str): Username to remove
            
        Returns:
            bool: True if credentials were removed, False otherwise
        """
        try:
            if service in self.credentials and username in self.credentials[service]:
                del self.credentials[service][username]
                if not self.credentials[service]:
                    del self.credentials[service]
                self._save_credentials()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove credentials: {str(e)}")
            return False 