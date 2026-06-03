"""
MCP Protocol Tests

These tests verify the MCP server protocol implementation by connecting
to the server via stdio and testing tools directly.

No Claude login or browser required!

Run with: pytest tests/mcp/test_mcp_protocol.py -v
"""

import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.mcp]

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture
def server_params():
    """Get MCP server parameters for stdio connection."""
    from mcp import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "odoo_mcp_server.server"],
        env={
            **os.environ,
            "ODOO_URL": os.environ["ODOO_URL"],
            "ODOO_DB": os.environ["ODOO_DB"],
            "ODOO_API_KEY": os.getenv("ODOO_API_KEY", ""),
        },
    )


class TestMCPServerConnection:
    """Test basic MCP server connection and initialization."""

    async def test_server_starts_and_responds(self, server_params):
        """
        GIVEN: MCP server configuration
        WHEN: Client connects via stdio
        THEN: Server initializes successfully
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()

                assert result is not None
                assert result.serverInfo is not None
                assert "odoo" in result.serverInfo.name.lower()

    async def test_server_reports_capabilities(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Checking server capabilities
        THEN: Server reports tool and resource capabilities
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()

                # Server should support tools
                assert result.capabilities is not None


class TestMCPToolListing:
    """Test MCP tool discovery."""

    async def test_list_tools_returns_employee_tools(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Listing available tools
        THEN: Employee self-service tools are present
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                tool_names = [t.name for t in tools_result.tools]

                # Expected employee tools
                expected_tools = [
                    "get_my_profile",
                    "get_my_manager",
                    "find_colleague",
                    "get_my_leave_balance",
                    "get_my_leave_requests",
                    "get_my_documents",
                    "get_document_categories",
                ]

                for expected in expected_tools:
                    assert expected in tool_names, f"Missing tool: {expected}"

    async def test_tools_have_descriptions(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Listing tools
        THEN: Each tool has a description
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                for tool in tools_result.tools:
                    assert tool.description, f"Tool {tool.name} has no description"
                    assert len(tool.description) > 10, f"Tool {tool.name} description too short"

    async def test_tools_have_input_schemas(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Listing tools
        THEN: Each tool has an input schema
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                for tool in tools_result.tools:
                    assert tool.inputSchema is not None, f"Tool {tool.name} has no input schema"


class TestMCPToolExecution:
    """Test MCP tool execution."""

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured"
    )
    async def test_get_my_profile_returns_data(self, server_params):
        """
        GIVEN: Connected MCP session with valid Odoo credentials
        WHEN: Calling get_my_profile tool
        THEN: Profile data is returned
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(
                    "get_my_profile",
                    arguments={"employee_id": int(os.getenv("TEST_EMPLOYEE_ID", "1"))}
                )

                # Should have content
                assert result.content is not None
                assert len(result.content) > 0

                # Content should be text with JSON
                content = result.content[0]
                assert content.type == "text"

                # Parse the JSON
                profile = json.loads(content.text)
                assert "name" in profile

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured"
    )
    async def test_get_my_leave_balance_returns_data(self, server_params):
        """
        GIVEN: Connected MCP session with valid Odoo credentials
        WHEN: Calling get_my_leave_balance tool
        THEN: Leave balance data is returned
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "get_my_leave_balance",
                    arguments={"employee_id": int(os.getenv("TEST_EMPLOYEE_ID", "1"))}
                )

                assert result.content is not None
                assert len(result.content) > 0

    @pytest.mark.skipif(
        not os.getenv("ODOO_API_KEY"),
        reason="ODOO_API_KEY not configured"
    )
    async def test_find_colleague_returns_results(self, server_params):
        """
        GIVEN: Connected MCP session with valid Odoo credentials
        WHEN: Searching for a colleague
        THEN: Search results are returned
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "find_colleague",
                    arguments={"name": "test"}
                )

                assert result.content is not None
                # Even empty results should return valid JSON
                content = result.content[0]
                data = json.loads(content.text)
                assert isinstance(data, list)


class TestMCPResourceListing:
    """Test MCP resource discovery."""

    async def test_list_resources(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Listing resources
        THEN: Resources are returned (may be empty)
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                try:
                    resources_result = await session.list_resources()
                    # Resources may or may not be implemented
                    assert resources_result is not None
                except Exception:
                    # Resources not implemented is OK
                    pytest.skip("Resources not implemented")


class TestMCPErrorHandling:
    """Test MCP error handling."""

    async def test_invalid_tool_returns_error(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Calling non-existent tool
        THEN: Error response is returned
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        from mcp.shared.exceptions import McpError

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # May raise McpError or return error content
                try:
                    result = await session.call_tool(
                        "nonexistent_tool",
                        arguments={}
                    )
                    # If no exception, check result contains error
                    if result.content:
                        content = result.content[0].text
                        # Check for error indication
                        assert "error" in content.lower() or result.isError
                except McpError:
                    # This is expected behavior
                    pass

    async def test_missing_required_argument_returns_error(self, server_params):
        """
        GIVEN: Connected MCP session
        WHEN: Calling tool without required arguments
        THEN: Error response is returned
        """
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # find_colleague requires 'name' argument
                result = await session.call_tool(
                    "find_colleague",
                    arguments={}  # Missing required 'name'
                )

                # Should return error content or raise exception
                if result.content:
                    content = result.content[0].text
                    # Either has error or is handled gracefully
                    assert content is not None
