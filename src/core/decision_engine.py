from typing import List, Dict, Any, Optional
from .function_chain import FunctionChain
from ..utils.logging import get_logger

logger = get_logger(__name__)

class Perspective:
    """Base class for different AI perspectives"""
    def evaluate(self, task: str, context: Dict[str, Any]) -> Dict[str, float]:
        """Evaluate options and return scores"""
        pass

class DecisionEngine:
    """Coordinates different AI perspectives to plan task execution"""
    
    def __init__(self):
        self.perspectives = []
        self.available_chains = []
    
    def add_perspective(self, perspective: Perspective):
        self.perspectives.append(perspective)
    
    def plan_execution(self, task: str) -> Optional[FunctionChain]:
        """Create execution plan based on perspectives' input"""
        context = {
            'task': task,
            'available_chains': self.available_chains
        }
        
        # Get scores from all perspectives
        chain_scores = {}
        for perspective in self.perspectives:
            scores = perspective.evaluate(task, context)
            for chain_id, score in scores.items():
                chain_scores[chain_id] = chain_scores.get(chain_id, 0) + score
        
        # Find the chain with the highest score
        if chain_scores:
            best_chain_id = max(chain_scores, key=chain_scores.get)
            for chain in self.available_chains:
                if getattr(chain, 'id', None) == best_chain_id:
                    logger.info(f"Selected chain {chain.__class__.__name__} with score {chain_scores[best_chain_id]}")
                    return chain
        
        # If we have a web-related task and WebAnalysisChain is available, use it
        if any(keyword in task.lower() for keyword in ['web', 'url', 'website', 'http', 'https']):
            for chain in self.available_chains:
                if chain.__class__.__name__ == 'WebAnalysisChain':
                    logger.info(f"Selected WebAnalysisChain for web-related task")
                    return chain
        
        return None 