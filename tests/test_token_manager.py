import pytest
import os
import json
import pickle
import base64
import time
from pathlib import Path
from datetime import datetime
from src.utils.token_manager import TokenManager
from google.oauth2.credentials import Credentials

@pytest.fixture
def test_dirs(tmp_path):
    """Create temporary directories for testing"""
    token_dir = tmp_path / ".auth_tokens"
    backup_dir = tmp_path / ".auth_tokens_backup"
    token_dir.mkdir()
    backup_dir.mkdir()
    return token_dir, backup_dir

@pytest.fixture
def token_manager(test_dirs):
    """Create a TokenManager instance with test directories"""
    token_dir, backup_dir = test_dirs
    # Set a fixed encryption key for testing
    os.environ["TOKEN_ENCRYPTION_KEY"] = "test-encryption-key-for-unit-tests"
    return TokenManager(str(token_dir), str(backup_dir))

@pytest.fixture
def sample_token_data():
    """Create sample token data for testing"""
    return {
        "access_token": "ya29.test-token",
        "refresh_token": "1//test-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "scopes": ["https://www.googleapis.com/auth/calendar"]
    }

@pytest.fixture
def sample_credentials(sample_token_data):
    """Create a sample Credentials object"""
    return Credentials(
        token=sample_token_data["access_token"],
        refresh_token=sample_token_data["refresh_token"],
        token_uri=sample_token_data["token_uri"],
        client_id=sample_token_data["client_id"],
        client_secret=sample_token_data["client_secret"],
        scopes=sample_token_data["scopes"]
    )

def test_init_encryption(token_manager, test_dirs):
    """Test encryption key initialization"""
    token_dir, _ = test_dirs
    key_file = token_dir / ".key"
    salt_file = token_dir / ".salt"
    
    # Check that key and salt files were created
    assert key_file.exists()
    assert salt_file.exists()
    
    # Check that key is valid base64
    with open(key_file, "rb") as f:
        key_data = f.read()
    try:
        key_bytes = base64.urlsafe_b64decode(key_data)
        assert len(key_bytes) == 32  # Fernet keys are 32 bytes
    except Exception as e:
        pytest.fail(f"Invalid key format: {str(e)}")

def test_token_encryption(token_manager, sample_token_data):
    """Test token encryption and decryption"""
    # Convert token to bytes
    token_bytes = pickle.dumps(sample_token_data)
    
    # Encrypt
    encrypted = token_manager.encrypt_token(token_bytes)
    assert encrypted != token_bytes
    
    # Decrypt
    decrypted = token_manager.decrypt_token(encrypted)
    assert decrypted == token_bytes
    
    # Verify decrypted data
    recovered_data = pickle.loads(decrypted)
    assert recovered_data == sample_token_data

def test_store_and_load_token(token_manager, sample_credentials):
    """Test storing and loading a token"""
    service_name = "test_service"
    
    # Store token
    assert token_manager.store_token(service_name, sample_credentials)
    
    # Check that token file exists
    token_path = token_manager.token_dir / f"{service_name}_token.pickle"
    assert token_path.exists()
    
    # Load token
    loaded_creds = token_manager.load_token(service_name)
    assert isinstance(loaded_creds, Credentials)
    assert loaded_creds.token == sample_credentials.token
    assert loaded_creds.refresh_token == sample_credentials.refresh_token
    assert loaded_creds.scopes == sample_credentials.scopes

def test_token_backup(token_manager, sample_credentials):
    """Test token backup creation"""
    service_name = "test_service"
    
    # Store token (which creates backup)
    token_manager.store_token(service_name, sample_credentials)
    
    # Check that backup was created
    backups = list(token_manager.backup_dir.glob(f"{service_name}_token_*.backup"))
    assert len(backups) == 1
    
    # Verify backup content
    with open(backups[0], "r") as f:
        backup_data = json.load(f)
    assert "timestamp" in backup_data
    assert backup_data["service"] == service_name
    assert "token" in backup_data

def test_token_recovery(token_manager, sample_credentials, test_dirs):
    """Test token recovery from backup"""
    service_name = "test_service"
    token_dir, _ = test_dirs
    
    # Store token
    token_manager.store_token(service_name, sample_credentials)
    
    # Delete original token file
    token_path = token_dir / f"{service_name}_token.pickle"
    token_path.unlink()
    
    # Try to load token (should trigger recovery)
    recovered_creds = token_manager.load_token(service_name)
    assert recovered_creds is not None
    assert isinstance(recovered_creds, Credentials)
    assert recovered_creds.token == sample_credentials.token

def test_backup_rotation(token_manager, sample_credentials):
    """Test that old backups are cleaned up"""
    service_name = "test_service"
    
    # Create multiple backups with delays
    for i in range(7):  # More than keep_count
        token_manager.store_token(service_name, sample_credentials)
        # Ensure each backup has a unique timestamp
        time.sleep(0.1)
    
    # Get sorted backups after cleanup
    backups = token_manager._cleanup_old_backups(service_name)
    
    # Check that only 5 backups are kept
    assert len(backups) == 5
    
    # Verify backups are the most recent ones (sorted by filename)
    backup_names = [str(backup) for backup in backups]
    sorted_names = sorted(backup_names, reverse=True)
    assert backup_names == sorted_names  # Should be in descending order

def test_invalid_token_recovery(token_manager):
    """Test behavior with invalid/missing tokens"""
    service_name = "nonexistent_service"
    
    # Try to load nonexistent token
    result = token_manager.load_token(service_name)
    assert result is None
    
    # Try to recover nonexistent backup
    assert not token_manager._recover_token(service_name)

def test_encryption_with_env_key(test_dirs):
    """Test encryption with environment variable key"""
    # Set a specific encryption key
    test_key = "specific-test-key-for-encryption-test"
    os.environ["TOKEN_ENCRYPTION_KEY"] = test_key
    
    # Create two token managers
    token_dir, backup_dir = test_dirs
    manager1 = TokenManager(str(token_dir), str(backup_dir))
    manager2 = TokenManager(str(token_dir), str(backup_dir))
    
    # Test that both can encrypt/decrypt the same data
    test_data = b"test data"
    encrypted = manager1.encrypt_token(test_data)
    decrypted = manager2.decrypt_token(encrypted)
    assert decrypted == test_data

def test_credentials_encryption(token_manager, sample_credentials):
    """Test encryption/decryption of Credentials object"""
    # Store credentials
    service_name = "test_credentials"
    assert token_manager.store_token(service_name, sample_credentials)
    
    # Load credentials
    loaded_creds = token_manager.load_token(service_name)
    assert isinstance(loaded_creds, Credentials)
    assert loaded_creds.token == sample_credentials.token
    assert loaded_creds.refresh_token == sample_credentials.refresh_token
    assert loaded_creds.scopes == sample_credentials.scopes
    assert loaded_creds.token_uri == sample_credentials.token_uri
    assert loaded_creds.client_id == sample_credentials.client_id
    assert loaded_creds.client_secret == sample_credentials.client_secret 