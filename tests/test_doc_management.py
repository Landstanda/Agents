#!/usr/bin/env python3

from src.modules.doc_management import DocumentManagementModule
from src.utils.logging import get_logger
import os
import shutil

logger = get_logger(__name__)

def test_doc_management():
    """Test document management functionality"""
    try:
        logger.info("=== Testing Document Management Module ===")
        doc_module = DocumentManagementModule()
        
        # Test saving in different formats
        test_content = {
            "business_name": "Mirror Aphrodite",
            "description": "Smart vanity mirror with AI capabilities",
            "features": [
                "Facial tracking",
                "Voice control",
                "Automatic zoom"
            ]
        }
        
        # Test JSON format
        logger.info("\nTesting JSON format...")
        json_result = doc_module.execute({
            'operation': 'save_document',
            'name': 'test_doc',
            'content': test_content,
            'format': 'json'
        })
        
        if json_result['success']:
            logger.info("✓ Successfully saved JSON document")
            
            # Test loading JSON
            load_result = doc_module.execute({
                'operation': 'load_document',
                'name': 'test_doc',
                'format': 'json'
            })
            
            if load_result['content']['business_name'] == test_content['business_name']:
                logger.info("✓ Successfully loaded JSON document")
            else:
                logger.error("Failed to load JSON document correctly")
        
        # Test YAML format
        logger.info("\nTesting YAML format...")
        yaml_result = doc_module.execute({
            'operation': 'convert_format',
            'name': 'test_doc',
            'from_format': 'json',
            'to_format': 'yaml'
        })
        
        if yaml_result['success']:
            logger.info("✓ Successfully converted to YAML")
            
        # Test versioning
        logger.info("\nTesting version control...")
        version_result = doc_module.execute({
            'operation': 'create_version',
            'name': 'test_doc',
            'format': 'json'
        })
        
        if version_result['success']:
            logger.info(f"✓ Created version {version_result['version']}")
            
            # Test getting versions
            versions_result = doc_module.execute({
                'operation': 'get_versions',
                'name': 'test_doc',
                'format': 'json'
            })
            
            if versions_result['versions']:
                logger.info(f"✓ Found {len(versions_result['versions'])} versions")
                for version in versions_result['versions']:
                    logger.info(f"  • Version {version['version']} - {version['modified']}")
                    
        # Test Markdown format
        logger.info("\nTesting Markdown format...")
        md_content = """# Mirror Aphrodite

## Smart Vanity Mirror

A revolutionary beauty tool combining:
- AI-powered facial tracking
- Voice control
- Automatic zoom functionality

Perfect for detailed makeup application and skincare routines."""

        md_result = doc_module.execute({
            'operation': 'save_document',
            'name': 'product_description',
            'content': md_content,
            'format': 'md'
        })
        
        if md_result['success']:
            logger.info("✓ Successfully saved Markdown document")
            
        # Test listing documents
        logger.info("\nListing all documents...")
        list_result = doc_module.execute({
            'operation': 'list_documents',
            'format': None  # List all formats
        })
        
        if list_result['documents']:
            logger.info("✓ Found documents:")
            for doc in list_result['documents']:
                logger.info(f"  • {doc['name']}.{doc['format']} - Modified: {doc['modified']}")
                
        logger.info("\n✨ Document management tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Document management test error: {str(e)}")
    finally:
        # Clean up test files
        if os.path.exists('business_docs'):
            shutil.rmtree('business_docs')
        
if __name__ == "__main__":
    test_doc_management() 