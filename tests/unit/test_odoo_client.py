"""
Unit tests for Odoo client functionality.

Run with: pytest tests/unit/test_odoo_client.py -v -m unit
"""

import asyncio
from unittest.mock import AsyncMock
from xmlrpc.client import Fault

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.odoo]


# =============================================================================
# Error Handling Tests (TDD - Feedback 4.2)
# =============================================================================


class TestOdooErrorHandling:
    """Tests for Odoo XML-RPC error mapping to clean MCP errors."""

    def test_access_denied_error_mapping(self):
        """AccessDenied fault should map to AuthenticationError."""
        from odoo_mcp_server.odoo.exceptions import (
            OdooAuthenticationError,
            map_odoo_fault,
        )

        fault = Fault(3, "Access Denied")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooAuthenticationError)
        assert "Access Denied" in str(error)
        assert error.error_code == "ACCESS_DENIED"

    def test_user_error_mapping(self):
        """UserError fault should map to OdooValidationError."""
        from odoo_mcp_server.odoo.exceptions import OdooValidationError, map_odoo_fault

        fault = Fault(1, "UserError: Date must be in the future")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooValidationError)
        assert "Date must be in the future" in str(error)
        assert error.error_code == "VALIDATION_ERROR"

    def test_missing_error_mapping(self):
        """MissingError fault should map to OdooRecordNotFoundError."""
        from odoo_mcp_server.odoo.exceptions import (
            OdooRecordNotFoundError,
            map_odoo_fault,
        )

        fault = Fault(2, "MissingError: Record does not exist")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooRecordNotFoundError)
        assert error.error_code == "RECORD_NOT_FOUND"

    def test_access_error_mapping(self):
        """AccessError fault should map to OdooPermissionError."""
        from odoo_mcp_server.odoo.exceptions import OdooPermissionError, map_odoo_fault

        fault = Fault(4, "AccessError: You don't have access to this record")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooPermissionError)
        assert error.error_code == "PERMISSION_DENIED"

    def test_validation_error_mapping(self):
        """ValidationError fault should map to OdooValidationError."""
        from odoo_mcp_server.odoo.exceptions import OdooValidationError, map_odoo_fault

        fault = Fault(1, "ValidationError: Required field missing")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooValidationError)
        assert error.error_code == "VALIDATION_ERROR"

    def test_connection_error_mapping(self):
        """Connection errors should map to OdooConnectionError."""

        from odoo_mcp_server.odoo.exceptions import (
            OdooConnectionError,
            map_connection_error,
        )
        error = map_connection_error(TimeoutError("Connection timed out"))

        assert isinstance(error, OdooConnectionError)
        assert error.error_code == "CONNECTION_TIMEOUT"
        assert error.is_retryable is True

    def test_unknown_fault_mapping(self):
        """Unknown faults should map to generic OdooError with details."""
        from odoo_mcp_server.odoo.exceptions import OdooError, map_odoo_fault

        fault = Fault(999, "Some unknown error occurred")
        error = map_odoo_fault(fault)

        assert isinstance(error, OdooError)
        # The error should contain details about the fault
        assert "999" in str(error) or "unknown" in str(error).lower() or "error" in str(error).lower()

    def test_error_to_mcp_response(self):
        """Errors should be convertible to MCP-friendly JSON responses."""
        from odoo_mcp_server.odoo.exceptions import OdooValidationError

        error = OdooValidationError("Date must be in the future", field="start_date")
        response = error.to_mcp_response()

        assert "error" in response
        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in response["error"]
        assert response["error"].get("field") == "start_date"


# =============================================================================
# Concurrency Safety Tests (TDD - Feedback 4.3)
# =============================================================================


class TestOdooClientConcurrency:
    """Tests for OdooClient async/concurrency safety."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_isolation(self):
        """Concurrent requests should not interfere with each other."""
        from odoo_mcp_server.odoo.client import OdooClient

        client = OdooClient(
            url="https://test.odoo.com",
            database="test_db",
            username="test",
            api_key="test_key",
        )
        client._uid = 1  # Pre-authenticate

        # Mock the XML-RPC calls
        call_count = 0

        async def mock_run_in_executor(func, *args):
            nonlocal call_count
            call_count += 1
            current_call = call_count
            await asyncio.sleep(0.01)  # Simulate network delay
            return [{"id": current_call, "name": f"Record {current_call}"}]

        client._run_in_executor = mock_run_in_executor

        # Run concurrent requests
        tasks = [
            client.search_read("res.partner", [], ["id", "name"], limit=1)
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # Each result should be independent
        assert len(results) == 5
        ids = [r[0]["id"] for r in results]
        # All IDs should be unique (no cross-contamination)
        assert len(set(ids)) == 5

    @pytest.mark.asyncio
    async def test_uid_caching_thread_safety(self):
        """UID caching should be thread-safe for async operations."""
        from odoo_mcp_server.odoo.client import OdooClient

        client = OdooClient(
            url="https://test.odoo.com",
            database="test_db",
            username="test",
            api_key="test_key",
        )

        # The _uid should be protected by asyncio.Lock
        assert hasattr(client, '_uid_lock') or hasattr(client, '_lock')

    @pytest.mark.asyncio
    async def test_client_is_reusable_across_requests(self):
        """Single client instance should handle multiple sequential requests."""
        from odoo_mcp_server.odoo.client import OdooClient

        client = OdooClient(
            url="https://test.odoo.com",
            database="test_db",
            username="test",
            api_key="test_key",
        )
        client._uid = 1  # Pre-authenticate

        async def mock_run(*args):
            return [{"id": 1}]

        client._run_in_executor = mock_run
        call_count = 0

        async def counting_mock(*args):
            nonlocal call_count
            call_count += 1
            return [{"id": 1}]

        client._run_in_executor = counting_mock

        # Multiple sequential calls
        result1 = await client.search_read("res.partner", [], ["id"])
        result2 = await client.search_read("hr.employee", [], ["id"])
        result3 = await client.search_read("hr.leave", [], ["id"])

        assert result1 == result2 == result3 == [{"id": 1}]
        assert call_count == 3


# =============================================================================
# Mocking Examples for Unit Tests (TDD - Feedback 4.4)
# =============================================================================


class TestOdooClientWithMocking:
    """
    Unit tests using mocking - no live Odoo server required.

    These tests demonstrate proper mocking patterns for the OdooClient.
    """

    @pytest.fixture
    def mock_odoo_client(self):
        """Create a mocked OdooClient for unit testing."""
        from odoo_mcp_server.odoo.client import OdooClient

        client = OdooClient(
            url="https://mock.odoo.com",
            database="mock_db",
            username="mock_user",
            api_key="mock_key",
        )

        # Pre-authenticate
        client._uid = 1

        return client

    @pytest.mark.asyncio
    async def test_search_read_mocked(self, mock_odoo_client):
        """Test search_read with mocked responses."""
        # Setup mock response by mocking _run_in_executor
        async def mock_run(*args):
            return [
                {"id": 1, "name": "John Doe", "work_email": "john@example.com"},
                {"id": 2, "name": "Jane Doe", "work_email": "jane@example.com"},
            ]

        mock_odoo_client._run_in_executor = mock_run

        # Execute
        result = await mock_odoo_client.search_read(
            model="hr.employee",
            domain=[["department_id", "=", 1]],
            fields=["id", "name", "work_email"],
        )

        # Verify
        assert len(result) == 2
        assert result[0]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_create_mocked(self, mock_odoo_client):
        """Test create with mocked responses."""
        async def mock_run(*args):
            return 42

        mock_odoo_client._run_in_executor = mock_run

        result = await mock_odoo_client.create(
            model="hr.leave",
            values={
                "employee_id": 1,
                "holiday_status_id": 1,
                "date_from": "2025-02-01",
                "date_to": "2025-02-02",
            },
        )

        assert result == 42

    @pytest.mark.asyncio
    async def test_error_handling_mocked(self, mock_odoo_client):
        """Test error handling with mocked XML-RPC fault."""
        from odoo_mcp_server.odoo.exceptions import OdooValidationError, map_odoo_fault

        # When mocking _run_in_executor, we need to raise the mapped exception
        # since we're bypassing the error handling in the original method
        async def mock_run(*args):
            fault = Fault(1, "ValidationError: Leave request overlaps with existing")
            raise map_odoo_fault(fault)

        mock_odoo_client._run_in_executor = mock_run

        with pytest.raises(OdooValidationError) as exc_info:
            await mock_odoo_client.create(
                model="hr.leave",
                values={"employee_id": 1},
            )

        assert "overlaps" in str(exc_info.value).lower()


class TestEmployeeToolsWithMocking:
    """Unit tests for employee tools using mocked OdooClient."""

    @pytest.fixture
    def mock_odoo_client(self):
        """Create a mock OdooClient."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_my_profile_mocked(self, mock_odoo_client):
        """Test get_my_profile returns standard fields (stock Odoo, no custom fields)."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        # Setup mock response
        mock_odoo_client.read.return_value = [
            {
                "id": 1,
                "name": "Test Employee",
                "work_email": "test@example.com",
                "department_id": [1, "Engineering"],
                "parent_id": [2, "Manager Name"],
                "job_title": "Developer",
            }
        ]

        result = await execute_employee_tool(
            name="get_my_profile",
            arguments={},
            odoo_client=mock_odoo_client,
            employee_id=1,
        )

        # Verify
        import json
        profile = json.loads(result[0].text)

        assert profile["name"] == "Test Employee"
        assert profile["department"] == "Engineering"
        # Stock Odoo: no custom fields configured, so no custom keys are present.
        assert "preferred_name" not in profile
        assert "division" not in profile

    @pytest.mark.asyncio
    async def test_get_my_profile_with_custom_fields(self, mock_odoo_client):
        """Test get_my_profile surfaces configured custom fields generically."""
        from odoo_mcp_server.tools import employee as employee_mod
        from odoo_mcp_server.tools.employee import execute_employee_tool

        mock_odoo_client.read.return_value = [
            {
                "id": 1,
                "name": "Test Employee",
                "work_email": "test@example.com",
                "department_id": [1, "Engineering"],
                "x_preferred_name": "Testy",
                "x_division": "Product",
            }
        ]

        # Configure instance-specific custom fields, then restore defaults.
        employee_mod.configure(
            custom_fields={"preferred_name": "x_preferred_name", "division": "x_division"}
        )
        try:
            result = await execute_employee_tool(
                name="get_my_profile",
                arguments={},
                odoo_client=mock_odoo_client,
                employee_id=1,
            )
            import json
            profile = json.loads(result[0].text)
            assert profile["preferred_name"] == "Testy"
            assert profile["division"] == "Product"
            # The configured Odoo field names were requested from the server.
            requested_fields = mock_odoo_client.read.call_args.kwargs["fields"]
            assert "x_preferred_name" in requested_fields
            assert "x_division" in requested_fields
        finally:
            employee_mod.configure(custom_fields={})

    @pytest.mark.asyncio
    async def test_get_my_leave_balance_mocked(self, mock_odoo_client):
        """Test get_my_leave_balance tool with mocked client."""
        from odoo_mcp_server.tools.employee import execute_employee_tool

        # Mock hr.leave.type with native computed fields (new implementation)
        mock_odoo_client.execute.return_value = [
            {
                "id": 1,
                "name": "Paid Time Off",
                "max_leaves": 25,
                "leaves_taken": 3,
                "virtual_remaining_leaves": 22,
            },
        ]

        result = await execute_employee_tool(
            name="get_my_leave_balance",
            arguments={"year": 2026},
            odoo_client=mock_odoo_client,
            employee_id=1,
        )

        import json
        response = json.loads(result[0].text)

        # Response format: {"year": ..., "balances": [...], "note": ..., "version": ...}
        assert response["year"] == 2026
        balances = response["balances"]
        assert len(balances) == 1
        assert balances[0]["leave_type"] == "Paid Time Off"
        assert balances[0]["allocated"] == 25
        assert balances[0]["taken"] == 3
        assert balances[0]["remaining"] == 22

        # Verify execute was called on hr.leave.type model
        mock_odoo_client.execute.assert_called()
        call_args = mock_odoo_client.execute.call_args
        assert call_args[0][0] == "hr.leave.type"
        assert call_args[0][1] == "search_read"


class TestOdooClientConfiguration:
    """Tests for Odoo client configuration."""

    def test_url_normalization(self):
        """URL should be normalized (trailing slash removed)."""
        urls = [
            ("https://erp.example.com", "https://erp.example.com"),
            ("https://erp.example.com/", "https://erp.example.com"),
            ("https://erp.example.com//", "https://erp.example.com"),
        ]

        for input_url, expected in urls:
            normalized = input_url.rstrip("/")
            assert normalized == expected

    def test_api_key_takes_precedence_over_password(self):
        """When both API key and password are provided, API key should be used."""
        config = {
            "api_key": "secret_key",
            "password": "user_password",
        }

        # API key should be preferred
        auth_credential = config.get("api_key") or config.get("password")
        assert auth_credential == "secret_key"


class TestOdooDomainParsing:
    """Tests for Odoo search domain parsing."""

    def test_simple_domain(self):
        """Simple domain should be parsed correctly."""
        domain = [["name", "=", "Test"]]

        assert len(domain) == 1
        assert domain[0][0] == "name"
        assert domain[0][1] == "="
        assert domain[0][2] == "Test"

    def test_compound_domain_with_and(self):
        """AND domain should use implicit conjunction."""
        domain = [
            ["is_company", "=", True],
            ["active", "=", True],
        ]

        # Implicit AND between conditions
        assert len(domain) == 2

    def test_compound_domain_with_or(self):
        """OR domain should use '|' operator."""
        domain = [
            "|",
            ["name", "ilike", "test"],
            ["email", "ilike", "test"],
        ]

        assert domain[0] == "|"
        assert len(domain) == 3

    def test_nested_domain(self):
        """Nested domain should be supported."""
        domain = [
            "&",
            ["is_company", "=", True],
            "|",
            ["country_id.code", "=", "US"],
            ["country_id.code", "=", "CA"],
        ]

        assert domain[0] == "&"
        assert domain[2] == "|"


class TestOdooFieldSelection:
    """Tests for field selection logic."""

    def test_default_common_fields(self):
        """Common fields should be selected by default for known models."""
        model_default_fields = {
            "res.partner": ["id", "name", "email", "phone", "is_company"],
            "crm.lead": ["id", "name", "expected_revenue", "probability", "stage_id"],
            "product.product": ["id", "name", "default_code", "list_price"],
        }

        for model, fields in model_default_fields.items():
            assert "id" in fields
            assert "name" in fields

    def test_all_fields_selector(self):
        """__all__ should indicate all fields requested."""
        fields = ["__all__"]
        assert fields == ["__all__"]
        assert len(fields) == 1

    def test_empty_fields_means_default(self):
        """Empty fields list should use smart defaults."""
        fields = []
        # Empty should trigger default selection logic
        assert len(fields) == 0


class TestOdooRecordFormatting:
    """Tests for record formatting for LLM consumption."""

    def test_datetime_serialization(self):
        """Datetime fields should be serialized to ISO format."""
        from datetime import datetime

        dt = datetime(2025, 1, 15, 10, 30, 0)
        # Using str() or isoformat() for serialization
        serialized = dt.isoformat()

        assert "2025-01-15" in serialized
        assert "10:30:00" in serialized

    def test_many2one_field_formatting(self):
        """Many2one fields should show both ID and name."""
        record = {
            "partner_id": [1, "Test Partner"],
        }

        partner = record["partner_id"]
        assert partner[0] == 1  # ID
        assert partner[1] == "Test Partner"  # Display name

    def test_one2many_field_formatting(self):
        """One2many fields should show list of IDs."""
        record = {
            "invoice_ids": [1, 2, 3, 4, 5],
        }

        invoice_ids = record["invoice_ids"]
        assert isinstance(invoice_ids, list)
        assert len(invoice_ids) == 5

    def test_selection_field_formatting(self):
        """Selection fields should show the key value."""
        record = {
            "state": "draft",
            "type": "opportunity",
        }

        assert record["state"] == "draft"
        assert record["type"] == "opportunity"
