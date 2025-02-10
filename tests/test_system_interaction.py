import pytest
import os
import tempfile
from pathlib import Path
from src.modules.system_interaction import SystemInteractionModule, SystemInteractionError

@pytest.fixture
def system_module():
    return SystemInteractionModule()

@pytest.fixture
def temp_test_file():
    # Create a temporary text file for testing
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as f:
        f.write('Test content')
        temp_path = f.name
    yield temp_path
    # Cleanup after test
    try:
        os.remove(temp_path)
    except:
        pass

def test_init(system_module):
    """Test module initialization"""
    assert isinstance(system_module, SystemInteractionModule)
    assert system_module._default_applications['.txt'] == 'xdg-open'

def test_open_file_nonexistent(system_module):
    """Test opening a non-existent file"""
    with pytest.raises(SystemInteractionError) as exc_info:
        system_module.open_file('/path/to/nonexistent/file.txt')
    assert 'File not found' in str(exc_info.value)

def test_open_file_with_default_app(system_module, temp_test_file):
    """Test opening a file with default application"""
    try:
        result = system_module.open_file(temp_test_file)
        assert result is True
    except SystemInteractionError as e:
        # If xdg-open is not available, this is expected
        assert 'Failed to open file' in str(e)

def test_list_running_processes(system_module):
    """Test listing running processes"""
    processes = system_module.list_running_processes()
    assert isinstance(processes, list)
    assert len(processes) > 0
    # Check if each process has the required fields
    for process in processes:
        assert 'pid' in process
        assert 'name' in process
        assert 'cpu_percent' in process
        assert 'memory_percent' in process

def test_kill_nonexistent_process(system_module):
    """Test killing a non-existent process"""
    # Try to kill a process with an invalid PID
    with pytest.raises(SystemInteractionError) as exc_info:
        system_module.kill_process(999999)
    assert 'No process found with PID' in str(exc_info.value)

def test_open_file_with_specific_app(system_module, temp_test_file):
    """Test opening a file with a specific application"""
    try:
        result = system_module.open_file(temp_test_file, application='cat')
        assert result is True
    except SystemInteractionError as e:
        pytest.fail(f"Should not raise an error with 'cat': {str(e)}") 