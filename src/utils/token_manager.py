from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from src.utils.logging import get_logger

logger = get_logger(__name__)

class TokenManager:
    """Manages secure token storage, encryption, backup and recovery"""
    
    def __init__(self, token_dir: str = ".auth_tokens", backup_dir: str = ".auth_tokens_backup", keep_count: int = 5):
        self.token_dir = Path(token_dir)
        self.backup_dir = Path(backup_dir)
        self.keep_count = keep_count
        
        # Create directories if they don't exist
        self.token_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Initialize encryption
        self._init_encryption()
        
    def _init_encryption(self) -> None:
        """Initialize or load encryption key"""
        key_file = self.token_dir / ".key"
        if key_file.exists():
            with open(key_file, "rb") as f:
                self.key = f.read()
        else:
            # Generate a new key
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            # Use environment variables or a secure secret for the password
            password = os.getenv("TOKEN_ENCRYPTION_KEY")
            if password is None:
                password = base64.urlsafe_b64encode(os.urandom(32)).decode()
            self.key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # Save the key securely
            with open(key_file, "wb") as f:
                f.write(self.key)
            
            # Save salt for potential recovery
            with open(self.token_dir / ".salt", "wb") as f:
                f.write(salt)
                
        self.fernet = Fernet(self.key)
        
    def encrypt_token(self, token_data: bytes) -> bytes:
        """Encrypt token data"""
        return self.fernet.encrypt(token_data)
        
    def decrypt_token(self, encrypted_data: bytes) -> bytes:
        """Decrypt token data"""
        return self.fernet.decrypt(encrypted_data)
        
    def store_token(self, service_name: str, token) -> bool:
        """Store a token for a service, creating a backup"""
        try:
            # Serialize and encrypt token
            token_bytes = pickle.dumps(token)
            encrypted_token = self.encrypt_token(token_bytes)
            
            # Store encrypted token
            token_path = self.token_dir / f"{service_name}_token.pickle"
            with open(token_path, "wb") as f:
                f.write(encrypted_token)
            
            # Create backup with microsecond precision
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = self.backup_dir / f"{service_name}_token_{timestamp}.backup"
            backup_data = {
                "timestamp": timestamp,
                "service": service_name,
                "token": base64.b64encode(encrypted_token).decode('utf-8')
            }
            with open(backup_path, "w") as f:
                json.dump(backup_data, f)
            
            logger.debug(f"Created new backup at: {backup_path}")
            
            # Clean up old backups
            self._cleanup_old_backups(service_name)
            
            logger.debug(f"Token stored successfully for service: {service_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to store token for {service_name}: {str(e)}")
            return False
            
    def load_token(self, service_name: str) -> Optional[Any]:
        """Load and decrypt a token"""
        try:
            token_path = self.token_dir / f"{service_name}_token.pickle"
            if not token_path.exists():
                # Try to recover from backup
                if self._recover_token(service_name):
                    return self.load_token(service_name)
                return None
                
            with open(token_path, "rb") as f:
                encrypted_token = f.read()
                
            # Decrypt the token
            token_bytes = self.decrypt_token(encrypted_token)
            
            # Deserialize the token
            token_data = pickle.loads(token_bytes)
            
            logger.debug(f"Token loaded successfully for service: {service_name}")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to load token for {service_name}: {str(e)}")
            # Try to recover from backup
            if self._recover_token(service_name):
                return self.load_token(service_name)
            return None
            
    def _recover_token(self, service_name: str) -> bool:
        """Recover token from latest backup"""
        try:
            # Find latest backup
            backups = sorted(
                self.backup_dir.glob(f"{service_name}_token_*.backup"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if not backups:
                logger.error(f"No backups found for service: {service_name}")
                return False
                
            latest_backup = backups[0]
            
            # Load and verify backup
            with open(latest_backup, "r") as f:
                backup_data = json.load(f)
                
            encrypted_token = base64.b64decode(backup_data["token"])
            
            # Restore token
            token_path = self.token_dir / f"{service_name}_token.pickle"
            with open(token_path, "wb") as f:
                f.write(encrypted_token)
                
            logger.info(f"Token recovered from backup for service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to recover token for {service_name}: {str(e)}")
            return False
            
    def _cleanup_old_backups(self, service_name: str):
        """Keep only the most recent backups based on keep_count"""
        try:
            # Get all backups for this service
            pattern = f"{service_name}_token_*.backup"
            backups = list(self.backup_dir.glob(pattern))
            logger.debug(f"Found {len(backups)} backups for {service_name}")
            
            # Sort backups by timestamp in filename (newest first)
            backups.sort(key=lambda x: str(x), reverse=True)
            logger.debug(f"Sorted backups: {[str(b) for b in backups]}")
            
            # Remove old backups beyond keep_count
            if len(backups) > self.keep_count:
                logger.debug(f"Will remove {len(backups) - self.keep_count} old backups")
                for backup in backups[self.keep_count:]:
                    try:
                        backup.unlink()
                        logger.debug(f"Removed old backup: {backup}")
                    except Exception as e:
                        logger.error(f"Failed to remove backup {backup}: {str(e)}")
            else:
                logger.debug(f"No backups to remove. Current count ({len(backups)}) <= keep_count ({self.keep_count})")
            
            # Get and sort remaining backups
            remaining = list(self.backup_dir.glob(pattern))
            remaining.sort(key=lambda x: str(x), reverse=True)
            return remaining
        except Exception as e:
            logger.error(f"Failed to cleanup old backups for {service_name}: {str(e)}")
            return [] 