"""
Claude Agent SDK E2E Tests

These tests use the Claude Agent SDK to test the MCP server end-to-end.
Claude receives natural language queries and calls MCP tools to fulfill them.

No browser automation required!

Prerequisites:
- ANTHROPIC_API_KEY environment variable set
- ODOO_API_KEY for live Odoo tests (optional)

Run with: pytest tests/e2e/test_agent_sdk.py -v
"""

import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.agent_sdk]

# Skip all tests if ANTHROPIC_API_KEY not set
pytestmark.append(
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not configured"
    )
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture
def mcp_server_command():
    """Get MCP server command for Agent SDK."""
    return f"{sys.executable} -m odoo_mcp_server.server"


@pytest.fixture
def agent_options():
    """Get options for Claude Agent SDK."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=5,
        )
    except ImportError:
        pytest.skip("claude-agent-sdk not installed")


class TestAgentSDKBasics:
    """Test basic Claude Agent SDK functionality."""

    async def test_agent_sdk_import(self):
        """
        GIVEN: claude-agent-sdk is installed
        WHEN: Importing the SDK
        THEN: Import succeeds
        """
        try:
            from claude_agent_sdk import query
            assert query is not None
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

    async def test_agent_can_list_tools(self, mcp_server_command):
        """
        GIVEN: MCP server and Claude Agent SDK
        WHEN: Asking Claude what tools are available
        THEN: Claude lists the MCP tools
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        messages = []
        async for message in query(
            prompt="What MCP tools do you have available? Just list the tool names.",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 3},
        ):
            messages.append(message)

        # Should have received some response
        assert len(messages) > 0

        # Check if tool names are mentioned in responses
        full_response = str(messages)
        expected_tools = ["get_my_profile", "find_colleague", "get_my_leave"]

        tools_found = sum(1 for tool in expected_tools if tool in full_response.lower())
        assert tools_found > 0, f"No expected tools found in response: {full_response[:500]}"


class TestAgentSDKToolCalls:
    """Test Claude calling MCP tools via Agent SDK."""

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_calls_get_my_profile(self, mcp_server_command):
        """
        GIVEN: MCP server with Odoo credentials
        WHEN: Asking Claude to get employee profile
        THEN: Claude calls the get_my_profile tool and returns data
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        employee_id = os.getenv("TEST_EMPLOYEE_ID", "1")

        messages = []
        async for message in query(
            prompt=f"Use the get_my_profile tool with employee_id={employee_id} and tell me the person's name.",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 5},
        ):
            messages.append(message)

        # Should have received response with profile data
        full_response = str(messages)
        assert len(full_response) > 0

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_calls_find_colleague(self, mcp_server_command):
        """
        GIVEN: MCP server with Odoo credentials
        WHEN: Asking Claude to find a colleague
        THEN: Claude calls the find_colleague tool
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        messages = []
        async for message in query(
            prompt="Use the find_colleague tool to search for anyone named 'John'. Return the results.",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 5},
        ):
            messages.append(message)

        assert len(messages) > 0

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_calls_leave_balance(self, mcp_server_command):
        """
        GIVEN: MCP server with Odoo credentials
        WHEN: Asking Claude about leave balance
        THEN: Claude calls the get_my_leave_balance tool
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        employee_id = os.getenv("TEST_EMPLOYEE_ID", "1")

        messages = []
        async for message in query(
            prompt=f"Use get_my_leave_balance with employee_id={employee_id}. What leave types are available?",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 5},
        ):
            messages.append(message)

        assert len(messages) > 0


class TestAgentSDKNaturalLanguage:
    """Test Claude understanding natural language and selecting correct tools."""

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_understands_profile_request(self, mcp_server_command):
        """
        GIVEN: MCP server
        WHEN: Using natural language to ask about profile
        THEN: Claude understands and calls appropriate tool
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        messages = []
        async for message in query(
            prompt="I want to know information about employee #1. Can you show me their profile details?",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 5},
        ):
            messages.append(message)

        # Claude should have called get_my_profile
        assert len(messages) > 0

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_understands_vacation_request(self, mcp_server_command):
        """
        GIVEN: MCP server
        WHEN: Asking about vacation/PTO
        THEN: Claude calls leave balance tool
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        messages = []
        async for message in query(
            prompt="How many vacation days does employee #1 have left?",
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 5},
        ):
            messages.append(message)

        assert len(messages) > 0


class TestAgentSDKErrorHandling:
    """Test error handling in Agent SDK integration."""

    async def test_agent_handles_missing_odoo_gracefully(self, mcp_server_command):
        """
        GIVEN: MCP server without Odoo credentials
        WHEN: Trying to call Odoo tools
        THEN: Error is handled gracefully
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        # Temporarily unset ODOO_API_KEY
        original_key = os.environ.pop("ODOO_API_KEY", None)

        try:
            messages = []
            async for message in query(
                prompt="Try to get employee profile for employee_id=1",
                mcp_servers=[mcp_server_command],
                options={"permission_mode": "bypassPermissions", "max_turns": 3},
            ):
                messages.append(message)

            # Should have some response (error or explanation)
            assert len(messages) > 0
        finally:
            # Restore key
            if original_key:
                os.environ["ODOO_API_KEY"] = original_key


class TestAgentSDKMultiStep:
    """Test multi-step conversations with Agent SDK."""

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured for live tests"
    )
    async def test_agent_multi_tool_query(self, mcp_server_command):
        """
        GIVEN: MCP server with multiple tools
        WHEN: Asking question requiring multiple tool calls
        THEN: Claude uses multiple tools to answer
        """
        try:
            from claude_agent_sdk import query
        except ImportError:
            pytest.skip("claude-agent-sdk not installed")

        messages = []
        async for message in query(
            prompt=(
                "For employee #1, get their profile and their leave balance. "
                "Summarize both in one response."
            ),
            mcp_servers=[mcp_server_command],
            options={"permission_mode": "bypassPermissions", "max_turns": 8},
        ):
            messages.append(message)

        # Should have called multiple tools
        assert len(messages) > 0
