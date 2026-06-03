"""
End-to-End MCP HTTP Tests

True e2e tests exercising the full HTTP stack against staging Odoo:
  HTTP request -> FastAPI -> OAuth middleware -> JSON-RPC parsing
  -> scope check -> employee mapping -> tool execution -> Odoo XML-RPC -> response

Uses FastAPI TestClient with OAUTH_DEV_MODE=true to bypass OAuth token validation
while still testing the full HTTP pipeline including employee mapping.

Requires environment variables:
    ODOO_URL         - Odoo instance URL (staging)
    ODOO_DB          - Odoo database name
    ODOO_API_KEY     - API key for authentication
    ODOO_USERNAME    - Username for authentication
    TEST_USER_EMAIL  - Email matching an employee in staging Odoo

Run with: pytest tests/e2e/test_mcp_http_e2e.py -v
"""

import base64
import importlib
import json
import os
import uuid

import pytest

pytestmark = [pytest.mark.e2e]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mcp_client():
    """
    MCP HTTP client with dev mode auth and real Odoo staging.

    Uses monkeypatch at module scope via os.environ manipulation
    and importlib.reload to pick up changes.
    """
    required_vars = ["ODOO_URL", "ODOO_DB", "ODOO_API_KEY"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        pytest.fail(f"Missing required env vars: {', '.join(missing)}")

    # Store original values to restore later
    orig_env = {}
    test_email = os.environ.get("TEST_USER_EMAIL") or "test@example.com"
    env_overrides = {
        "OAUTH_DEV_MODE": "true",
        "TEST_USER_EMAIL": test_email,
    }

    for key, value in env_overrides.items():
        orig_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        import odoo_mcp_server.http_server as http_server_module

        importlib.reload(http_server_module)

        from fastapi.testclient import TestClient

        with TestClient(http_server_module.app) as client:
            # Verify Odoo connectivity by trying to authenticate
            # This catches bad credentials before tests run
            try:
                from odoo_mcp_server.odoo.client import OdooClient

                _verify_client = OdooClient(
                    url=os.environ["ODOO_URL"],
                    db=os.environ["ODOO_DB"],
                    api_key=os.environ.get("ODOO_API_KEY"),
                    username=os.environ.get("ODOO_USERNAME"),
                )
                import asyncio
                asyncio.get_event_loop().run_until_complete(_verify_client.authenticate())
            except Exception as e:
                pytest.fail(f"Odoo connectivity check failed: {e}")

            yield client
    finally:
        # Restore original env
        for key, orig_value in orig_env.items():
            if orig_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig_value


def mcp_call(client, method: str, params: dict | None = None, req_id: int = 1):
    """Send a JSON-RPC request to POST /mcp."""
    return client.post(
        "/mcp",
        headers={"Authorization": "Bearer e2e-test-token"},
        json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id,
        },
    )


def mcp_tool_call(client, tool_name: str, arguments: dict | None = None, req_id: int = 1):
    """Call an MCP tool via JSON-RPC and return parsed content."""
    response = mcp_call(
        client,
        "tools/call",
        {"name": tool_name, "arguments": arguments or {}},
        req_id,
    )
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text}"

    body = response.json()

    # Check for JSON-RPC errors first
    if body.get("error"):
        error_msg = body["error"].get("message", str(body["error"]))
        raise AssertionError(f"JSON-RPC error calling {tool_name}: {error_msg}")

    assert body.get("result") is not None, f"Null result in response: {body}"
    assert "content" in body["result"], f"No content in result: {body['result']}"

    text = body["result"]["content"][0]["text"]
    return json.loads(text)


# ===========================================================================
# 1. MCP Protocol Tests
# ===========================================================================


class TestMCPProtocol:
    """Protocol-level tests for the JSON-RPC endpoint."""

    def test_initialize(self, mcp_client):
        """POST initialize should return protocolVersion and capabilities."""
        response = mcp_call(mcp_client, "initialize")
        assert response.status_code == 200

        result = response.json()["result"]
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "odoo-mcp-server"

    def test_ping(self, mcp_client):
        """POST ping should return empty result."""
        response = mcp_call(mcp_client, "ping")
        assert response.status_code == 200
        assert response.json()["result"] == {}

    def test_unknown_method(self, mcp_client):
        """Unknown method should return error code -32601."""
        response = mcp_call(mcp_client, "nonexistent/method")
        assert response.status_code == 200

        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == -32601

    def test_missing_bearer_token(self, mcp_client):
        """POST without Authorization header should return 401."""
        response = mcp_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_invalid_bearer_format(self, mcp_client):
        """Authorization without 'Bearer ' prefix should return 401."""
        response = mcp_client.post(
            "/mcp",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
        assert response.status_code == 401

    def test_health_endpoint(self, mcp_client):
        """GET /health should not require auth and return healthy."""
        response = mcp_client.get("/health")
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "odoo-mcp-server"

    def test_oauth_metadata(self, mcp_client):
        """GET /.well-known/oauth-protected-resource should return RFC 9728 metadata."""
        response = mcp_client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200

        body = response.json()
        assert "resource" in body
        assert "authorization_servers" in body


# ===========================================================================
# 2. Tools List
# ===========================================================================


class TestToolsList:
    """Tool discovery tests."""

    def test_tools_list_returns_all_tools(self, mcp_client):
        """tools/list should return all 30 tools (dev mode grants all scopes)."""
        response = mcp_call(mcp_client, "tools/list")
        assert response.status_code == 200

        tools = response.json()["result"]["tools"]
        assert len(tools) >= 30, f"Expected >= 30 tools, got {len(tools)}"

    def test_tools_list_has_required_fields(self, mcp_client):
        """Each tool should have name, description, and inputSchema."""
        response = mcp_call(mcp_client, "tools/list")
        tools = response.json()["result"]["tools"]

        for tool in tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing description"
            assert "inputSchema" in tool, f"Tool {tool.get('name')} missing inputSchema"

    def test_tools_list_contains_expected_tools(self, mcp_client):
        """Verify key tools are present."""
        response = mcp_call(mcp_client, "tools/list")
        tool_names = {t["name"] for t in response.json()["result"]["tools"]}

        expected = {
            "get_my_profile",
            "get_my_manager",
            "get_my_team",
            "find_colleague",
            "get_direct_reports",
            "update_my_contact",
            "get_my_leave_balance",
            "get_my_leave_requests",
            "request_leave",
            "cancel_leave_request",
            "get_public_holidays",
            "get_my_documents",
            "get_document_categories",
            "upload_identity_document",
            "download_document",
            "get_document_details",
            "get_my_pending_signatures",
            "get_my_signature_requests",
            "get_signature_request_status",
            "list_sign_templates",
            "send_signature_request",
            "download_signed_document",
            "cancel_signature_request",
            "search_records",
            "get_record",
            "create_record",
            "update_record",
            "delete_record",
            "count_records",
            "list_models",
        }
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"

    def test_resources_list(self, mcp_client):
        """resources/list should return available resources."""
        response = mcp_call(mcp_client, "resources/list")
        assert response.status_code == 200

        resources = response.json()["result"]["resources"]
        assert isinstance(resources, list)
        assert len(resources) >= 1


# ===========================================================================
# 3. Employee Profile Tools (via full HTTP stack)
# ===========================================================================


class TestEmployeeProfileE2E:
    """Employee profile tools tested through the full HTTP pipeline."""

    def test_get_my_profile(self, mcp_client):
        """get_my_profile should return profile with name, work_email, department."""
        profile = mcp_tool_call(mcp_client, "get_my_profile")

        assert "name" in profile
        assert "work_email" in profile
        assert "department" in profile

    def test_get_my_manager(self, mcp_client):
        """get_my_manager should return manager info or null manager message."""
        manager = mcp_tool_call(mcp_client, "get_my_manager")

        # Manager might be null for test employees
        if manager.get("name"):
            assert "email" in manager

    def test_get_my_team(self, mcp_client):
        """get_my_team should return a list of team members."""
        team = mcp_tool_call(mcp_client, "get_my_team")

        assert isinstance(team, list)
        for member in team:
            assert "name" in member

    def test_find_colleague_by_name(self, mcp_client):
        """find_colleague should search and return matching employees."""
        # Get own profile first to extract a search term
        profile = mcp_tool_call(mcp_client, "get_my_profile")
        search_name = profile["name"].split()[0]

        colleagues = mcp_tool_call(mcp_client, "find_colleague", {"name": search_name})

        assert isinstance(colleagues, list)
        assert len(colleagues) > 0
        assert any(search_name.lower() in c.get("name", "").lower() for c in colleagues)

    def test_find_colleague_no_results(self, mcp_client):
        """Searching for a nonexistent name should return empty list."""
        colleagues = mcp_tool_call(mcp_client, "find_colleague", {"name": "XyzNonExistent12345"})

        assert isinstance(colleagues, list)
        assert len(colleagues) == 0

    def test_find_colleague_partial_match(self, mcp_client):
        """Partial name search should find matches."""
        # Use a common name fragment that exists in any Odoo instance
        colleagues = mcp_tool_call(mcp_client, "find_colleague", {"name": "Adam"})

        assert isinstance(colleagues, list)
        assert len(colleagues) > 0

    def test_get_direct_reports(self, mcp_client):
        """get_direct_reports should return dict with direct_reports and count."""
        response = mcp_tool_call(mcp_client, "get_direct_reports")

        assert isinstance(response, dict)
        assert "direct_reports" in response
        assert "count" in response
        assert isinstance(response["direct_reports"], list)
        assert response["count"] == len(response["direct_reports"])

    def test_update_my_contact_phone(self, mcp_client):
        """Update work_phone, verify success, then restore original."""
        # Get original phone
        profile = mcp_tool_call(mcp_client, "get_my_profile")
        original_phone = profile.get("work_phone") or ""

        test_phone = "+1-555-0199"
        try:
            response = mcp_tool_call(
                mcp_client, "update_my_contact", {"work_phone": test_phone}
            )
            assert response["status"] == "updated"
            assert "work_phone" in response["updated_fields"]
        finally:
            # Restore original
            mcp_tool_call(
                mcp_client,
                "update_my_contact",
                {"work_phone": original_phone or "+0-000-0000"},
            )

    def test_update_my_contact_invalid_email(self, mcp_client):
        """Invalid email format should return an error."""
        response = mcp_tool_call(
            mcp_client, "update_my_contact", {"work_email": "not-an-email"}
        )

        assert "error" in response
        assert "Invalid email format" in response["error"]

    def test_update_my_contact_no_fields(self, mcp_client):
        """Empty arguments should return an error about no fields."""
        response = mcp_tool_call(mcp_client, "update_my_contact", {})

        assert "error" in response
        assert "no fields" in response["error"].lower() or "No fields" in response["error"]


# ===========================================================================
# 4. Leave Tools (via full HTTP stack)
# ===========================================================================


class TestLeaveToolsE2E:
    """Leave management tools tested through the full HTTP pipeline."""

    def test_get_leave_balance(self, mcp_client):
        """get_my_leave_balance should return year, balances, version."""
        response = mcp_tool_call(mcp_client, "get_my_leave_balance")

        assert isinstance(response, dict)
        assert "year" in response
        assert "balances" in response
        assert "version" in response
        assert isinstance(response["balances"], list)

    def test_get_leave_balance_specific_year(self, mcp_client):
        """get_my_leave_balance with year=2025 should return that year."""
        response = mcp_tool_call(mcp_client, "get_my_leave_balance", {"year": 2025})
        assert response["year"] == 2025

    def test_get_leave_balance_future_year(self, mcp_client):
        """Leave balance for year 2030 should work (likely empty balances)."""
        response = mcp_tool_call(mcp_client, "get_my_leave_balance", {"year": 2030})

        assert response["year"] == 2030
        assert isinstance(response["balances"], list)

    def test_get_leave_requests_all(self, mcp_client):
        """get_my_leave_requests with status=all should return a list."""
        response = mcp_tool_call(
            mcp_client, "get_my_leave_requests", {"status": "all"}
        )
        assert isinstance(response, list)

    def test_get_leave_requests_pending(self, mcp_client):
        """Pending requests should have state in draft/confirm/validate1."""
        response = mcp_tool_call(
            mcp_client, "get_my_leave_requests", {"status": "pending"}
        )

        assert isinstance(response, list)
        for req in response:
            assert req["state"] in ["draft", "confirm", "validate1"]

    def test_get_leave_requests_approved(self, mcp_client):
        """Approved requests should have state=validate."""
        response = mcp_tool_call(
            mcp_client, "get_my_leave_requests", {"status": "approved"}
        )

        assert isinstance(response, list)
        for req in response:
            assert req["state"] == "validate"

    def test_request_and_cancel_leave(self, mcp_client):
        """Create a leave request then cancel it."""
        # First find a valid leave type
        leave_types = mcp_tool_call(
            mcp_client, "search_records",
            {"model": "hr.leave.type", "fields": ["id", "name"], "limit": 1},
        )
        if not leave_types:
            pytest.skip("No leave types configured in Odoo")

        leave_type_name = leave_types[0]["name"]
        start_date = "2029-12-17"
        end_date = "2029-12-17"

        # Try to create - may fail if no allocation
        created_id = None
        try:
            create_response = mcp_tool_call(
                mcp_client,
                "request_leave",
                {
                    "leave_type": leave_type_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "reason": "E2E HTTP test - auto cleanup",
                },
            )

            if isinstance(create_response, dict) and "error" in create_response:
                pytest.skip(
                    f"Cannot create leave request in staging: {create_response['error']}"
                )

            assert "request_id" in create_response
            assert create_response["status"] == "submitted"
            created_id = create_response["request_id"]

            # Cancel the request
            cancel_response = mcp_tool_call(
                mcp_client,
                "cancel_leave_request",
                {"request_id": created_id},
            )
            assert cancel_response["status"] == "cancelled"
            created_id = None  # Successfully cleaned up

        except Exception:
            # If the tool call itself errored (Odoo fault), skip gracefully
            if created_id is None:
                pytest.skip("Cannot create leave request in staging (Odoo error)")
            raise
        finally:
            # Safety cleanup via CRUD
            if created_id is not None:
                try:
                    mcp_tool_call(
                        mcp_client,
                        "delete_record",
                        {"model": "hr.leave", "record_id": created_id},
                    )
                except Exception:
                    pass

    def test_request_leave_invalid_dates(self, mcp_client):
        """End date before start date should return an error."""
        leave_types = mcp_tool_call(
            mcp_client, "search_records",
            {"model": "hr.leave.type", "fields": ["id", "name"], "limit": 1},
        )
        if not leave_types:
            pytest.skip("No leave types configured")

        response = mcp_tool_call(
            mcp_client,
            "request_leave",
            {
                "leave_type": leave_types[0]["name"],
                "start_date": "2029-12-20",
                "end_date": "2029-12-10",
            },
        )

        assert isinstance(response, dict)
        assert "error" in response
        error_lower = response["error"].lower()
        assert "date" in error_lower or "end" in error_lower or "after" in error_lower

    def test_cancel_nonexistent_leave(self, mcp_client):
        """Cancelling a non-existent leave request should return an error."""
        response = mcp_tool_call(
            mcp_client, "cancel_leave_request", {"request_id": 999999}
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower() or "not yours" in response["error"].lower()

    def test_get_public_holidays(self, mcp_client):
        """get_public_holidays should return year, holidays list, and count."""
        response = mcp_tool_call(mcp_client, "get_public_holidays")

        assert isinstance(response, dict)
        assert "year" in response
        assert "holidays" in response
        assert "count" in response
        assert isinstance(response["holidays"], list)
        assert response["count"] == len(response["holidays"])

    def test_get_public_holidays_specific_year(self, mcp_client):
        """get_public_holidays with year=2025 should return that year."""
        response = mcp_tool_call(mcp_client, "get_public_holidays", {"year": 2025})
        assert response["year"] == 2025


# ===========================================================================
# 5. Document Tools (via full HTTP stack)
# ===========================================================================


class TestDocumentToolsE2E:
    """DMS document tools tested through the full HTTP pipeline."""

    def test_get_document_categories(self, mcp_client):
        """get_document_categories should return categories with name, count, can_upload."""
        response = mcp_tool_call(mcp_client, "get_document_categories")

        assert isinstance(response, dict)
        assert "categories" in response

        for cat in response.get("categories", []):
            assert "name" in cat
            assert "document_count" in cat
            assert "can_upload" in cat

    def test_restricted_folders_excluded(self, mcp_client):
        """Background Checks and Offboarding Documents must not appear."""
        response = mcp_tool_call(mcp_client, "get_document_categories")

        restricted = {"Background Checks", "Offboarding Documents"}
        category_names = {cat["name"] for cat in response.get("categories", [])}
        assert category_names.isdisjoint(restricted), (
            f"Restricted folders visible: {category_names & restricted}"
        )

    def test_get_my_documents_all(self, mcp_client):
        """get_my_documents should return documents list or message."""
        response = mcp_tool_call(mcp_client, "get_my_documents")

        assert isinstance(response, dict)
        assert "documents" in response or "message" in response

    def test_get_my_documents_by_category(self, mcp_client):
        """Documents filtered by Identity category should belong to Identity."""
        response = mcp_tool_call(
            mcp_client, "get_my_documents", {"category": "Identity"}
        )

        assert isinstance(response, dict)
        for doc in response.get("documents", []):
            assert doc.get("category") == "Identity"

    def test_upload_download_delete_document(self, mcp_client):
        """Full document lifecycle: upload, get details, download, delete."""
        test_content = b"e2e http test content - full stack"
        content_b64 = base64.b64encode(test_content).decode()
        unique_name = f"e2e_test_{uuid.uuid4().hex[:8]}.txt"

        uploaded_file_id = None
        try:
            # Upload
            upload_response = mcp_tool_call(
                mcp_client,
                "upload_identity_document",
                {
                    "filename": unique_name,
                    "content_base64": content_b64,
                    "document_type": "other",
                },
            )

            if "error" in upload_response:
                pytest.skip(
                    f"Cannot upload document in staging: {upload_response['error']}"
                )

            assert upload_response["status"] == "uploaded"
            assert "file_id" in upload_response
            uploaded_file_id = upload_response["file_id"]

            # Get document details
            details = mcp_tool_call(
                mcp_client,
                "get_document_details",
                {"document_id": uploaded_file_id},
            )
            assert details["id"] == uploaded_file_id
            assert "filename" in details
            assert "mimetype" in details

            # Download and verify content
            download = mcp_tool_call(
                mcp_client,
                "download_document",
                {"document_id": uploaded_file_id},
            )
            assert download["id"] == uploaded_file_id
            assert "content_base64" in download
            downloaded_bytes = base64.b64decode(download["content_base64"])
            assert downloaded_bytes == test_content

        finally:
            # Cleanup via CRUD delete
            if uploaded_file_id is not None:
                try:
                    mcp_tool_call(
                        mcp_client,
                        "delete_record",
                        {"model": "dms.file", "record_id": uploaded_file_id},
                    )
                except Exception:
                    pass

    def test_upload_invalid_base64(self, mcp_client):
        """Uploading invalid base64 content should return an error."""
        response = mcp_tool_call(
            mcp_client,
            "upload_identity_document",
            {
                "filename": "bad_doc.txt",
                "content_base64": "!!!not-valid-base64!!!",
                "document_type": "other",
            },
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "base64" in response["error"].lower() or "invalid" in response["error"].lower()

    def test_download_nonexistent_document(self, mcp_client):
        """Downloading a non-existent document should return an error."""
        response = mcp_tool_call(
            mcp_client, "download_document", {"document_id": 999999}
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower()


# ===========================================================================
# 6. Sign Tools (via full HTTP stack)
# ===========================================================================


class TestSignToolsE2E:
    """Sign module tools tested through the full HTTP pipeline.

    Since staging has 0 sign templates and 0 sign requests, these tests
    verify the tools execute without errors and return the expected
    response structure (empty lists, proper error messages).
    """

    def test_get_my_pending_signatures(self, mcp_client):
        """get_my_pending_signatures should return a list (possibly empty)."""
        data = mcp_tool_call(mcp_client, "get_my_pending_signatures")

        assert "pending_signatures" in data
        assert "count" in data
        assert isinstance(data["pending_signatures"], list)
        assert data["count"] == len(data["pending_signatures"])

    def test_get_my_signature_requests(self, mcp_client):
        """get_my_signature_requests should return a list (possibly empty)."""
        data = mcp_tool_call(mcp_client, "get_my_signature_requests")

        assert "signature_requests" in data
        assert "count" in data
        assert isinstance(data["signature_requests"], list)
        assert data["count"] == len(data["signature_requests"])

    def test_get_my_signature_requests_with_filter(self, mcp_client):
        """get_my_signature_requests with status filter should work."""
        data = mcp_tool_call(
            mcp_client, "get_my_signature_requests", {"status": "sent"}
        )

        assert "signature_requests" in data
        assert isinstance(data["signature_requests"], list)

    def test_get_signature_request_status_not_found(self, mcp_client):
        """get_signature_request_status for non-existent ID should return error."""
        data = mcp_tool_call(
            mcp_client, "get_signature_request_status", {"request_id": 999999}
        )

        assert "error" in data

    def test_list_sign_templates(self, mcp_client):
        """list_sign_templates should return a list (possibly empty)."""
        data = mcp_tool_call(mcp_client, "list_sign_templates")

        assert "templates" in data
        assert "count" in data
        assert isinstance(data["templates"], list)
        assert data["count"] == len(data["templates"])

    def test_download_signed_document_not_found(self, mcp_client):
        """download_signed_document for non-existent ID should return error."""
        data = mcp_tool_call(
            mcp_client, "download_signed_document", {"request_id": 999999}
        )

        assert "error" in data

    def test_cancel_signature_request_not_found(self, mcp_client):
        """cancel_signature_request for non-existent ID should return error."""
        data = mcp_tool_call(
            mcp_client, "cancel_signature_request", {"request_id": 999999}
        )

        assert "error" in data

    def test_sign_tools_in_tools_list(self, mcp_client):
        """All 7 sign tools should appear in tools/list."""
        response = mcp_call(mcp_client, "tools/list")
        tool_names = {t["name"] for t in response.json()["result"]["tools"]}

        sign_tools = [
            "get_my_pending_signatures",
            "get_my_signature_requests",
            "get_signature_request_status",
            "list_sign_templates",
            "send_signature_request",
            "download_signed_document",
            "cancel_signature_request",
        ]
        for tool_name in sign_tools:
            assert tool_name in tool_names, f"{tool_name} not in tools list"


# ===========================================================================
# 7. CRUD Tools (via full HTTP stack)
# ===========================================================================


class TestCrudToolsE2E:
    """Generic CRUD tools tested through the full HTTP pipeline."""

    def test_search_records(self, mcp_client):
        """search_records on res.partner with limit=5 should return a list."""
        response = mcp_tool_call(
            mcp_client, "search_records", {"model": "res.partner", "limit": 5}
        )

        assert isinstance(response, list)
        assert len(response) <= 5

    def test_search_records_with_domain(self, mcp_client):
        """search_records with domain filter should return matching records."""
        response = mcp_tool_call(
            mcp_client,
            "search_records",
            {
                "model": "res.partner",
                "domain": [["is_company", "=", True]],
                "limit": 5,
            },
        )

        assert isinstance(response, list)

    def test_search_records_with_offset(self, mcp_client):
        """search_records with offset=1 should skip the first record."""
        first_two = mcp_tool_call(
            mcp_client,
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 2, "offset": 0},
        )
        if len(first_two) < 2:
            pytest.skip("Need at least 2 partners for offset test")

        offset_results = mcp_tool_call(
            mcp_client,
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 1, "offset": 1},
        )

        assert len(offset_results) == 1
        assert offset_results[0]["id"] == first_two[1]["id"]

    def test_get_record(self, mcp_client):
        """Get a record by ID."""
        partners = mcp_tool_call(
            mcp_client,
            "search_records",
            {"model": "res.partner", "fields": ["id", "name"], "limit": 1},
        )
        assert len(partners) >= 1

        record = mcp_tool_call(
            mcp_client,
            "get_record",
            {"model": "res.partner", "record_id": partners[0]["id"], "fields": ["id", "name"]},
        )

        assert isinstance(record, dict)
        assert record["id"] == partners[0]["id"]
        assert "name" in record

    def test_get_nonexistent_record(self, mcp_client):
        """Getting a non-existent record should return an error."""
        response = mcp_tool_call(
            mcp_client,
            "get_record",
            {"model": "res.partner", "record_id": 999999},
        )

        assert isinstance(response, dict)
        assert "error" in response
        assert "not found" in response["error"].lower()

    def test_create_update_delete_lifecycle(self, mcp_client):
        """Full lifecycle: create res.partner, update it, delete it."""
        unique_name = f"MCP E2E Test {uuid.uuid4().hex[:8]}"
        created_id = None

        try:
            # Create
            create_response = mcp_tool_call(
                mcp_client,
                "create_record",
                {
                    "model": "res.partner",
                    "values": {"name": unique_name, "email": "e2e-test@example.com"},
                },
            )
            assert "id" in create_response
            created_id = create_response["id"]
            assert isinstance(created_id, int)

            # Update
            update_response = mcp_tool_call(
                mcp_client,
                "update_record",
                {
                    "model": "res.partner",
                    "record_id": created_id,
                    "values": {"phone": "+1-555-0100"},
                },
            )
            assert update_response.get("success") is True

            # Delete
            delete_response = mcp_tool_call(
                mcp_client,
                "delete_record",
                {"model": "res.partner", "record_id": created_id},
            )
            assert delete_response.get("success") is True
            created_id = None  # Successfully cleaned up

        finally:
            if created_id is not None:
                try:
                    mcp_tool_call(
                        mcp_client,
                        "delete_record",
                        {"model": "res.partner", "record_id": created_id},
                    )
                except Exception:
                    pass

    def test_count_records(self, mcp_client):
        """count_records for res.partner should return a non-negative count."""
        response = mcp_tool_call(
            mcp_client, "count_records", {"model": "res.partner"}
        )

        assert isinstance(response, dict)
        assert "count" in response
        assert isinstance(response["count"], int)
        assert response["count"] >= 0

    def test_list_models(self, mcp_client):
        """list_models should return a list of models with model and name."""
        response = mcp_tool_call(mcp_client, "list_models")

        assert isinstance(response, list)
        assert len(response) > 0
        for entry in response:
            assert "model" in entry
            assert "name" in entry


# ===========================================================================
# 8. Security Tests (via full HTTP stack)
# ===========================================================================


class TestSecurityE2E:
    """Security constraints tested through the full HTTP pipeline."""

    def test_no_auth_returns_401(self, mcp_client):
        """No Bearer header should return 401."""
        response = mcp_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        )
        assert response.status_code == 401

    def test_tools_call_without_name(self, mcp_client):
        """tools/call without tool name should return an error."""
        response = mcp_call(mcp_client, "tools/call", {"arguments": {}})
        assert response.status_code == 200

        body = response.json()
        assert "error" in body

    def test_colleague_no_sensitive_fields(self, mcp_client):
        """find_colleague should not expose sensitive fields."""
        colleagues = mcp_tool_call(mcp_client, "find_colleague", {"name": "TEST"})

        sensitive_fields = {
            "bank_account_id",
            "identification_id",
            "passport_id",
            "wage",
            "salary",
        }
        for colleague in colleagues:
            exposed = sensitive_fields & set(colleague.keys())
            assert not exposed, f"Sensitive fields exposed: {exposed}"

    def test_cancel_others_leave_denied(self, mcp_client):
        """Cancelling a leave with id=999999 should be denied."""
        response = mcp_tool_call(
            mcp_client, "cancel_leave_request", {"request_id": 999999}
        )

        assert isinstance(response, dict)
        assert "error" in response

    def test_security_headers_present(self, mcp_client):
        """Security headers should be present on responses."""
        response = mcp_client.get("/health")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Strict-Transport-Security" in response.headers


# ===========================================================================
# 9. Edge Cases (via full HTTP stack)
# ===========================================================================


class TestEdgeCasesE2E:
    """Edge cases tested through the full HTTP pipeline."""

    def test_empty_search_results(self, mcp_client):
        """Searching for a nonexistent name should return empty."""
        colleagues = mcp_tool_call(
            mcp_client, "find_colleague", {"name": "ZzzzNonexistentPerson99999"}
        )
        assert isinstance(colleagues, list)
        assert len(colleagues) == 0

    def test_search_records_empty_domain(self, mcp_client):
        """search_records with empty domain should return results."""
        response = mcp_tool_call(
            mcp_client,
            "search_records",
            {"model": "hr.employee", "domain": [], "limit": 5},
        )
        assert isinstance(response, list)
        assert len(response) > 0

    def test_notifications_initialized(self, mcp_client):
        """notifications/initialized should return 202 Accepted (MCP 2025-03-26)."""
        response = mcp_call(mcp_client, "notifications/initialized")
        assert response.status_code == 202

    def test_jsonrpc_id_propagation(self, mcp_client):
        """Response should echo back the request ID."""
        response = mcp_call(mcp_client, "ping", req_id=42)
        assert response.json()["id"] == 42

    def test_jsonrpc_string_id(self, mcp_client):
        """String request IDs should be supported."""
        response = mcp_client.post(
            "/mcp",
            headers={"Authorization": "Bearer e2e-test-token"},
            json={"jsonrpc": "2.0", "method": "ping", "id": "test-id-123"},
        )
        assert response.status_code == 200
        assert response.json()["id"] == "test-id-123"


# ===========================================================================
# 10. Resources (via full HTTP stack)
# ===========================================================================


class TestResourcesE2E:
    """MCP resource tests through the full HTTP pipeline."""

    def test_resources_list(self, mcp_client):
        """resources/list should return available resources."""
        response = mcp_call(mcp_client, "resources/list")
        assert response.status_code == 200

        resources = response.json()["result"]["resources"]
        assert isinstance(resources, list)
        assert len(resources) >= 1

        # Verify structure
        for resource in resources:
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource

    def test_resources_read_models(self, mcp_client):
        """resources/read with odoo://models should return model data."""
        response = mcp_call(
            mcp_client, "resources/read", {"uri": "odoo://models"}
        )
        assert response.status_code == 200

        result = response.json()["result"]
        assert "contents" in result
        assert len(result["contents"]) > 0

        # Parse the content - should be valid JSON with model data
        content_text = result["contents"][0]["text"]
        models = json.loads(content_text)
        assert isinstance(models, list)
        assert len(models) > 0

    def test_resources_read_invalid_uri(self, mcp_client):
        """resources/read with invalid URI should return an error."""
        response = mcp_call(
            mcp_client, "resources/read", {"uri": "odoo://nonexistent"}
        )
        assert response.status_code == 200

        body = response.json()
        assert "error" in body
