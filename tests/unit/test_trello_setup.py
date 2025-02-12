#!/usr/bin/env python3

from src.modules.trello_integration import TrelloModule
from src.utils.logging import get_logger

logger = get_logger(__name__)

def test_trello():
    """Test Trello integration setup"""
    try:
        logger.info("Initializing Trello Module...")
        trello_module = TrelloModule()
        
        # Test getting boards
        logger.info("Getting existing boards...")
        result = trello_module.execute({'operation': 'get_boards'})
        
        if result and 'boards' in result:
            logger.info("✓ Successfully connected to Trello!")
            logger.info(f"✓ Found {len(result['boards'])} boards")
            for board in result['boards']:
                logger.info(f"  - {board['name']}")
                
            # Create a test board
            logger.info("\nCreating a test board...")
            board_result = trello_module.execute({
                'operation': 'create_board',
                'name': 'AphroAgent Test Board'
            })
            
            if board_result and 'id' in board_result:
                board_id = board_result['id']
                logger.info("✓ Test board created successfully!")
                
                # Create lists
                lists = ['To Do', 'In Progress', 'Done']
                for list_name in lists:
                    list_result = trello_module.execute({
                        'operation': 'create_list',
                        'board_id': board_id,
                        'name': list_name
                    })
                    if list_result and 'id' in list_result:
                        logger.info(f"✓ Created list: {list_name}")
                
                logger.info("\n✨ Trello integration test completed successfully!")
                logger.info("You can now use the Trello integration in your workflows")
            else:
                logger.error("Failed to create test board")
        else:
            logger.error("Failed to get boards")
            
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        logger.info("Make sure you have set TRELLO_API_KEY and TRELLO_TOKEN in your .env file")
    except Exception as e:
        logger.error(f"Trello test error: {str(e)}")
        
if __name__ == "__main__":
    test_trello() 