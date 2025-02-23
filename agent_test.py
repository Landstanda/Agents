import asyncio
import logging
from src.tools.agent import Agent
from src.utils.flow_logger import FlowLogger

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_agent_loading():
    """Test the Agent's service loading in isolation"""
    try:
        logger.info("\n=== Testing Agent Service Loading ===")
        
        # Initialize FlowLogger
        flow_logger = FlowLogger()
        await flow_logger.setup()
        
        # Create Agent instance
        agent = Agent(flow_logger=flow_logger)
        
        # Initialize agent (this will load services)
        logger.info("Initializing agent...")
        await agent.initialize()
        
        # Check loaded services
        logger.info(f"Loaded services: {list(agent.services.keys())}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_agent_loading()) 