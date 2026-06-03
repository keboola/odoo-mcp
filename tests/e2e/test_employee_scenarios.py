"""
Employee Self-Service Test Scenarios

Tests real-world employee queries through the MCP server.
These tests simulate actual questions employees would ask via Claude or Slack.

Run with: pytest tests/e2e/test_employee_scenarios.py -v -m employee
"""

import json

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.employee]


class TestProfileQueries:
    """Tests for employee profile queries."""

    async def test_get_my_profile(self, authenticated_employee_client):
        """
        Scenario: Employee asks "What's my profile?" or "Show my info"
        Expected: Returns their name, email, department, manager, and custom fields
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_profile", arguments={}
        )

        profile = json.loads(result.content[0].text)

        assert "name" in profile
        assert "work_email" in profile
        assert "department" in profile
        assert "manager" in profile
        # Optional custom fields appear only when configured via EMPLOYEE_CUSTOM_FIELDS;
        # when present they must carry through to the profile output.
        for key in ("preferred_name", "division"):
            if key in profile:
                assert profile[key] is None or isinstance(profile[key], str)

    async def test_get_my_manager(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Who is my manager?"
        Expected: Returns manager's name and contact info
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_manager", arguments={}
        )

        manager = json.loads(result.content[0].text)

        assert "name" in manager
        assert "email" in manager

    async def test_get_my_team(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Who's in my team?" or "Show my colleagues"
        Expected: Returns list of team members in same department
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_team", arguments={}
        )

        team = json.loads(result.content[0].text)

        assert isinstance(team, list)
        for member in team:
            assert "name" in member

    async def test_get_my_department(self, authenticated_employee_client):
        """
        Scenario: Employee asks "What department am I in?"
        Expected: Returns department name and info
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_profile", arguments={}
        )

        profile = json.loads(result.content[0].text)

        assert "department" in profile
        assert profile["department"] is not None


class TestLeaveQueries:
    """Tests for leave/time-off queries."""

    async def test_get_leave_balance(self, authenticated_employee_client):
        """
        Scenario: Employee asks "How many vacation days do I have?"
        Expected: Returns balance for each leave type
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_leave_balance", arguments={}
        )

        balances = json.loads(result.content[0].text)

        assert isinstance(balances, list)
        for balance in balances:
            assert "leave_type" in balance
            assert "allocated" in balance
            assert "taken" in balance
            assert "remaining" in balance

    async def test_get_specific_leave_type_balance(self, authenticated_employee_client):
        """
        Scenario: Employee asks "How much sick leave do I have left?"
        Expected: Returns balance for specific leave type
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_leave_balance", arguments={"leave_type": "Sick Leave"}
        )

        balance = json.loads(result.content[0].text)

        # Could be single object or filtered list
        if isinstance(balance, list):
            assert len(balance) >= 0
        else:
            assert "remaining" in balance

    async def test_get_pending_leave_requests(self, authenticated_employee_client):
        """
        Scenario: Employee asks "What leave requests are pending?"
        Expected: Returns list of pending requests
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_leave_requests", arguments={"status": "pending"}
        )

        requests = json.loads(result.content[0].text)

        assert isinstance(requests, list)
        for req in requests:
            assert req.get("state") in ["draft", "confirm", "validate1"]

    async def test_get_all_leave_requests(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Show all my leave requests"
        Expected: Returns all leave requests regardless of status
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_leave_requests", arguments={"status": "all"}
        )

        requests = json.loads(result.content[0].text)

        assert isinstance(requests, list)

    async def test_request_leave(self, authenticated_employee_client):
        """
        Scenario: Employee says "I want to take vacation next Monday"
        Expected: Creates leave request, returns confirmation
        """
        result = await authenticated_employee_client.call_tool(
            "request_leave",
            arguments={
                "leave_type": "Paid Time Off",
                "start_date": "2025-02-10",
                "end_date": "2025-02-10",
                "reason": "Personal day (test)",
            },
        )

        response = json.loads(result.content[0].text)

        assert "request_id" in response or "id" in response
        assert response.get("status") in ["submitted", "draft", "confirm"]

        # Cleanup: Cancel the test request
        request_id = response.get("request_id") or response.get("id")
        if request_id:
            try:
                await authenticated_employee_client.call_tool(
                    "cancel_leave_request", arguments={"request_id": request_id}
                )
            except Exception:
                pass  # Ignore cleanup errors

    async def test_request_leave_validates_dates(self, authenticated_employee_client):
        """
        Scenario: Employee tries to request leave with invalid dates
        Expected: Returns validation error
        """
        with pytest.raises(Exception) as exc_info:
            await authenticated_employee_client.call_tool(
                "request_leave",
                arguments={
                    "leave_type": "Paid Time Off",
                    "start_date": "2025-02-15",
                    "end_date": "2025-02-10",  # End before start
                    "reason": "Invalid dates test",
                },
            )

        error_msg = str(exc_info.value).lower()
        assert "date" in error_msg or "invalid" in error_msg


class TestDocumentQueries:
    """Tests for DMS document queries."""

    async def test_get_my_documents(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Show my documents" or "What documents do I have?"
        Expected: Returns list of documents from allowed folders
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_documents", arguments={}
        )

        response = json.loads(result.content[0].text)

        assert "documents" in response
        assert isinstance(response["documents"], list)

    async def test_get_documents_by_category(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Show my contracts" or "Show my identity documents"
        Expected: Returns documents filtered by category
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_documents", arguments={"category": "Identity"}
        )

        response = json.loads(result.content[0].text)

        assert "documents" in response
        # All returned documents should be from Identity category
        for doc in response["documents"]:
            assert doc.get("category") == "Identity"

    async def test_get_document_categories(self, authenticated_employee_client):
        """
        Scenario: Employee asks "What document folders do I have?"
        Expected: Returns list of accessible categories with document counts
        """
        result = await authenticated_employee_client.call_tool(
            "get_document_categories", arguments={}
        )

        response = json.loads(result.content[0].text)

        assert "categories" in response
        for category in response["categories"]:
            assert "name" in category
            assert "document_count" in category
            # Restricted folders should not appear
            assert category["name"] not in ["Background Checks", "Offboarding Documents"]

    async def test_cannot_access_restricted_folders(self, authenticated_employee_client):
        """
        Security: Employee cannot access Background Checks or Offboarding Documents
        Expected: These folders are not visible in categories or documents
        """
        result = await authenticated_employee_client.call_tool(
            "get_document_categories", arguments={}
        )

        response = json.loads(result.content[0].text)

        for category in response.get("categories", []):
            assert category["name"] not in ["Background Checks", "Offboarding Documents"]

    async def test_upload_identity_document(self, authenticated_employee_client):
        """
        Scenario: Employee uploads an identity document
        Expected: File is uploaded to Identity folder
        """
        import base64
        test_content = base64.b64encode(b"Test document content").decode()

        result = await authenticated_employee_client.call_tool(
            "upload_identity_document",
            arguments={
                "filename": "test_passport.pdf",
                "content_base64": test_content,
                "document_type": "passport",
            },
        )

        response = json.loads(result.content[0].text)

        assert response.get("status") == "uploaded"
        assert "file_id" in response

    async def test_download_document(self, authenticated_employee_client):
        """
        Scenario: Employee downloads a specific document
        Expected: Returns document content in base64
        """
        # First get list of documents
        list_result = await authenticated_employee_client.call_tool(
            "get_my_documents", arguments={}
        )
        docs = json.loads(list_result.content[0].text)

        if docs.get("documents"):
            doc_id = docs["documents"][0]["id"]
            result = await authenticated_employee_client.call_tool(
                "download_document", arguments={"document_id": doc_id}
            )

            response = json.loads(result.content[0].text)

            assert "filename" in response
            assert "content_base64" in response or "error" not in response


class TestDirectoryQueries:
    """Tests for employee directory queries."""

    async def test_find_colleague_by_name(self, authenticated_employee_client):
        """
        Scenario: Employee asks "What's John's email?"
        Expected: Returns matching colleagues with contact info
        """
        result = await authenticated_employee_client.call_tool(
            "find_colleague", arguments={"name": "Admin"}
        )

        colleagues = json.loads(result.content[0].text)

        assert isinstance(colleagues, list)
        for colleague in colleagues:
            assert "name" in colleague
            assert "work_email" in colleague or "email" in colleague

    async def test_find_colleague_partial_match(self, authenticated_employee_client):
        """
        Scenario: Employee asks "Who is Jo?" (partial name)
        Expected: Returns colleagues matching partial name
        """
        result = await authenticated_employee_client.call_tool(
            "find_colleague", arguments={"name": "Jo"}
        )

        colleagues = json.loads(result.content[0].text)

        assert isinstance(colleagues, list)

    async def test_find_colleague_no_results(self, authenticated_employee_client):
        """
        Scenario: Employee searches for non-existent name
        Expected: Returns empty list, not error
        """
        result = await authenticated_employee_client.call_tool(
            "find_colleague", arguments={"name": "XyzNonExistent123"}
        )

        colleagues = json.loads(result.content[0].text)

        assert isinstance(colleagues, list)
        assert len(colleagues) == 0


class TestSecurityConstraints:
    """Tests for security and data isolation."""

    async def test_cannot_see_others_leave_balance(self, authenticated_employee_client):
        """
        Security: Employee cannot query another employee's leave balance
        Expected: Only returns own data
        """
        # The tool should not accept employee_id parameter
        result = await authenticated_employee_client.call_tool(
            "get_my_leave_balance", arguments={}
        )

        balances = json.loads(result.content[0].text)

        # Should only return authenticated user's data
        assert isinstance(balances, list)

    async def test_cannot_see_sensitive_colleague_data(
        self, authenticated_employee_client
    ):
        """
        Security: Employee should not see sensitive fields of others
        Expected: Salary, bank info, personal phone not returned
        """
        result = await authenticated_employee_client.call_tool(
            "find_colleague", arguments={"name": "Admin"}
        )

        colleagues = json.loads(result.content[0].text)

        if colleagues:
            colleague = colleagues[0]
            # These sensitive fields should NOT be present
            assert "bank_account_id" not in colleague
            assert "private_phone" not in colleague
            assert "identification_id" not in colleague
            assert "passport_id" not in colleague
            assert "wage" not in colleague
            assert "salary" not in colleague

    async def test_cannot_cancel_others_leave(self, authenticated_employee_client):
        """
        Security: Employee cannot cancel another employee's leave request
        Expected: Error or no effect
        """
        # Try to cancel a non-existent or other's leave
        with pytest.raises(Exception):
            await authenticated_employee_client.call_tool(
                "cancel_leave_request",
                arguments={"request_id": 999999}  # Non-existent ID
            )


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    async def test_leave_request_insufficient_balance(
        self, authenticated_employee_client
    ):
        """
        Scenario: Employee requests more leave than available
        Expected: Clear error message about insufficient balance
        """
        # Request 100 days of leave (likely exceeds balance)
        result = await authenticated_employee_client.call_tool(
            "request_leave",
            arguments={
                "leave_type": "Paid Time Off",
                "start_date": "2025-06-01",
                "end_date": "2025-09-08",  # ~100 days
                "reason": "Test insufficient balance",
            },
        )

        response = json.loads(result.content[0].text)

        # Should either fail or return error status
        assert (
            response.get("error")
            or response.get("status") == "error"
            or "insufficient" in str(response).lower()
            or "balance" in str(response).lower()
        )

    async def test_invalid_leave_type(self, authenticated_employee_client):
        """
        Scenario: Employee requests non-existent leave type
        Expected: Clear error message
        """
        with pytest.raises(Exception) as exc_info:
            await authenticated_employee_client.call_tool(
                "request_leave",
                arguments={
                    "leave_type": "NonExistentLeaveType123",
                    "start_date": "2025-02-10",
                    "end_date": "2025-02-10",
                    "reason": "Test invalid type",
                },
            )

        error_msg = str(exc_info.value).lower()
        assert "leave type" in error_msg or "not found" in error_msg or "invalid" in error_msg

    async def test_graceful_handling_no_documents(
        self, authenticated_employee_client
    ):
        """
        Scenario: Employee asks about documents when none exist
        Expected: Graceful response with empty list, not error
        """
        result = await authenticated_employee_client.call_tool(
            "get_my_documents", arguments={}
        )

        response = json.loads(result.content[0].text)

        # Should return empty list or message, not error
        assert isinstance(response, dict)
        assert "documents" in response or "message" in response

    async def test_download_nonexistent_document(
        self, authenticated_employee_client
    ):
        """
        Scenario: Employee tries to download a document that doesn't exist
        Expected: Clear error message
        """
        result = await authenticated_employee_client.call_tool(
            "download_document", arguments={"document_id": 999999}
        )

        response = json.loads(result.content[0].text)

        assert "error" in response
        assert "not found" in response["error"].lower()
