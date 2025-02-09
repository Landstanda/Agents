#!/usr/bin/env python3

from src.modules.business_context import BusinessContextModule
from src.utils.logging import get_logger
import json
import os

logger = get_logger(__name__)

def test_business_context():
    """Test business context management"""
    try:
        logger.info("=== Testing Business Context Module ===")
        context_module = BusinessContextModule()
        
        # Test importing business context
        business_info = """
        Product Name: Mirror Aphrodite
        Website: mirrorAphrodite.com

        Business Vision:
        Develop a digital magnifying vanity mirror that combines advanced machine learning with elegant design.
        Target upper-class, 30-50-year-old women who value beauty and convenience.

        Product Specifications:
        - Uses facial tracking for zoom control
        - Voice-controlled operation
        - Clear, distortion-free magnification
        - Optimal viewing from arms-length distance

        Technical Components:
        - Raspberry Pi-5
        - 5-inch round display
        - ArduCam 64 MB Hawkeye camera
        - MediaPipe ML algorithms

        Pricing:
        - Manufacturing cost: ~$300
        - Retail price: ~$800

        Target Market:
        - Upper-class women aged 30-50
        - Focus on those with disposable income
        - Interest in premium beauty products
        """
        
        logger.info("\nImporting business context...")
        result = context_module.execute({
            'operation': 'import_context',
            'text': business_info
        })
        
        if result and 'context' in result:
            logger.info("✓ Successfully imported business context")
            
            # Test retrieving context
            logger.info("\nRetrieving business context...")
            get_result = context_module.execute({
                'operation': 'get_context',
                'section': None  # Get all context
            })
            
            if get_result and 'context' in get_result:
                context = get_result['context']
                logger.info("✓ Successfully retrieved context")
                logger.info("\nBusiness Context Summary:")
                logger.info(f"• Business Name: {context.get('business_name', 'N/A')}")
                logger.info(f"• Target Market: {context.get('target_market', 'N/A')}")
                logger.info(f"• Key Features: {', '.join(context.get('key_features', []))}")
                
                # Test updating specific section
                logger.info("\nUpdating business goals...")
                update_result = context_module.execute({
                    'operation': 'update_context',
                    'updates': {
                        'goals': [
                            "Complete prototype and gather customer feedback",
                            "Launch social media campaigns",
                            "Implement manufacturing automation",
                            "Reach 10,000 units sold by year-end"
                        ]
                    }
                })
                
                if update_result and 'context' in update_result:
                    logger.info("✓ Successfully updated business goals")
                    logger.info("\nUpdated Goals:")
                    for goal in update_result['context'].get('goals', []):
                        logger.info(f"• {goal}")
                else:
                    logger.error("Failed to update business goals")
            else:
                logger.error("Failed to retrieve context")
        else:
            logger.error("Failed to import business context")
            
        # Clean up test file
        if os.path.exists('business_context.json'):
            os.remove('business_context.json')
            
    except Exception as e:
        logger.error(f"Business context test error: {str(e)}")
        
if __name__ == "__main__":
    test_business_context() 