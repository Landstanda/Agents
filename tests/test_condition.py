import pytest
from src.modules.conditions import ConditionHandler

@pytest.fixture
def condition_handler():
    return ConditionHandler()

@pytest.mark.asyncio
async def test_basic_field_comparison():
    handler = ConditionHandler()
    
    # Test context
    context = {
        "email": {
            "subject": "Important Meeting",
            "priority": "high",
            "read": False,
            "attachments": 2
        }
    }
    
    # Test equals condition
    params = {
        "conditions": [{
            "if": {
                "field": "email.priority",
                "equals": "high"
            }
        }],
        "context": context
    }
    
    result = await handler.execute(params)
    assert result["status"] == "success"
    assert result["result"] is True

@pytest.mark.asyncio
async def test_complex_and_conditions():
    handler = ConditionHandler()
    
    context = {
        "email": {
            "subject": "Project Update",
            "unread": True,
            "attachments": 3
        }
    }
    
    params = {
        "conditions": {
            "and": [
                {
                    "field": "email.unread",
                    "equals": True
                },
                {
                    "field": "email.attachments",
                    "greater_than": 2
                }
            ]
        },
        "context": context
    }
    
    result = await handler.execute(params)
    assert result["status"] == "success"
    assert result["result"] is True

@pytest.mark.asyncio
async def test_loop_condition():
    handler = ConditionHandler()
    
    context = {
        "remaining_emails": 5,
        "processed": 3
    }
    
    params = {
        "loop_check": {
            "while": "remaining_emails",
            "then_step": 1,
            "else_step": "complete"
        },
        "context": context
    }
    
    result = await handler.execute(params)
    assert result["status"] == "success"
    assert result["continue_loop"] is True
    assert result["next_step"] == 1

@pytest.mark.asyncio
async def test_nested_conditions():
    handler = ConditionHandler()
    
    context = {
        "email": {
            "category": "work",
            "flags": {
                "important": True,
                "follow_up": True
            }
        }
    }
    
    params = {
        "conditions": {
            "or": [
                {
                    "and": [
                        {
                            "field": "email.category",
                            "equals": "work"
                        },
                        {
                            "field": "email.flags.important",
                            "equals": True
                        }
                    ]
                },
                {
                    "field": "email.flags.follow_up",
                    "equals": True
                }
            ]
        },
        "context": context
    }
    
    result = await handler.execute(params)
    assert result["status"] == "success"
    assert result["result"] is True

@pytest.mark.asyncio
async def test_error_handling():
    handler = ConditionHandler()
    
    # Test invalid field path
    params = {
        "conditions": [{
            "field": "nonexistent.path",
            "equals": "value"
        }],
        "context": {}
    }
    
    result = await handler.execute(params)
    assert result["status"] == "error"
    assert "error" in result

@pytest.mark.asyncio
async def test_existence_check():
    handler = ConditionHandler()
    
    context = {
        "email": {
            "attachments": []
        }
    }
    
    params = {
        "conditions": {
            "exists": "email.attachments"
        },
        "context": context
    }
    
    result = await handler.execute(params)
    assert result["status"] == "success"
    assert result["result"] is True