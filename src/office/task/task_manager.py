from typing import Dict, Any, Optional, List
import logging
import asyncio
from datetime import datetime
import heapq

logger = logging.getLogger(__name__)

class TaskManager:
    """
    Manages the execution of task recipes.
    Handles the actual implementation of tasks, tracking their progress,
    and managing any necessary resources or dependencies.
    """
    
    def __init__(self):
        """Initialize the task manager."""
        self.active_task = None  # Currently running task
        self.task_history = []  # Keep history of completed tasks
        self._task_queue = []  # Priority queue for pending tasks
        self._task_lock = asyncio.Lock()  # Lock for task queue operations
        self._processing = False  # Flag to track if we're processing tasks
        self._request_map = {}  # Map task_id to request_id
        logger.info("Task Manager initialized")
    
    async def execute_recipe(self, recipe: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queue a recipe for execution with the given context.
        
        Args:
            recipe: The recipe to execute
            context: Execution context including:
                - nlp_result: NLP processing result with urgency indicator
                - user_info: User information
                - channel_id: Slack channel ID
                - thread_ts: Thread timestamp if in thread
                - request: Request object if available
                - Any additional entities needed for recipe execution
                
        Returns:
            Dict containing:
                - status: "queued" or "error"
                - details: Additional information
                - error: Error message if status is "error"
                - task_id: ID of the queued task
        """
        try:
            # Get urgency from request if available, otherwise from NLP result
            request = context.get("request")
            urgency = (request.priority if request else 
                      context.get("nlp_result", {}).get("urgency", 0.5))
            
            # Create task entry
            task_id = f"{recipe['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Extract entities from context
            entities = {}
            for key, value in context.items():
                if key not in ["nlp_result", "user_info", "channel_id", "thread_ts", "request"]:
                    entities[key] = value
            
            # Add entities to context
            execution_context = {
                "entities": entities,
                **context  # Keep original context
            }
            
            task = {
                "id": task_id,
                "recipe": recipe,
                "context": execution_context,
                "urgency": urgency,
                "queued_time": datetime.now(),
                "request_id": request.request_id if request else None
            }
            
            # Store request mapping
            if request:
                self._request_map[task_id] = request.request_id
                request.task_id = task_id
            
            # Execute steps immediately for now (we can make this async later)
            execution_result = {"status": "success", "details": []}
            for step in recipe["steps"]:
                step_result = await self._execute_step(step, execution_context)
                if step_result["status"] == "error":
                    return {
                        "status": "error",
                        "error": step_result["error"]
                    }
                execution_result["details"].append(step_result["details"])
            
            return {
                "status": "success",
                "details": " ".join(execution_result["details"]),
                "task_id": task_id
            }
            
        except Exception as e:
            logger.error(f"Error executing recipe: {str(e)}")
            return {
                "status": "error",
                "error": f"Failed to execute recipe: {str(e)}"
            }
    
    async def _process_queue(self):
        """Process tasks from the queue sequentially."""
        while True:
            async with self._task_lock:
                if not self._task_queue:
                    self._processing = False
                    break
                
                # Get highest priority task
                _, _, task = heapq.heappop(self._task_queue)
                self.active_task = task
            
            # Execute the task
            try:
                start_time = datetime.now()
                request_id = task.get("request_id")
                
                # Check for error handling task
                if task["recipe"]["name"] == "Error Handling":
                    execution_result = {
                        "status": "error",
                        "error": "Invalid or unsupported task",
                        "details": task["recipe"]["steps"][0]["message"]
                    }
                else:
                    # Execute steps
                    results = []
                    for step in task["recipe"]["steps"]:
                        step_result = await self._execute_step(step, task["context"])
                        results.append(step_result)
                        
                        if step_result["status"] == "error":
                            raise Exception(f"Step failed: {step_result['error']}")
                    
                    execution_result = {
                        "status": "success",
                        "details": self._format_execution_details(results)
                    }
                
                # Update task history
                history_entry = {
                    "task_id": task["id"],
                    "recipe_name": task["recipe"]["name"],
                    "queued_time": task["queued_time"],
                    "start_time": start_time,
                    "end_time": datetime.now(),
                    "urgency": task["urgency"],
                    "result": execution_result,
                    "request_id": request_id
                }
                
                async with self._task_lock:
                    self.task_history.append(history_entry)
                    if len(self.task_history) > 1000:
                        self.task_history = self.task_history[-500:]
                    
                    # Clean up request mapping
                    if task["id"] in self._request_map:
                        del self._request_map[task["id"]]
                    
                    self.active_task = None
                    
                    # Check if there are more tasks
                    if self._task_queue:
                        continue
                    else:
                        self._processing = False
                        break
                        
            except Exception as e:
                logger.error(f"Task execution failed: {str(e)}")
                execution_result = {
                    "status": "error",
                    "error": str(e),
                    "details": "Task execution failed"
                }
            
            # Update task history
            async with self._task_lock:
                self.task_history.append({
                    "task_id": task["id"],
                    "recipe_name": task["recipe"]["name"],
                    "queued_time": task["queued_time"],
                    "start_time": start_time,
                    "end_time": datetime.now(),
                    "urgency": task["urgency"],
                    "result": execution_result
                })
                
                # Keep history manageable
                if len(self.task_history) > 1000:
                    self.task_history = self.task_history[-500:]
                
                self.active_task = None
                
                # Check if there are more tasks to process
                if self._task_queue:
                    # Continue processing without breaking the loop
                    continue
                else:
                    self._processing = False
                    break
    
    async def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step in a recipe."""
        try:
            step_type = step["type"]
            
            if step_type == "api_call":
                return await self._handle_api_call(step, context)
            elif step_type == "database_query":
                return await self._handle_database_query(step, context)
            elif step_type == "notification":
                return await self._handle_notification(step, context)
            else:
                return {
                    "status": "error",
                    "error": f"Unknown step type: {step_type}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Step execution failed: {str(e)}"
            }
    
    async def _handle_api_call(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle API call steps."""
        try:
            action = step.get('action')
            params = step.get('params', {})
            
            # Replace any template parameters with context values
            for key, value in params.items():
                if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                    param_name = value[1:-1]  # Remove { }
                    if param_name in context:
                        params[key] = context[param_name]
            
            if action == "check_availability":
                # Simulate checking calendar availability
                return {
                    "status": "success",
                    "details": f"Checked availability for {params.get('time')} with {params.get('participants')}"
                }
            elif action == "create_meeting":
                # Simulate creating a meeting
                return {
                    "status": "success",
                    "details": f"Created meeting for {params.get('time')} with {params.get('participants')}"
                }
            else:
                return {
                    "status": "error",
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": f"API call failed: {str(e)}"
            }
    
    async def _handle_database_query(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle database query steps."""
        # This would integrate with your database
        return {
            "status": "success",
            "details": f"Database query {step.get('query_type', 'unknown')} completed"
        }
    
    async def _handle_notification(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notification steps."""
        # This would integrate with your notification system
        return {
            "status": "success",
            "details": f"Notification sent: {step.get('message', 'unknown')}"
        }
    
    def _format_execution_details(self, results: List[Dict[str, Any]]) -> str:
        """Format the execution results into a user-friendly message."""
        details = []
        for result in results:
            if result["status"] == "success" and "details" in result:
                details.append(result["details"])
        
        if not details:
            return "Task completed successfully."
        
        return " ".join(details)
    
    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently running task."""
        if not self.active_task:
            return None
            
        return {
            "task_id": self.active_task["id"],
            "recipe_name": self.active_task["recipe"]["name"],
            "queued_time": self.active_task["queued_time"],
            "urgency": self.active_task["urgency"]
        }
    
    def get_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of completed tasks."""
        return self.task_history[-limit:] 