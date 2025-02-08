from typing import Dict, Any, List
from ..core.decision_engine import Perspective
from ..utils.logging import get_logger

logger = get_logger(__name__)

class PracticalManagerPerspective(Perspective):
    """
    A practical management perspective that evaluates tasks based on:
    - Time efficiency
    - Resource usage
    - Success probability
    - Cost-benefit ratio
    """
    
    def evaluate(self, task: str, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Evaluate task options from a practical management perspective
        
        Args:
            task: The task description
            context: Additional context including:
                - available_chains: List of available function chains
                - resources: Dict of available resources
                - time_constraints: Dict of time-related constraints
                - previous_results: Dict of previous execution results
        
        Returns:
            Dict mapping chain IDs to their scores (0-1)
        """
        scores = {}
        available_chains = context.get('available_chains', [])
        
        for chain in available_chains:
            # Start with base score
            score = 1.0
            
            # Evaluate time efficiency
            time_score = self._evaluate_time_efficiency(chain, context)
            score *= time_score
            
            # Evaluate resource usage
            resource_score = self._evaluate_resource_usage(chain, context)
            score *= resource_score
            
            # Evaluate success probability
            success_score = self._evaluate_success_probability(chain, context)
            score *= success_score
            
            # Evaluate cost-benefit
            cost_benefit_score = self._evaluate_cost_benefit(chain, context)
            score *= cost_benefit_score
            
            scores[chain.id] = score
            
            logger.debug(f"Chain {chain.id} scored {score:.2f}")
        
        return scores
    
    def _evaluate_time_efficiency(self, chain, context: Dict) -> float:
        """Evaluate time efficiency of the chain"""
        time_constraints = context.get('time_constraints', {})
        estimated_duration = self._estimate_chain_duration(chain)
        
        if 'deadline' in time_constraints:
            if estimated_duration > time_constraints['deadline']:
                return 0.1  # Severely penalize but don't completely eliminate
            return 1.0 - (estimated_duration / time_constraints['deadline'])
        
        return 0.8  # Default good score if no specific constraints
    
    def _evaluate_resource_usage(self, chain, context: Dict) -> float:
        """Evaluate resource usage efficiency"""
        available_resources = context.get('resources', {})
        required_resources = self._estimate_required_resources(chain)
        
        if not required_resources:
            return 1.0
        
        resource_scores = []
        for resource, required in required_resources.items():
            available = available_resources.get(resource, 0)
            if available < required:
                resource_scores.append(0.2)  # Severe penalty for insufficient resources
            else:
                efficiency = 1.0 - (required / available)
                resource_scores.append(0.5 + (efficiency * 0.5))  # Score between 0.5 and 1.0
        
        return sum(resource_scores) / len(resource_scores) if resource_scores else 0.8
    
    def _evaluate_success_probability(self, chain, context: Dict) -> float:
        """Evaluate likelihood of successful execution"""
        previous_results = context.get('previous_results', {})
        chain_history = previous_results.get(chain.id, [])
        
        if not chain_history:
            return 0.7  # Default score for unknown chains
        
        success_rate = sum(1 for result in chain_history if result.get('success', False)) / len(chain_history)
        return 0.4 + (success_rate * 0.6)  # Score between 0.4 and 1.0
    
    def _evaluate_cost_benefit(self, chain, context: Dict) -> float:
        """Evaluate cost-benefit ratio"""
        estimated_cost = self._estimate_chain_cost(chain)
        estimated_benefit = self._estimate_chain_benefit(chain, context)
        
        if estimated_cost <= 0:
            return 1.0
        
        ratio = estimated_benefit / estimated_cost
        return min(1.0, ratio / 2)  # Normalize to 0-1 range
    
    def _estimate_chain_duration(self, chain) -> float:
        """Estimate time required for chain execution"""
        # Simple estimation based on number of modules
        return len(chain.modules) * 2.0  # 2 minutes per module as baseline
    
    def _estimate_required_resources(self, chain) -> Dict[str, float]:
        """Estimate required resources for chain execution"""
        resources = {}
        for module in chain.modules:
            if hasattr(module, 'resource_requirements'):
                for resource, amount in module.resource_requirements.items():
                    resources[resource] = resources.get(resource, 0) + amount
        return resources
    
    def _estimate_chain_cost(self, chain) -> float:
        """Estimate monetary cost of chain execution"""
        # Simple estimation based on module types
        base_cost = len(chain.modules) * 0.01  # Base cost per module
        return base_cost
    
    def _estimate_chain_benefit(self, chain, context: Dict) -> float:
        """Estimate potential benefit of chain execution"""
        # Simple estimation based on chain capabilities matching task requirements
        task_keywords = set(context.get('task', '').lower().split())
        chain_capabilities = set()
        for module in chain.modules:
            chain_capabilities.update(module.capabilities)
        
        matching_keywords = len(task_keywords.intersection(chain_capabilities))
        return matching_keywords * 0.5  # 0.5 benefit points per matching capability 