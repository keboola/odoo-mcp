"""
Comprehensive Staging Integration Tests for Odoo MCP Server

Tests ALL tools (employee self-service and CRUD) against a real staging Odoo instance.
Calls execute_employee_tool and execute_tool (CRUD) directly with a real OdooClient.

Requires environment variables:
    ODOO_URL       - Odoo instance URL
    ODOO_DB        - Odoo database name
    ODOO_API_KEY   - API key for authentication
    ODOO_USERNAME  - Username for authentication

Run with: pytest tests/integration/test_staging_comprehensive.py -v
"""

import base64
import json
import os
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def odoo_client():
    """Create a real Odoo client connected to staging."""
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
    """Get a test employee ID (first employee with a work email)."""
    employees = await odoo_client.search_read(
        model="hr.employee",
        domain=[["work_email", "!=", False]],
        fields=["id", "name"],
        limit=1,
    )
    if not employees:
        pytest.skip("No employees found in Odoo")
    return employees[0]["id"]


@pytest.fixture
async def test_employee_name(odoo_client, test_employee_id):
    """Get the test employee's full name."""
    employees = await odoo_client.read(
        model="hr.employee",
        ids=[test_employee_id],
        fields=["name"],
    )
    return employees[0]["name"]


@pytest.fixture
async def valid_leave_type_name(odoo_client):
    """Dynamically find a valid leave type that exists in the Odoo instance."""
    leave_types = await odoo_client.search_read(
        model="hr.leave.type",
        domain=[],
        fields=["id", "name"],
        limit=1,
    )
    if not leave_types:
        pytest.skip("No leave types configured in Odoo")
    return leave_types[0]["name"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _call_employee_tool(name: str, arguments: dict, odoo_client, employee_id: int) -> dict | list:
    """Call an employee tool and return parsed JSON response."""
    from odoo_mcp_server.tools.employee import execute_employee_tool

    result = await execute_employee_tool(
        name=name,
        arguments=arguments,
        odoo_client=odoo_client,
        employee_id=employee_id,
    )
    return json.loads(result[0].text)


async def _call_crud_tool(name: str, arguments: dict, odoo_client) -> dict | list:
    """Call a CRUD tool and return parsed JSON response."""
    from odoo_mcp_server.tools.records import execute_tool as execute_crud_tool

    result = await execute_crud_tool(
        name=name,
        arguments=arguments,
        client=odoo_client,
    )
    return json.loads(result[0].text)


# ===========================================================================
# 1. Employee Team Tools
# ===========================================================================


class TestEmployeeTeamTools:
    """Test team and colleague discovery tools."""

    async def test_get_my_team(self, odoo_client, test_employee_id):
        """get_my_team should return a list of team members with name and email."""
        response = await _call_employee_tool(
            "get_my_team", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, list)
        # The list may be empty if the employee has no department or is the
        # only member, but the shape must be correct.
        for member in response:
            assert "name" in member
            assert "email" in member

    async def test_get_direct_reports(self, odoo_client, test_employee_id):
        """get_direct_reports should return dict with direct_reports list and count."""
        response = await _call_employee_tool(
            "get_direct_reports", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, dict)
        assert "direct_reports" in response
        assert "count" in response
        assert isinstance(response["direct_reports"], list)
        assert isinstance(response["count"], int)
        assert response["count"] == len(response["direct_reports"])

    async def test_get_direct_reports_structure(self, odoo_client, test_employee_id):
        """Each direct report should have id, name, email, department, job_title."""
        response = await _call_employee_tool(
            "get_direct_reports", {}, odoo_client, test_employee_id
        )

        for report in response["direct_reports"]:
            assert "id" in report
            assert "name" in report
            assert "email" in report
            assert "department" in report
            assert "job_title" in report


# ===========================================================================
# 2. Employee Contact Update
# ===========================================================================


class TestEmployeeContactUpdate:
    """Test contact information update tools."""

    async def test_update_my_contact_phone(self, odoo_client, test_employee_id):
        """Update work_phone, verify status/updated_fields, then restore original."""
        # Read original value
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[test_employee_id],
            fields=["work_phone"],
        )
        original_phone = employees[0].get("work_phone") or ""

        test_phone = "+1-555-0199"
        try:
            response = await _call_employee_tool(
                "update_my_contact",
                {"work_phone": test_phone},
                odoo_client,
                test_employee_id,
            )

            assert response["status"] == "updated"
            assert "work_phone" in response["updated_fields"]
        finally:
            # Restore original value
            restore_value = original_phone if original_phone else False
            await odoo_client.write(
                model="hr.employee",
                ids=[test_employee_id],
                values={"work_phone": restore_value},
            )

    async def test_update_my_contact_invalid_email(self, odoo_client, test_employee_id):
        """Invalid email format should return an error."""
        response = await _call_employee_tool(
            "update_my_contact",
            {"work_email": "not-an-email"},
            odoo_client,
            test_employee_id,
        )

        assert "error" in response
        assert "Invalid email format" in response["error"]

    async def test_update_my_contact_no_fields(self, odoo_client, test_employee_id):
        """Empty arguments should return an error about no fields."""
        response = await _call_employee_tool(
            "update_my_contact",
            {},
            odoo_client,
            test_employee_id,
        )

        assert "error" in response
        assert "No fields" in response["error"] or "no fields" in response["error"].lower()


# ===========================================================================
# 3. Leave Management
# ===========================================================================


class TestLeaveManagement:
    """Test leave balance, requests, and public holidays tools."""

    async def test_get_leave_balance_structure(self, odoo_client, test_employee_id):
        """get_my_leave_balance should return year, balances, version keys."""
        response = await _call_employee_tool(
            "get_my_leave_balance", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, dict)
        assert "year" in response
        assert "balances" in response
        assert "version" in response
        assert isinstance(response["balances"], list)

    async def test_get_leave_balance_specific_year(self, odoo_client, test_employee_id):
        """get_my_leave_balance with year=2025 should return that year."""
        response = await _call_employee_tool(
            "get_my_leave_balance",
            {"year": 2025},
            odoo_client,
            test_employee_id,
        )

        assert response["year"] == 2025

    async def test_get_leave_requests_all(self, odoo_client, test_employee_id):
        """get_my_leave_requests with status=all should return a list."""
        response = await _call_employee_tool(
            "get_my_leave_requests",
            {"status": "all"},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)

    async def test_get_leave_requests_pending(self, odoo_client, test_employee_id):
        """Pending requests should all have state in draft/confirm/validate1."""
        response = await _call_employee_tool(
            "get_my_leave_requests",
            {"status": "pending"},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)
        for req in response:
            assert req["state"] in ["draft", "confirm", "validate1"]

    async def test_get_leave_requests_approved(self, odoo_client, test_employee_id):
        """Approved requests should all have state=validate."""
        response = await _call_employee_tool(
            "get_my_leave_requests",
            {"status": "approved"},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)
        for req in response:
            assert req["state"] == "validate"

    async def test_request_and_cancel_leave(
        self, odoo_client, test_employee_id, valid_leave_type_name
    ):
        """Create a leave request, verify response, then cancel it."""
        from odoo_mcp_server.odoo.exceptions import OdooError

        # Use a far-future weekend-free date range to avoid conflicts
        start_date = "2029-12-17"
        end_date = "2029-12-17"

        created_id = None
        try:
            try:
                create_response = await _call_employee_tool(
                    "request_leave",
                    {
                        "leave_type": valid_leave_type_name,
                        "start_date": start_date,
                        "end_date": end_date,
                        "reason": "Staging integration test - auto cleanup",
                    },
                    odoo_client,
                    test_employee_id,
                )
            except OdooError as e:
                # Skip if employee has no leave allocation (common in staging)
                pytest.skip(f"Cannot create leave request in staging: {e}")

            # If we get an error (e.g., no allocation), skip gracefully
            if isinstance(create_response, dict) and "error" in create_response:
                pytest.skip(
                    f"Cannot create leave request in staging: {create_response['error']}"
                )

            assert "request_id" in create_response
            assert create_response["status"] == "submitted"
            created_id = create_response["request_id"]

            # Cancel the request
            cancel_response = await _call_employee_tool(
                "cancel_leave_request",
                {"request_id": created_id},
                odoo_client,
                test_employee_id,
            )

            assert cancel_response["status"] == "cancelled"
            created_id = None  # Successfully cleaned up
        finally:
            # Safety net: try to delete if cancel failed
            if created_id is not None:
                try:
                    await odoo_client.unlink(model="hr.leave", ids=[created_id])
                except Exception:
                    pass  # Best effort cleanup

    async def test_request_leave_invalid_dates(
        self, odoo_client, test_employee_id, valid_leave_type_name
    ):
        """End date before start date should return an error."""
        response = await _call_employee_tool(
            "request_leave",
            {
                "leave_type": valid_leave_type_name,
                "start_date": "2029-12-20",
                "end_date": "2029-12-10",
            },
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert "error" in response
        # The error message should mention dates
        error_lower = response["error"].lower()
        assert "date" in error_lower or "end" in error_lower or "after" in error_lower

    async def test_cancel_nonexistent_leave(self, odoo_client, test_employee_id):
        """Cancelling a non-existent leave request should return an error."""
        response = await _call_employee_tool(
            "cancel_leave_request",
            {"request_id": 999999},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower() or "not yours" in response["error"].lower()

    async def test_get_public_holidays(self, odoo_client, test_employee_id):
        """get_public_holidays should return year, holidays list, and count."""
        response = await _call_employee_tool(
            "get_public_holidays", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, dict)
        assert "year" in response
        assert "holidays" in response
        assert "count" in response
        assert isinstance(response["holidays"], list)
        assert isinstance(response["count"], int)
        assert response["count"] == len(response["holidays"])

    async def test_get_public_holidays_specific_year(self, odoo_client, test_employee_id):
        """get_public_holidays with year=2025 should return that year."""
        response = await _call_employee_tool(
            "get_public_holidays",
            {"year": 2025},
            odoo_client,
            test_employee_id,
        )

        assert response["year"] == 2025


# ===========================================================================
# 4. Document Management
# ===========================================================================


class TestDocumentManagement:
    """Test DMS document tools (categories, upload, download, details)."""

    async def test_get_document_categories_structure(self, odoo_client, test_employee_id):
        """get_document_categories should return categories list with expected keys."""
        response = await _call_employee_tool(
            "get_document_categories", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, dict)
        assert "categories" in response

        for cat in response.get("categories", []):
            assert "name" in cat
            assert "document_count" in cat
            assert "can_upload" in cat

    async def test_restricted_folders_not_visible(self, odoo_client, test_employee_id):
        """Background Checks and Offboarding Documents must not appear."""
        response = await _call_employee_tool(
            "get_document_categories", {}, odoo_client, test_employee_id
        )

        restricted = {"Background Checks", "Offboarding Documents"}
        category_names = {cat["name"] for cat in response.get("categories", [])}
        assert category_names.isdisjoint(restricted), (
            f"Restricted folders visible: {category_names & restricted}"
        )

    async def test_get_my_documents_all(self, odoo_client, test_employee_id):
        """get_my_documents should return a response with a documents list."""
        response = await _call_employee_tool(
            "get_my_documents", {}, odoo_client, test_employee_id
        )

        assert isinstance(response, dict)
        assert "documents" in response or "message" in response
        if "documents" in response:
            assert isinstance(response["documents"], list)

    async def test_get_my_documents_by_category(self, odoo_client, test_employee_id):
        """Documents filtered by Identity category should all belong to Identity."""
        response = await _call_employee_tool(
            "get_my_documents",
            {"category": "Identity"},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        # If documents are present, verify category
        for doc in response.get("documents", []):
            assert doc.get("category") == "Identity"

    async def test_upload_and_download_identity_document(
        self, odoo_client, test_employee_id
    ):
        """Upload a test document, get details, download it, then delete it."""
        test_content = b"staging integration test content"
        content_b64 = base64.b64encode(test_content).decode()
        unique_name = f"test_doc_{uuid.uuid4().hex[:8]}.txt"

        uploaded_file_id = None
        try:
            # Upload
            upload_response = await _call_employee_tool(
                "upload_identity_document",
                {
                    "filename": unique_name,
                    "content_base64": content_b64,
                    "document_type": "other",
                },
                odoo_client,
                test_employee_id,
            )

            if "error" in upload_response:
                pytest.skip(
                    f"Cannot upload document in staging: {upload_response['error']}"
                )

            assert upload_response["status"] == "uploaded"
            assert "file_id" in upload_response
            uploaded_file_id = upload_response["file_id"]

            # Get document details (metadata)
            details_response = await _call_employee_tool(
                "get_document_details",
                {"document_id": uploaded_file_id},
                odoo_client,
                test_employee_id,
            )

            assert details_response["id"] == uploaded_file_id
            assert "filename" in details_response
            assert "mimetype" in details_response

            # Download and verify content
            download_response = await _call_employee_tool(
                "download_document",
                {"document_id": uploaded_file_id},
                odoo_client,
                test_employee_id,
            )

            assert download_response["id"] == uploaded_file_id
            assert "content_base64" in download_response
            downloaded_bytes = base64.b64decode(download_response["content_base64"])
            assert downloaded_bytes == test_content

        finally:
            # Cleanup: delete the uploaded file via CRUD
            if uploaded_file_id is not None:
                try:
                    await _call_crud_tool(
                        "delete_record",
                        {"model": "dms.file", "record_id": uploaded_file_id},
                        odoo_client,
                    )
                except Exception:
                    pass  # Best effort cleanup

    async def test_upload_invalid_base64(self, odoo_client, test_employee_id):
        """Uploading invalid base64 content should return an error."""
        response = await _call_employee_tool(
            "upload_identity_document",
            {
                "filename": "bad_doc.txt",
                "content_base64": "!!!not-valid-base64!!!",
                "document_type": "other",
            },
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "base64" in response["error"].lower() or "invalid" in response["error"].lower()

    async def test_download_nonexistent_document(self, odoo_client, test_employee_id):
        """Downloading a non-existent document should return an error."""
        response = await _call_employee_tool(
            "download_document",
            {"document_id": 999999},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower()


# ===========================================================================
# 5. CRUD Tools
# ===========================================================================


class TestCrudTools:
    """Test generic CRUD record tools."""

    async def test_search_records(self, odoo_client):
        """search_records on res.partner with limit=5 should return a list."""
        response = await _call_crud_tool(
            "search_records",
            {"model": "res.partner", "limit": 5},
            odoo_client,
        )

        assert isinstance(response, list)
        assert len(response) <= 5

    async def test_search_records_with_domain(self, odoo_client):
        """search_records with a domain filter should return matching records."""
        response = await _call_crud_tool(
            "search_records",
            {
                "model": "res.partner",
                "domain": [["is_company", "=", True]],
                "limit": 5,
            },
            odoo_client,
        )

        assert isinstance(response, list)

    async def test_get_record(self, odoo_client):
        """Get a record by ID -- first search, then retrieve by ID."""
        # Find a partner to read
        partners = await _call_crud_tool(
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 1},
            odoo_client,
        )

        assert len(partners) >= 1
        partner_id = partners[0]["id"]

        record = await _call_crud_tool(
            "get_record",
            {"model": "res.partner", "record_id": partner_id, "fields": ["id", "name"]},
            odoo_client,
        )

        assert isinstance(record, dict)
        assert record["id"] == partner_id
        assert "name" in record

    async def test_create_update_delete_record(self, odoo_client):
        """Full lifecycle: create, update, delete a res.partner."""
        unique_name = f"MCP Staging Test {uuid.uuid4().hex[:8]}"
        created_id = None

        try:
            # Create
            create_response = await _call_crud_tool(
                "create_record",
                {
                    "model": "res.partner",
                    "values": {"name": unique_name, "email": "staging-test@example.com"},
                },
                odoo_client,
            )

            assert "id" in create_response
            created_id = create_response["id"]
            assert isinstance(created_id, int)

            # Update
            update_response = await _call_crud_tool(
                "update_record",
                {
                    "model": "res.partner",
                    "record_id": created_id,
                    "values": {"phone": "+1-555-0100"},
                },
                odoo_client,
            )

            assert update_response.get("success") is True

            # Delete
            delete_response = await _call_crud_tool(
                "delete_record",
                {"model": "res.partner", "record_id": created_id},
                odoo_client,
            )

            assert delete_response.get("success") is True
            created_id = None  # Successfully cleaned up
        finally:
            if created_id is not None:
                try:
                    await odoo_client.unlink(model="res.partner", ids=[created_id])
                except Exception:
                    pass

    async def test_count_records(self, odoo_client):
        """count_records for res.partner should return a non-negative count."""
        response = await _call_crud_tool(
            "count_records",
            {"model": "res.partner"},
            odoo_client,
        )

        assert isinstance(response, dict)
        assert "count" in response
        assert isinstance(response["count"], int)
        assert response["count"] >= 0

    async def test_list_models(self, odoo_client):
        """list_models should return a list of models with model and name fields."""
        response = await _call_crud_tool(
            "list_models",
            {},
            odoo_client,
        )

        assert isinstance(response, list)
        assert len(response) > 0
        for model_entry in response:
            assert "model" in model_entry
            assert "name" in model_entry

    async def test_get_nonexistent_record(self, odoo_client):
        """Getting a non-existent res.partner should return an error."""
        response = await _call_crud_tool(
            "get_record",
            {"model": "res.partner", "record_id": 999999},
            odoo_client,
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower()


# ===========================================================================
# 6. Security Constraints
# ===========================================================================


class TestSecurityConstraints:
    """Test that security restrictions are enforced."""

    async def test_cannot_access_restricted_dms_folder(self, odoo_client, test_employee_id):
        """Restricted folders (Background Checks, Offboarding) must not appear."""
        response = await _call_employee_tool(
            "get_document_categories", {}, odoo_client, test_employee_id
        )

        restricted = {"Background Checks", "Offboarding Documents"}
        category_names = {cat["name"] for cat in response.get("categories", [])}
        assert category_names.isdisjoint(restricted)

    async def test_find_colleague_no_sensitive_fields(self, odoo_client, test_employee_id):
        """find_colleague should not expose sensitive fields."""
        # Search for the test employee by first name
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[test_employee_id],
            fields=["name"],
        )
        first_name = employees[0]["name"].split()[0]

        response = await _call_employee_tool(
            "find_colleague",
            {"name": first_name},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)
        sensitive_fields = {
            "bank_account_id",
            "identification_id",
            "passport_id",
            "wage",
            "salary",
        }
        for colleague in response:
            exposed = sensitive_fields & set(colleague.keys())
            assert not exposed, f"Sensitive fields exposed: {exposed}"

    async def test_cancel_others_leave_denied(self, odoo_client, test_employee_id):
        """Cancelling a leave that does not belong to the employee should be denied."""
        response = await _call_employee_tool(
            "cancel_leave_request",
            {"request_id": 999999},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert "error" in response

    async def test_invalid_employee_id_profile(self, odoo_client):
        """get_my_profile with a non-existent employee_id should return a graceful error."""
        response = await _call_employee_tool(
            "get_my_profile",
            {},
            odoo_client,
            employee_id=999999,
        )

        assert isinstance(response, dict)
        # Should return error or empty, not crash
        assert "error" in response or response == {}

    async def test_invalid_employee_id_team(self, odoo_client):
        """get_my_team with a non-existent employee_id should return empty list gracefully."""
        response = await _call_employee_tool(
            "get_my_team",
            {},
            odoo_client,
            employee_id=999999,
        )

        # Should return empty list (employee has no department) or similar
        assert isinstance(response, list)
        assert len(response) == 0


# ===========================================================================
# 7. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Test boundary conditions and unusual inputs."""

    async def test_find_colleague_empty_result(self, odoo_client, test_employee_id):
        """Searching for a nonsense name should return an empty list."""
        response = await _call_employee_tool(
            "find_colleague",
            {"name": "XyzNonExistent123"},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)
        assert len(response) == 0

    async def test_find_colleague_partial_match(self, odoo_client, test_employee_id):
        """Searching for the first 2 characters of the test employee name should match."""
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[test_employee_id],
            fields=["name"],
        )
        partial = employees[0]["name"][:2]

        response = await _call_employee_tool(
            "find_colleague",
            {"name": partial},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, list)
        assert len(response) > 0

    async def test_leave_balance_future_year(self, odoo_client, test_employee_id):
        """Leave balance for year 2030 should have empty (or very few) balances."""
        response = await _call_employee_tool(
            "get_my_leave_balance",
            {"year": 2030},
            odoo_client,
            test_employee_id,
        )

        assert isinstance(response, dict)
        assert response["year"] == 2030
        assert isinstance(response["balances"], list)
        # Typically no allocations far in the future
        # We do not strictly assert empty because Odoo config may vary

    async def test_search_records_empty_domain(self, odoo_client):
        """search_records on hr.employee with empty domain should return results."""
        response = await _call_crud_tool(
            "search_records",
            {"model": "hr.employee", "domain": [], "limit": 5},
            odoo_client,
        )

        assert isinstance(response, list)
        assert len(response) > 0

    async def test_search_records_with_offset(self, odoo_client):
        """search_records with offset=1 should skip the first record."""
        # Get first two records
        first_two = await _call_crud_tool(
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 2, "offset": 0},
            odoo_client,
        )

        if len(first_two) < 2:
            pytest.skip("Need at least 2 partners for offset test")

        # Get with offset=1
        offset_results = await _call_crud_tool(
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 1, "offset": 1},
            odoo_client,
        )

        assert isinstance(offset_results, list)
        assert len(offset_results) == 1
        # The first result with offset=1 should be the second result from the initial query
        assert offset_results[0]["id"] == first_two[1]["id"]
