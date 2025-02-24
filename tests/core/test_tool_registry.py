import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import importlib
from pathlib import Path
from src.core.registry.tool_registry import ToolRegistry
from src.core.module_interface import BaseModule

# Mock tool classes for testing
class ValidTool(BaseModule):
    """Valid tool implementation for testing"""
    capabilities = ["test_capability"]
    
    async def execute(self, **kwargs):
        """Valid async execute method"""
        return {"status": "success"}

class InvalidTool:
    """Invalid tool without proper inheritance"""
    pass

class NoCapabilitiesTool(BaseModule):
    """Invalid tool without capabilities"""
    capabilities = []  # Empty capabilities list
    
    async def execute(self, **kwargs):
        return {"status": "success"}

class NoExecuteTool(BaseModule):
    """Invalid tool without execute method"""
    capabilities = ["test_capability"]
    execute = None  # Override execute method with None

class SyncExecuteTool(BaseModule):
    """Invalid tool with sync execute method"""
    capabilities = ["test_capability"]
    
    def execute(self, **kwargs):
        return {"status": "success"}

@pytest.fixture
def mock_workspace_root(tmp_path):
    """Create a temporary workspace root"""
    return tmp_path

@pytest.fixture
def tool_registry(mock_workspace_root):
    """Create a ToolRegistry instance with mocked workspace root"""
    registry = ToolRegistry(tools_path=str(mock_workspace_root / "src/modules"))
    registry.workspace_root = mock_workspace_root
    return registry

@pytest.mark.asyncio
class TestToolRegistry:
    """Tests for the ToolRegistry class"""
    
    async def test_initialization(self, tool_registry):
        """Test basic registry initialization"""
        assert tool_registry.name == "tool"
        assert not tool_registry.initialized
        assert isinstance(tool_registry.items, dict)
        assert len(tool_registry.items) == 0
    
    async def test_validate_valid_tool(self, tool_registry):
        """Test validation of a valid tool class"""
        is_valid = await tool_registry.validate_item(ValidTool)
        assert is_valid
    
    async def test_validate_invalid_inheritance(self, tool_registry):
        """Test validation of a tool without proper inheritance"""
        is_valid = await tool_registry.validate_item(InvalidTool)
        assert not is_valid
    
    async def test_validate_missing_capabilities(self, tool_registry):
        """Test validation of a tool without capabilities"""
        is_valid = await tool_registry.validate_item(NoCapabilitiesTool)
        assert not is_valid
    
    async def test_validate_missing_execute(self, tool_registry):
        """Test validation of a tool without execute method"""
        is_valid = await tool_registry.validate_item(NoExecuteTool)
        assert not is_valid
    
    async def test_validate_sync_execute(self, tool_registry):
        """Test validation of a tool with synchronous execute method"""
        is_valid = await tool_registry.validate_item(SyncExecuteTool)
        assert not is_valid
    
    async def test_register_valid_tool(self, tool_registry):
        """Test registration of a valid tool"""
        await tool_registry.register_item("valid_tool", ValidTool)
        assert "valid_tool" in tool_registry.items
        assert tool_registry.items["valid_tool"] == ValidTool
    
    async def test_register_invalid_tool(self, tool_registry):
        """Test registration of an invalid tool"""
        with pytest.raises(ValueError):
            await tool_registry.register_item("invalid_tool", InvalidTool)
        assert "invalid_tool" not in tool_registry.items
    
    async def test_get_registered_tool(self, tool_registry):
        """Test retrieving a registered tool"""
        await tool_registry.register_item("test_tool", ValidTool)
        tool = tool_registry.get_item("test_tool")
        assert tool == ValidTool
    
    async def test_get_nonexistent_tool(self, tool_registry):
        """Test retrieving a non-existent tool"""
        tool = tool_registry.get_item("nonexistent")
        assert tool is None
    
    async def test_load_tools_from_directory(self, mock_workspace_root):
        """Test loading tools from a directory"""
        # Create mock tool files
        modules_dir = mock_workspace_root / "src" / "modules"
        modules_dir.mkdir(parents=True)
        
        # Create __init__.py to make it a package
        with open(modules_dir / "__init__.py", "w") as f:
            f.write("")
        
        # Create a valid tool file
        valid_tool_content = '''
from src.core.module_interface import BaseModule

class TestTool(BaseModule):
    capabilities = ["test"]
    async def execute(self, **kwargs):
        return {"status": "success"}
'''
        with open(modules_dir / "test_tool.py", "w") as f:
            f.write(valid_tool_content)
        
        # Add src to Python path
        import sys
        sys.path.insert(0, str(mock_workspace_root))
        
        try:
            # Initialize registry with mock directory
            registry = ToolRegistry(tools_path=str(modules_dir))
            registry.workspace_root = mock_workspace_root
            
            # Load tools
            await registry.load_items()
            
            # Verify tool was loaded
            assert "test_tool" in registry.items
            assert registry.initialized
        finally:
            # Clean up sys.path
            sys.path.pop(0)
    
    async def test_load_tools_invalid_directory(self, tool_registry):
        """Test loading tools from non-existent directory"""
        await tool_registry.load_items()
        assert len(tool_registry.items) == 0
        assert tool_registry.initialized
    
    async def test_load_tools_with_errors(self, mock_workspace_root):
        """Test loading tools with some invalid files"""
        # Create mock tool files
        modules_dir = mock_workspace_root / "src" / "modules"
        modules_dir.mkdir(parents=True)
        
        # Create __init__.py files
        (mock_workspace_root / "src").mkdir(parents=True, exist_ok=True)
        (mock_workspace_root / "src" / "__init__.py").write_text("")
        (mock_workspace_root / "src" / "core").mkdir(parents=True, exist_ok=True)
        (mock_workspace_root / "src" / "core" / "__init__.py").write_text("")
        (modules_dir / "__init__.py").write_text("")
        
        # Create module_interface.py
        module_interface_content = '''
class BaseModule:
    """Base class for all modules"""
    capabilities = []
    
    async def execute(self, **kwargs):
        raise NotImplementedError
'''
        (mock_workspace_root / "src" / "core" / "module_interface.py").write_text(module_interface_content)
        
        # Create a valid tool file
        valid_tool_content = '''
from src.core.module_interface import BaseModule

class TestTool(BaseModule):
    capabilities = ["test"]
    async def execute(self, **kwargs):
        return {"status": "success"}
'''
        (modules_dir / "valid_tool.py").write_text(valid_tool_content)
        
        # Create an invalid tool file
        invalid_tool_content = '''
from src.core.module_interface import BaseModule

class InvalidTool:
    pass
'''
        (modules_dir / "invalid_tool.py").write_text(invalid_tool_content)
        
        # Add workspace root to Python path
        import sys
        sys.path.insert(0, str(mock_workspace_root))
        
        try:
            # Initialize registry with mock directory
            registry = ToolRegistry(tools_path=str(modules_dir))
            registry.workspace_root = mock_workspace_root
            
            # Load tools
            await registry.load_items()
            
            # Verify only valid tool was loaded
            assert "valid_tool" in registry.items
            assert "invalid_tool" not in registry.items
            assert registry.initialized
        finally:
            # Clean up sys.path
            sys.path.pop(0)
    
    async def test_registry_contains(self, tool_registry):
        """Test the __contains__ method"""
        await tool_registry.register_item("test_tool", ValidTool)
        assert "test_tool" in tool_registry
        assert "nonexistent" not in tool_registry
    
    async def test_registry_len(self, tool_registry):
        """Test the __len__ method"""
        assert len(tool_registry) == 0
        await tool_registry.register_item("test_tool", ValidTool)
        assert len(tool_registry) == 1
    
    async def test_list_items(self, tool_registry):
        """Test listing all registered tools"""
        await tool_registry.register_item("tool1", ValidTool)
        await tool_registry.register_item("tool2", ValidTool)
        
        items = tool_registry.list_items()
        assert len(items) == 2
        assert "tool1" in items
        assert "tool2" in items
        
        # Verify it's a copy
        items["tool3"] = ValidTool
        assert "tool3" not in tool_registry.items 