import pytest
from src.core.success_evaluator import SuccessEvaluator, DotDict
from src.core.module_interface import ModuleResponse

@pytest.fixture
def evaluator():
    return SuccessEvaluator()

@pytest.fixture
def sample_response():
    return ModuleResponse(
        success=True,
        data={
            "user": {
                "name": "John",
                "age": 30,
                "active": True
            },
            "credentials": {
                "valid": True,
                "expires_in": 3600
            }
        },
        error=None
    )

class TestDotDict:
    def test_dot_dict_initialization(self):
        """Test DotDict initialization and basic access"""
        data = {"a": 1, "b": {"c": 2}}
        dot_dict = DotDict(data)
        
        assert dot_dict.a == 1
        assert dot_dict.b.c == 2
        assert dot_dict["a"] == 1
        assert dot_dict.get("a") == 1
        
    def test_dot_dict_missing_keys(self):
        """Test DotDict behavior with missing keys"""
        dot_dict = DotDict({"a": 1})
        
        assert dot_dict.missing is None
        assert dot_dict.get("missing") is None
        assert dot_dict.get("missing", "default") == "default"
        
    def test_dot_dict_nested_access(self):
        """Test DotDict nested dictionary access"""
        data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        dot_dict = DotDict(data)
        
        assert dot_dict.level1.level2.level3 == "value"
        assert dot_dict["level1"]["level2"]["level3"] == "value"
        
    def test_dot_dict_bool_operations(self):
        """Test DotDict boolean operations"""
        assert bool(DotDict({"a": 1})) is True
        assert bool(DotDict({})) is False
        
    def test_dot_dict_comparison(self):
        """Test DotDict comparison operations"""
        dict1 = DotDict({"a": 1})
        dict2 = DotDict({"a": 1})
        regular_dict = {"a": 1}
        
        assert dict1 == dict2
        assert dict1 == regular_dict

class TestSuccessEvaluator:
    def test_simple_success_evaluation(self, evaluator, sample_response):
        """Test basic success criteria evaluation"""
        criteria = {
            "type": "all",
            "conditions": [
                "response.success == True",
                "response.data.user.active == True"
            ]
        }
        
        result = evaluator.evaluate(criteria, sample_response)
        assert result["success"] is True
        
    def test_any_condition_evaluation(self, evaluator):
        """Test 'any' type condition evaluation"""
        response = ModuleResponse(
            success=False,
            data={"status": "pending"},
            error=None
        )
        
        criteria = {
            "type": "any",
            "conditions": [
                "response.success == True",
                "response.data.status == 'pending'"
            ]
        }
        
        result = evaluator.evaluate(criteria, response)
        assert result["success"] is True
        
    def test_custom_expression_evaluation(self, evaluator, sample_response):
        """Test custom expression evaluation"""
        criteria = {
            "type": "custom",
            "expression": "len(response.data.user.name) > 2 and response.data.credentials.valid"
        }
        
        result = evaluator.evaluate(criteria, sample_response)
        assert result["success"] is True
        
    def test_failure_handling(self, evaluator):
        """Test failure handling with conditional actions"""
        response = ModuleResponse(
            success=False,
            data=None,
            error="Authentication failed"
        )
        
        criteria = {
            "type": "all",
            "conditions": ["response.success == True"],
            "on_failure": {
                "actions": [
                    {
                        "condition": "'Authentication failed' in str(response.error)",
                        "action": "retry_auth",
                        "target_step": "authenticate"
                    }
                ]
            }
        }
        
        result = evaluator.evaluate(criteria, response)
        assert result["success"] is False
        assert result["action"] == "retry_auth"
        assert result["next_step"] == "authenticate"
        
    def test_nested_condition_evaluation(self, evaluator, sample_response):
        """Test evaluation of deeply nested conditions"""
        criteria = {
            "type": "all",
            "conditions": [
                "response.data.user.age > 25",
                "response.data.credentials.expires_in > 1800"
            ]
        }
        
        result = evaluator.evaluate(criteria, sample_response)
        assert result["success"] is True
        
    def test_error_handling(self, evaluator):
        """Test handling of invalid conditions"""
        criteria = {
            "type": "all",
            "conditions": [
                "response.invalid.path.access",
                "response.nonexistent"
            ]
        }
        
        result = evaluator.evaluate(criteria, ModuleResponse(success=True))
        assert result["success"] is False
        assert result["action"] == "error"
        
    def test_success_with_next_step(self, evaluator, sample_response):
        """Test success with next step specification"""
        criteria = {
            "type": "all",
            "conditions": ["response.success == True"],
            "on_success": {
                "next_step": "process_data",
                "action": "continue"
            }
        }
        
        result = evaluator.evaluate(criteria, sample_response)
        assert result["success"] is True
        assert result["next_step"] == "process_data"
        assert result["action"] == "continue"
        
    def test_multiple_failure_conditions(self, evaluator):
        """Test multiple failure conditions with different actions"""
        response = ModuleResponse(
            success=False,
            data={"status": "rate_limited"},
            error="Rate limit exceeded"
        )
        
        criteria = {
            "type": "all",
            "conditions": ["response.success == True"],
            "on_failure": {
                "actions": [
                    {
                        "condition": "'rate limit' in str(response.error).lower()",
                        "action": "wait",
                        "params": {"delay": 60}
                    },
                    {
                        "condition": "response.data.status == 'rate_limited'",
                        "action": "backoff",
                        "target_step": "retry"
                    }
                ]
            }
        }
        
        result = evaluator.evaluate(criteria, response)
        assert result["success"] is False
        assert result["action"] == "wait"
        assert "delay" in result["action_params"]
        
    def test_empty_conditions(self, evaluator):
        """Test handling of empty condition lists"""
        criteria = {
            "type": "all",
            "conditions": []
        }
        
        result = evaluator.evaluate(criteria, ModuleResponse(success=True))
        assert result["success"] is False
        
    @pytest.mark.parametrize("invalid_type", ["unknown", "invalid", None])
    def test_invalid_criteria_type(self, evaluator, invalid_type):
        """Test handling of invalid criteria types"""
        criteria = {
            "type": invalid_type,
            "conditions": ["response.success == True"]
        }
        
        result = evaluator.evaluate(criteria, ModuleResponse(success=True))
        assert result["success"] is False
        assert result["action"] == "error"

if __name__ == "__main__":
    pytest.main(["-v", "test_success_evaluator.py"]) 