import asyncio
import os
import sys
from pathlib import Path
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.tools.service_maker import ServiceMaker
from src.tools.nlp import Ticket, TicketStatus

class TestTicket(Ticket):
    """Simple Ticket class for testing"""
    def __init__(self, message: str):
        self.ticket_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.original_message = message
        self.messages = [{"source": "user", "message": message}]
        self.status = TicketStatus.CREATED
        self.service = None
        self.created_services = []
        self.errors = []

    def add_error(self, error: str, error_type: str):
        self.errors.append({"error": error, "type": error_type})

class ServiceMakerTester:
    def __init__(self):
        logger.info("Initializing ServiceMakerTester")
        try:
            # Use src/services/capacity.yaml by default
            capacity_path = Path("src/services/capacity.yaml")
            if not capacity_path.exists():
                logger.warning(f"Capacity file not found at {capacity_path}, trying root directory")
                capacity_path = Path("capacity.yaml")
            
            logger.info(f"Using capacity file: {capacity_path}")
            self.service_maker = ServiceMaker(capacity_path=str(capacity_path))
            self.output_dir = Path("test_output")
            self.output_dir.mkdir(exist_ok=True)
            
            # Verify capacity file was loaded
            if not self.service_maker.capacity:
                raise ValueError("Capacity file not loaded properly")
            logger.info("ServiceMaker initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ServiceMakerTester: {str(e)}")
            raise

    async def test_service_creation(self, request: str) -> None:
        """Test service creation with a given request"""
        print("\n=== Testing Service Creation ===")
        print(f"Request: {request}")
        
        try:
            # Create test ticket
            ticket = TestTicket(request)
            
            # Try to match with existing services first
            print("\n--- Attempting Service Match ---")
            match_prompt = self.service_maker._create_matching_prompt(ticket)
            print("\nMatch Prompt:")
            print(match_prompt)
            
            match_result = await self.service_maker._try_service_match(ticket)
            print("\nMatch Result:")
            print(yaml.dump(match_result, default_flow_style=False))
            
            if not match_result.get("matched"):
                print("\n--- Creating New Service ---")
                creation_prompt = self.service_maker._create_service_prompt(ticket)
                print("\nCreation Prompt:")
                print(creation_prompt)
                
                # Create new service
                ticket = await self.service_maker._create_new_service(ticket)
                
                if ticket.created_services:
                    print("\nCreated Service:")
                    service = ticket.created_services[-1]
                    print(yaml.dump(service, default_flow_style=False))
                    
                    # Validate the service
                    print("\nValidating Service...")
                    if self.service_maker._validate_service(service):
                        print("Service validation successful")
                        self._save_service(service)
                    else:
                        print("Service validation failed")
                else:
                    print("\nNo service created. Errors:")
                    for error in ticket.errors:
                        print(f"- {error['error']} ({error['type']})")
                        
        except Exception as e:
            logger.error(f"Error in test_service_creation: {str(e)}")
            print(f"\nError during testing: {str(e)}")

    def _save_service(self, service: Dict[str, Any]) -> None:
        """Save a successful service to a file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            service_name = service.get("name", "unnamed").lower().replace(" ", "_")
            filename = self.output_dir / f"service_{service_name}_{timestamp}.yaml"
            
            with open(filename, "w") as f:
                yaml.dump(service, f, default_flow_style=False)
            print(f"\nService saved to: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving service: {str(e)}")
            print(f"Error saving service: {str(e)}")

async def main():
    try:
        tester = ServiceMakerTester()
        
        print("=== Service Maker Interactive Tester ===")
        print("Enter requests to test service creation (or 'quit' to exit)")
        print("Example requests:")
        print("1. 'Send an email to john@example.com'")
        print("2. 'Create a calendar event for tomorrow at 2pm'")
        print("3. 'Upload file.txt to Google Drive'\n")
        
        while True:
            try:
                request = input("\nEnter request (or 'quit'): ").strip()
                if request.lower() == 'quit':
                    break
                    
                await tester.test_service_creation(request)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                print(f"\nError: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        print(f"Failed to initialize tester: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 