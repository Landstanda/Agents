#!/usr/bin/env python3

"""
Chain package for AphroAgent.

This package contains all the chain implementations that can be used by the Brain
to process user requests. Each chain is a specialized workflow that combines
multiple modules to accomplish specific tasks.

Available chains:
- EmailProcessingChain: Process and organize emails
- WebResearchChain: Conduct web research and compile information
- BusinessCommunicationChain: Handle various forms of business communication
- DocumentManagementChain: Manage and organize documents
- ProjectManagementChain: Handle project and task management
"""

from ..modules.base_chain import Chain

__all__ = [
    'email_processing_chain',
    'web_research_chain',
    'business_communication_chain',
    'document_management_chain',
    'project_management_chain'
] 