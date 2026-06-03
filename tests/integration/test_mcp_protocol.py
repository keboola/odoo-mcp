"""
MCP Protocol Compliance Tests

Verifies the MCP server correctly implements the Model Context Protocol
specification for tools, resources, and communication patterns.

Run with: pytest tests/integration/test_mcp_protocol.py -v -m integration
"""

import pytest

pytestmark = [pytest.mark.integration]


class TestMCPInitialization:
    """Tests for MCP server initialization."""

    async def test_server_responds_to_initialize(self, mcp_client):
        """
        GIVEN: MCP server is running
        WHEN: Client sends initialize request
        THEN: Server returns capabilities and protocol version
        """
        result = await mcp_client.initialize()

        assert result.protocolVersion is not None
        assert result.capabilities is not None
        assert result.serverInfo.name == "odoo-mcp-server"

    async def test_server_declares_tools_capability(self, mcp_client):
        """
        GIVEN: MCP server is initialized
        WHEN: Checking server capabilities
        THEN: Tools capability is declared
        """
        result = await mcp_client.initialize()

        assert result.capabilities.tools is not None

    async def test_server_declares_resources_capability(self, mcp_client):
        """
        GIVEN: MCP server is initialized
        WHEN: Checking server capabilities
        THEN: Resources capability is declared
        """
        result = await mcp_client.initialize()

        assert result.capabilities.resources is not None


class TestMCPTools:
    """Tests for MCP tools functionality."""

    async def test_list_tools_returns_odoo_tools(self, mcp_client):
        """
        GIVEN: MCP server is initialized
        WHEN: Client requests tools list
        THEN: Odoo-specific tools are returned
        """
        await mcp_client.initialize()
        tools = await mcp_client.list_tools()

        tool_names = [t.name for t in tools.tools]

        # Expected core tools
        assert "search_records" in tool_names
        assert "get_record" in tool_names
        assert "create_record" in tool_names
        assert "update_record" in tool_names
        assert "list_models" in tool_names

    async def test_tool_has_valid_schema(self, mcp_client):
        """
        GIVEN: MCP server provides tools
        WHEN: Examining tool definitions
        THEN: Each tool has valid JSON schema for inputs
        """
        await mcp_client.initialize()
        tools = await mcp_client.list_tools()

        for tool in tools.tools:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None
            assert tool.inputSchema.get("type") == "object"

    async def test_search_records_tool_schema(self, mcp_client):
        """
        GIVEN: search_records tool is available
        WHEN: Examining its schema
        THEN: Required parameters are defined correctly
        """
        await mcp_client.initialize()
        tools = await mcp_client.list_tools()

        search_tool = next(t for t in tools.tools if t.name == "search_records")

        schema = search_tool.inputSchema
        properties = schema.get("properties", {})

        assert "model" in properties
        assert "domain" in properties
        assert "fields" in properties
        assert "limit" in properties


class TestMCPResources:
    """Tests for MCP resources functionality."""

    async def test_list_resources_returns_odoo_resources(self, mcp_client):
        """
        GIVEN: MCP server is initialized
        WHEN: Client requests resources list
        THEN: Odoo resource URIs are returned
        """
        await mcp_client.initialize()
        resources = await mcp_client.list_resources()

        resource_uris = [r.uri for r in resources.resources]

        # Check for expected resource patterns
        assert any("odoo://" in uri for uri in resource_uris)

    async def test_read_models_resource(self, mcp_client):
        """
        GIVEN: Models resource is available
        WHEN: Client reads odoo://models resource
        THEN: List of available Odoo models is returned
        """
        await mcp_client.initialize()

        result = await mcp_client.read_resource("odoo://models")

        assert result.contents is not None
        assert len(result.contents) > 0


class TestMCPErrorHandling:
    """Tests for MCP error handling."""

    async def test_invalid_tool_returns_error(self, mcp_client):
        """
        GIVEN: MCP server is running
        WHEN: Client calls non-existent tool
        THEN: Server returns appropriate error
        """
        await mcp_client.initialize()

        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool("non_existent_tool", arguments={})

        assert "not found" in str(exc_info.value).lower()

    async def test_invalid_tool_arguments_returns_error(self, mcp_client):
        """
        GIVEN: Valid tool exists
        WHEN: Client provides invalid arguments
        THEN: Server returns validation error
        """
        await mcp_client.initialize()

        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool(
                "search_records", arguments={"invalid_param": "value"}
            )

        # Should indicate missing required parameter
        error_msg = str(exc_info.value).lower()
        assert "model" in error_msg or "required" in error_msg
