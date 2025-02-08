import asyncio
import argparse
from typing import Dict, Any
from ..core.decision_engine import DecisionEngine
from ..perspectives.practical_manager import PracticalManagerPerspective
from ..chains.web_analysis_chain import WebAnalysisChain
from ..utils.logging import get_logger

logger = get_logger(__name__)

class CLI:
    """Command Line Interface for the Agent system"""
    
    def __init__(self):
        self.engine = DecisionEngine()
        self.engine.add_perspective(PracticalManagerPerspective())
        
        # Register available chains
        self.web_chain = WebAnalysisChain()
        self.available_chains = [self.web_chain]
    
    async def run(self):
        """Run the CLI interface"""
        parser = argparse.ArgumentParser(description='AI Agent System')
        parser.add_argument('--task', type=str, help='Task description in natural language')
        parser.add_argument('--context', type=str, help='Additional context for the task')
        
        while True:
            try:
                print("\nAI Agent System")
                print("1. Execute task")
                print("2. List available chains")
                print("3. Show system status")
                print("4. Exit")
                
                choice = input("\nEnter your choice (1-4): ")
                
                if choice == '1':
                    await self._handle_task_execution()
                elif choice == '2':
                    self._list_chains()
                elif choice == '3':
                    self._show_status()
                elif choice == '4':
                    print("Goodbye!")
                    break
                else:
                    print("Invalid choice. Please try again.")
            
            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
            except Exception as e:
                logger.error(f"Error in CLI: {str(e)}")
                print(f"An error occurred: {str(e)}")
    
    async def _handle_task_execution(self):
        """Handle task execution flow"""
        task = input("\nEnter task description: ")
        if not task:
            print("Task description cannot be empty")
            return
        
        print("\nGathering context...")
        context = self._gather_context()
        
        print("\nAnalyzing task...")
        chain = self.engine.plan_execution(task)
        
        if not chain:
            print("No suitable execution plan found")
            return
        
        print(f"\nSelected chain: {chain.__class__.__name__}")
        proceed = input("Proceed with execution? (y/n): ")
        
        if proceed.lower() == 'y':
            try:
                result = await self._execute_chain(chain, context)
                print("\nExecution completed!")
                print("Result:", result)
            except Exception as e:
                print(f"Execution failed: {str(e)}")
    
    def _gather_context(self) -> Dict[str, Any]:
        """Gather context information for task execution"""
        context = {
            'available_chains': self.available_chains,
            'resources': {
                'memory': 1000,  # MB
                'api_calls': 100,
                'storage': 5000,  # MB
            },
            'time_constraints': {
                'deadline': 3600,  # seconds
            }
        }
        return context
    
    async def _execute_chain(self, chain, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a function chain"""
        if isinstance(chain, WebAnalysisChain):
            # Extract URL from task description
            task = context.get('task', '').lower()
            urls = []
            import re
            url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
            found_urls = re.findall(url_pattern, task)
            if found_urls:
                urls = found_urls
            else:
                print("No valid URLs found in task description")
                return None

            result = await chain.analyze_websites(
                urls=urls,
                output_path='output/analysis.json'
            )
            
            # Pretty print the results
            if result:
                print("\nResults:")
                for url, data in result.items():
                    print(f"\nFrom {url}:")
                    if 'error' in data:
                        print(f"Error: {data['error']}")
                    elif 'headlines' in data:
                        print("Headlines:")
                        for i, headline in enumerate(data['headlines'], 1):
                            print(f"{i}. {headline}")
                    else:
                        print("No headlines found")
            
            return result
            
        raise ValueError(f"Unsupported chain type: {type(chain)}")
    
    def _list_chains(self):
        """List available function chains"""
        print("\nAvailable Function Chains:")
        for chain in self.available_chains:
            print(f"- {chain.__class__.__name__}")
            if hasattr(chain, 'modules'):
                print("  Modules:")
                for module in chain.modules:
                    print(f"  - {module.__class__.__name__}")
                    print(f"    Capabilities: {', '.join(module.capabilities)}")
    
    def _show_status(self):
        """Show system status"""
        print("\nSystem Status:")
        print(f"Active perspectives: {len(self.engine.perspectives)}")
        print(f"Available chains: {len(self.available_chains)}")
        # Add more status information as needed

def main():
    """Entry point for the CLI"""
    cli = CLI()
    asyncio.run(cli.run())

if __name__ == '__main__':
    main() 