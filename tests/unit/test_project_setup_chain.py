import pytest
import logging
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Mock implementations
class MockProjectSyncModule:
    async def create_project(self, project_name, description, team_members):
        logging.info(f"Mock: Created project '{project_name}'")
        return {
            "project_id": "mock_proj_123",
            "workspace_url": "https://workspace.com/mock_proj_123"
        }
    
    async def setup_workspace(self, project_id, workspace_config):
        logging.info(f"Mock: Set up workspace for project {project_id}")
        return {"status": "success", "workspace_id": "mock_ws_123"}

class MockBusinessContextModule:
    async def create_context(self, project_id, context_data):
        logging.info(f"Mock: Created business context for project {project_id}")
        return {
            "context_id": "mock_ctx_123",
            "doc_url": "https://docs.google.com/mock_ctx_123"
        }
    
    async def link_resources(self, context_id, resource_links):
        logging.info(f"Mock: Linked resources to context {context_id}")
        return {"status": "success"}

class MockTrelloModule:
    async def create_board(self, name, description, template=None):
        logging.info(f"Mock: Created Trello board '{name}'")
        return {
            "board_id": "mock_board_123",
            "url": "https://trello.com/mock_board_123"
        }
    
    async def create_lists(self, board_id, list_names):
        logging.info(f"Mock: Created lists on board {board_id}")
        return {"status": "success", "list_ids": ["list_1", "list_2", "list_3"]}
    
    async def add_members(self, board_id, member_emails):
        logging.info(f"Mock: Added members to board {board_id}")
        return {"status": "success"}

class MockSlackModule:
    async def create_channel(self, channel_name, is_private=False):
        logging.info(f"Mock: Created Slack channel #{channel_name}")
        return {
            "channel_id": "mock_channel_123",
            "name": channel_name
        }
    
    async def invite_members(self, channel_id, member_emails):
        logging.info(f"Mock: Invited members to channel {channel_id}")
        return {"status": "success"}
    
    async def send_message(self, channel, message):
        logging.info(f"Mock: Sent message to {channel}")
        return {"status": "sent", "timestamp": datetime.now().timestamp()}

# The chain implementation
class ProjectSetupChain:
    def __init__(self):
        self.project_sync = MockProjectSyncModule()
        self.business_context = MockBusinessContextModule()
        self.trello = MockTrelloModule()
        self.slack = MockSlackModule()

    async def execute(self, chain_vars):
        try:
            # Step 1: Create project workspace
            project = await self.project_sync.create_project(
                project_name=chain_vars["project_name"],
                description=chain_vars["description"],
                team_members=chain_vars["team_members"]
            )
            
            # Step 2: Set up workspace with config
            workspace = await self.project_sync.setup_workspace(
                project_id=project["project_id"],
                workspace_config=chain_vars.get("workspace_config", {})
            )
            
            # Step 3: Create business context
            context = await self.business_context.create_context(
                project_id=project["project_id"],
                context_data=chain_vars.get("context_data", {})
            )
            
            # Step 4: Create Trello board
            board = await self.trello.create_board(
                name=chain_vars["project_name"],
                description=chain_vars["description"],
                template=chain_vars.get("trello_template")
            )
            
            # Step 5: Set up Trello lists
            lists = await self.trello.create_lists(
                board_id=board["board_id"],
                list_names=chain_vars.get("list_names", ["To Do", "In Progress", "Done"])
            )
            
            # Step 6: Add team members to Trello
            await self.trello.add_members(
                board_id=board["board_id"],
                member_emails=chain_vars["team_members"]
            )
            
            # Step 7: Create Slack channel
            channel = await self.slack.create_channel(
                channel_name=chain_vars.get("slack_channel", 
                                         f"proj-{chain_vars['project_name'].lower().replace(' ', '-')}")
            )
            
            # Step 8: Invite team to Slack channel
            await self.slack.invite_members(
                channel_id=channel["channel_id"],
                member_emails=chain_vars["team_members"]
            )
            
            # Step 9: Send welcome message
            await self.slack.send_message(
                channel=channel["name"],
                message=f"Welcome to {chain_vars['project_name']}!\n"
                       f"Project Workspace: {project['workspace_url']}\n"
                       f"Trello Board: {board['url']}\n"
                       f"Business Context: {context['doc_url']}"
            )
            
            # Step 10: Link resources in business context
            await self.business_context.link_resources({
                "workspace": project["workspace_url"],
                "trello": board["url"],
                "slack": f"#{channel['name']}"
            })
            
            return {
                "status": "success",
                "project_id": project["project_id"],
                "workspace_url": project["workspace_url"],
                "trello_url": board["url"],
                "slack_channel": channel["name"],
                "context_url": context["doc_url"]
            }
            
        except Exception as e:
            logging.error(f"Chain execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# Tests
@pytest.mark.asyncio
async def test_basic_project_setup():
    chain = ProjectSetupChain()
    chain_vars = {
        "project_name": "New Product Launch",
        "description": "Q1 2024 product launch project",
        "team_members": ["pm@company.com", "dev@company.com", "design@company.com"]
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert all(key in result for key in ["project_id", "workspace_url", "trello_url", "slack_channel"])

@pytest.mark.asyncio
async def test_project_setup_with_custom_config():
    chain = ProjectSetupChain()
    chain_vars = {
        "project_name": "Client Website Redesign",
        "description": "Website redesign for Client X",
        "team_members": ["pm@company.com", "dev@company.com"],
        "workspace_config": {
            "template": "website_project",
            "features": ["git", "ci_cd", "staging"]
        },
        "trello_template": "website_template",
        "list_names": ["Backlog", "Design", "Development", "QA", "Done"],
        "slack_channel": "client-x-website",
        "context_data": {
            "client_name": "Client X",
            "timeline": "Q1 2024",
            "budget": "$50,000"
        }
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "success"
    assert result["slack_channel"] == "client-x-website"

@pytest.mark.asyncio
async def test_error_handling():
    chain = ProjectSetupChain()
    # Test with missing required fields
    chain_vars = {
        "project_name": "Test Project"
        # Missing description and team_members
    }
    
    result = await chain.execute(chain_vars)
    assert result["status"] == "error"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__]) 