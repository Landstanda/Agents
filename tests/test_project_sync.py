#!/usr/bin/env python3

from src.modules.project_sync import ProjectSyncModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

def test_project_sync():
    """Test project sync functionality"""
    try:
        logger.info("Initializing Project Sync Module...")
        sync_module = ProjectSyncModule()
        
        # Example business context
        context = """
        We are creating a business automation system with the following components:
        1. Slack bot for team communication
        2. Trello integration for task management
        3. Google Workspace integration for document handling
        4. Email automation for customer communication
        
        Current priorities:
        - Set up core infrastructure
        - Implement basic communication features
        - Create document management system
        - Develop task tracking workflow
        """
        
        # Set up project board
        logger.info("\nSetting up project board...")
        board_result = sync_module.execute({
            'operation': 'setup_project_board',
            'project_name': 'Business Automation Project',
            'context': context
        })
        
        if board_result and 'board_id' in board_result:
            board_id = board_result['board_id']
            logger.info("✓ Project board created successfully!")
            
            # Create additional task list
            logger.info("\nGenerating development tasks...")
            task_result = sync_module.execute({
                'operation': 'create_task_list',
                'board_id': board_id,
                'list_name': 'Development Tasks',
                'context': """
                Focus on implementing these features:
                1. Email monitoring and routing system
                2. Document creation and sharing automation
                3. Task notification system
                4. Integration testing framework
                """
            })
            
            if task_result and 'list_id' in task_result:
                logger.info("✓ Development tasks created successfully!")
                logger.info("\n✨ Project sync test completed successfully!")
                logger.info("You can now view your project board in Trello")
            else:
                logger.error("Failed to create task list")
        else:
            logger.error("Failed to create project board")
            
    except Exception as e:
        logger.error(f"Project sync test error: {str(e)}")
        
if __name__ == "__main__":
    test_project_sync() 