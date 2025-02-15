class Agent:
    def __init__(self):
        # ... existing code ...
        self.tools = {}  # Initialize tools dictionary
        logger.debug("Agent initialized")
        
    async def process_ticket(self, ticket: Ticket) -> None:
        """Process a ticket through the execution pipeline."""
        try:
            logger.debug(f"\n{'='*50}")
            logger.debug(f"Processing ticket: {ticket.ticket_id}")
            logger.debug(f"Service: {ticket.service}")
            logger.debug(f"Status: {ticket.status}")
            logger.debug(f"Entities: {ticket.entities}")
            
            # Load and validate tools
            available_tools = set(self.tools.keys())
            logger.debug(f"Available tools: {available_tools}")
            
            # Load service definition
            service_def = self._load_service_definition(ticket.service)
            if not service_def:
                error_msg = f"Failed to load service definition for {ticket.service}"
                logger.error(f"❌ {error_msg}")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(error_msg, "service_loading_error")
                return
                
            # Validate required tools
            required_tools = set()
            for step in service_def.get('steps', []):
                tool = step.get('tool', '').lower()
                if tool:
                    required_tools.add(tool)
            
            logger.debug(f"Required tools for service: {required_tools}")
            missing_tools = required_tools - available_tools
            
            if missing_tools:
                error_msg = f"Missing required tools: {missing_tools}"
                logger.error(f"❌ {error_msg}")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(error_msg, "missing_tools_error")
                return
                
            # Execute service
            logger.debug("Starting service execution")
            result = await self.execute_service(ticket)
            logger.debug(f"Service execution result: {result}")
            
            if result.get('status') == 'error':
                logger.error(f"❌ Service execution failed: {result.get('error')}")
                ticket.update_status(TicketStatus.ERROR)
                ticket.add_error(result.get('error'), "execution_error")
            else:
                logger.debug("✓ Service execution completed successfully")
                ticket.update_status(TicketStatus.COMPLETED)
                
        except Exception as e:
            error_msg = f"Error processing ticket: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            ticket.update_status(TicketStatus.ERROR)
            ticket.add_error(error_msg, "processing_error")
            
    def _load_service_definition(self, service_name: str) -> Optional[Dict]:
        """Load service definition from services.yaml"""
        try:
            logger.debug(f"Loading service definition for: {service_name}")
            services_path = Path("src/services/services.yaml")
            
            if not services_path.exists():
                logger.error(f"❌ Services file not found: {services_path}")
                return None
                
            with open(services_path, 'r') as f:
                services = yaml.safe_load(f) or {}
                
            if service_name not in services:
                logger.error(f"❌ Service {service_name} not found in services file")
                return None
                
            logger.debug(f"✓ Service definition loaded successfully")
            return services[service_name]
            
        except Exception as e:
            logger.error(f"❌ Error loading service definition: {str(e)}", exc_info=True)
            return None

# ... existing code ... 