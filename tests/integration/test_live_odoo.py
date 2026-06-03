"""
Live Odoo Integration Tests

These tests run against the real Odoo instance to verify the implementation.
Requires .env file with valid credentials.

Run with: pytest tests/integration/test_live_odoo.py -v
"""

import json
import os

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]


@pytest.fixture
async def odoo_client():
    """Create a real Odoo client for testing."""
    from odoo_mcp_server.odoo.client import OdooClient

    url = os.environ.get("ODOO_URL")
    db = os.environ.get("ODOO_DB")

    if not url or not db:
        pytest.fail("ODOO_URL and ODOO_DB must be set")
    api_key = os.getenv("ODOO_API_KEY")
    username = os.getenv("ODOO_USERNAME")

    if not api_key:
        pytest.fail("ODOO_API_KEY not configured")

    client = OdooClient(
        url=url,
        database=db,
        username=username,
        api_key=api_key,
    )

    await client.authenticate()
    return client


@pytest.fixture
async def test_employee_id(odoo_client):
    """Get a test employee ID."""
    employees = await odoo_client.search_read(
        model="hr.employee",
        domain=[["work_email", "!=", False]],
        fields=["id", "name"],
        limit=1,
    )
    if not employees:
        pytest.skip("No employees found in Odoo")
    return employees[0]["id"]


class TestOdooConnection:
    """Test basic Odoo connectivity."""

    async def test_get_version(self, odoo_client):
        """Should return Odoo version."""
        version = await odoo_client.get_version()
        assert "server_version" in version
        assert version["server_version"].startswith("18.")

    async def test_authenticate(self, odoo_client):
        """Should authenticate successfully."""
        assert odoo_client._uid is not None
        assert odoo_client._uid > 0


class TestEmployeeProfileTools:
    """Test employee profile tools against real Odoo."""

    async def test_get_my_profile(self, odoo_client, test_employee_id):
        """get_my_profile should return employee profile."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_profile",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        profile = json.loads(result[0].text)

        assert "name" in profile
        assert "work_email" in profile
        assert "department" in profile
        assert "division" in profile  # Custom field

    async def test_get_my_manager(self, odoo_client, test_employee_id):
        """get_my_manager should return manager info."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_manager",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        manager = json.loads(result[0].text)

        # Manager might be null for some employees
        if manager.get("name"):
            assert "email" in manager


class TestEmployeeDirectoryTools:
    """Test employee directory tools against real Odoo."""

    async def test_find_colleague_by_name(self, odoo_client, test_employee_id):
        """find_colleague should search employees."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        # First get the test employee's name to use as a search term
        profile_result = await execute_employee_tool(
            name="get_my_profile",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )
        profile = json.loads(profile_result[0].text)
        # Use the first name (first word) as search term
        search_name = profile["name"].split()[0]

        result = await execute_employee_tool(
            name="find_colleague",
            arguments={"name": search_name},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        colleagues = json.loads(result[0].text)

        assert isinstance(colleagues, list)
        assert len(colleagues) > 0
        assert any(search_name in c.get("name", "") for c in colleagues)


class TestLeaveTools:
    """Test leave management tools against real Odoo."""

    async def test_get_leave_balance(self, odoo_client, test_employee_id):
        """get_my_leave_balance should return leave allocations."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_leave_balance",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        response = json.loads(result[0].text)

        # Response is a dict with a "balances" key containing the list
        assert isinstance(response, dict)
        assert "balances" in response
        assert isinstance(response["balances"], list)

    async def test_get_leave_requests(self, odoo_client, test_employee_id):
        """get_my_leave_requests should return leave requests."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_leave_requests",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        requests = json.loads(result[0].text)

        assert isinstance(requests, list)


class TestDocumentTools:
    """Test DMS document tools against real Odoo."""

    async def test_get_document_categories(self, odoo_client, test_employee_id):
        """get_document_categories should return accessible folders."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_document_categories",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        response = json.loads(result[0].text)

        # Should return categories or a message
        assert "categories" in response or "message" in response

        # If categories exist, restricted folders should NOT be present
        if response.get("categories"):
            for cat in response["categories"]:
                assert cat["name"] not in ["Background Checks", "Offboarding Documents"]

    async def test_get_my_documents(self, odoo_client, test_employee_id):
        """get_my_documents should return documents or message."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_documents",
            arguments={},
            odoo_client=odoo_client,
            employee_id=test_employee_id,
        )

        response = json.loads(result[0].text)

        # Should return documents list or a message
        assert "documents" in response or "message" in response


class TestErrorHandling:
    """Test error handling against real Odoo."""

    async def test_invalid_employee_id(self, odoo_client):
        """Should handle invalid employee ID gracefully."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        result = await execute_employee_tool(
            name="get_my_profile",
            arguments={},
            odoo_client=odoo_client,
            employee_id=999999,  # Non-existent
        )

        response = json.loads(result[0].text)

        # Should return error or empty result, not crash
        assert "error" in response or response == {}
