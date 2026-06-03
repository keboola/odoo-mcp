"""
Odoo Integration Tests

Tests the MCP server's integration with Odoo ERP, including
record operations, permissions, and data handling.

Run with: pytest tests/integration/test_odoo_integration.py -v -m odoo
"""

import json

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.odoo]


class TestOdooConnection:
    """Tests for Odoo connection handling."""

    async def test_connection_to_odoo_instance(self, odoo_client):
        """
        GIVEN: Valid Odoo credentials
        WHEN: Client attempts to connect
        THEN: Connection is established successfully
        """
        version = await odoo_client.get_version()

        assert version is not None
        assert "18" in version.get("server_version", "")

    async def test_authentication_with_api_key(self, odoo_client):
        """
        GIVEN: Valid API key
        WHEN: Client authenticates
        THEN: User ID is returned
        """
        uid = await odoo_client.authenticate()

        assert uid is not None
        assert isinstance(uid, int)
        assert uid > 0


class TestOdooRecordOperations:
    """Tests for CRUD operations on Odoo records."""

    async def test_search_partners(self, authenticated_mcp_client):
        """
        GIVEN: Authenticated MCP client
        WHEN: Searching for partners
        THEN: Partner records are returned
        """
        result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "res.partner",
                "domain": [["is_company", "=", True]],
                "fields": ["name", "email", "phone"],
                "limit": 10,
            },
        )

        assert result.content is not None
        records = json.loads(result.content[0].text)
        assert isinstance(records, list)

    async def test_get_single_record(self, authenticated_mcp_client):
        """
        GIVEN: Known record ID
        WHEN: Requesting single record
        THEN: Complete record data is returned
        """
        result = await authenticated_mcp_client.call_tool(
            "get_record",
            arguments={
                "model": "res.partner",
                "record_id": 1,
                "fields": ["name", "email", "phone", "street"],
            },
        )

        assert result.content is not None
        record = json.loads(result.content[0].text)
        assert "name" in record

    async def test_create_and_delete_record(self, authenticated_mcp_client):
        """
        GIVEN: Authenticated client with write permissions
        WHEN: Creating and then deleting a record
        THEN: Operations complete successfully
        """
        # Create
        create_result = await authenticated_mcp_client.call_tool(
            "create_record",
            arguments={
                "model": "res.partner",
                "values": {
                    "name": "MCP Test Partner",
                    "email": "mcp_test@example.com",
                    "is_company": False,
                },
            },
        )

        created = json.loads(create_result.content[0].text)
        record_id = created["id"]
        assert record_id > 0

        # Delete (cleanup)
        delete_result = await authenticated_mcp_client.call_tool(
            "delete_record",
            arguments={"model": "res.partner", "record_id": record_id},
        )

        assert "success" in delete_result.content[0].text.lower()

    async def test_update_record(self, authenticated_mcp_client, test_partner_id: int):
        """
        GIVEN: Existing partner record
        WHEN: Updating record fields
        THEN: Changes are persisted
        """
        # Update
        await authenticated_mcp_client.call_tool(
            "update_record",
            arguments={
                "model": "res.partner",
                "record_id": test_partner_id,
                "values": {"phone": "+1-555-0123"},
            },
        )

        # Verify
        result = await authenticated_mcp_client.call_tool(
            "get_record",
            arguments={
                "model": "res.partner",
                "record_id": test_partner_id,
                "fields": ["phone"],
            },
        )

        record = json.loads(result.content[0].text)
        assert record["phone"] == "+1-555-0123"


class TestOdooPermissions:
    """Tests for Odoo permission handling."""

    async def test_user_can_only_access_permitted_models(
        self, authenticated_mcp_client
    ):
        """
        GIVEN: User with limited permissions
        WHEN: Accessing restricted model
        THEN: Access is denied with clear error
        """
        # Attempt to access a model the test user shouldn't have access to
        with pytest.raises(Exception) as exc_info:
            await authenticated_mcp_client.call_tool(
                "search_records",
                arguments={
                    "model": "ir.config_parameter",  # System model
                    "domain": [],
                    "limit": 1,
                },
            )

        error_msg = str(exc_info.value).lower()
        assert "access" in error_msg or "permission" in error_msg

    async def test_list_models_respects_permissions(self, authenticated_mcp_client):
        """
        GIVEN: Authenticated user
        WHEN: Listing available models
        THEN: Only accessible models are shown
        """
        result = await authenticated_mcp_client.call_tool(
            "list_models", arguments={}
        )

        models = json.loads(result.content[0].text)
        model_names = [m["model"] for m in models]

        # User-facing models should be available
        assert "res.partner" in model_names
        assert "product.product" in model_names


class TestOdooDataFormatting:
    """Tests for data formatting and LLM optimization."""

    async def test_large_result_pagination(self, authenticated_mcp_client):
        """
        GIVEN: Query matching many records
        WHEN: Limit is specified
        THEN: Results are paginated correctly
        """
        result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "res.partner",
                "domain": [],
                "limit": 5,
                "offset": 0,
            },
        )

        records = json.loads(result.content[0].text)
        assert len(records) <= 5

    async def test_count_records(self, authenticated_mcp_client):
        """
        GIVEN: Search domain
        WHEN: Requesting count only
        THEN: Total count is returned without full records
        """
        result = await authenticated_mcp_client.call_tool(
            "count_records",
            arguments={
                "model": "res.partner",
                "domain": [["is_company", "=", True]],
            },
        )

        count_data = json.loads(result.content[0].text)
        assert "count" in count_data
        assert isinstance(count_data["count"], int)
