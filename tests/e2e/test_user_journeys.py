"""
End-to-End User Journey Tests

Tests complete user workflows from OAuth login through
Odoo data operations, simulating real Claude/Slack usage.

Run with: pytest tests/e2e/test_user_journeys.py -v -m e2e
"""

import json

import pytest

pytestmark = [pytest.mark.e2e]


class TestEmployeeInformationJourney:
    """
    User Story: As an employee, I want to check my leave balance
    and submit a leave request through Claude.
    """

    async def test_employee_views_leave_balance(
        self, authenticated_mcp_client, test_employee_id: int
    ):
        """
        Complete journey: Employee checks their leave balance.
        """
        # Step 1: Get employee record
        employee_result = await authenticated_mcp_client.call_tool(
            "get_record",
            arguments={
                "model": "hr.employee",
                "record_id": test_employee_id,
                "fields": ["name", "department_id", "remaining_leaves"],
            },
        )

        employee = json.loads(employee_result.content[0].text)
        assert "remaining_leaves" in employee or "name" in employee

        # Step 2: Get leave types available
        leave_types = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "hr.leave.type",
                "domain": [["active", "=", True]],
                "fields": ["name", "max_leaves"],
            },
        )

        types = json.loads(leave_types.content[0].text)
        assert isinstance(types, list)

    async def test_employee_submits_leave_request(
        self, authenticated_mcp_client, test_employee_id: int
    ):
        """
        Complete journey: Employee submits a leave request.
        """
        # Search for a valid leave type first
        leave_types_result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "hr.leave.type",
                "domain": [["active", "=", True]],
                "fields": ["id", "name"],
                "limit": 1,
            },
        )

        leave_types = json.loads(leave_types_result.content[0].text)
        if not leave_types:
            pytest.skip("No leave types available")

        leave_type_id = leave_types[0]["id"]

        # Create leave request
        result = await authenticated_mcp_client.call_tool(
            "create_record",
            arguments={
                "model": "hr.leave",
                "values": {
                    "employee_id": test_employee_id,
                    "holiday_status_id": leave_type_id,
                    "date_from": "2025-02-01",
                    "date_to": "2025-02-03",
                    "name": "Family vacation (MCP test)",
                },
            },
        )

        leave = json.loads(result.content[0].text)
        assert leave["id"] > 0

        # Cleanup - delete the test leave request
        await authenticated_mcp_client.call_tool(
            "delete_record",
            arguments={"model": "hr.leave", "record_id": leave["id"]},
        )


class TestSalesInformationJourney:
    """
    User Story: As a sales person, I want to check my
    sales pipeline and create a new opportunity.
    """

    async def test_salesperson_views_pipeline(self, authenticated_mcp_client):
        """
        Complete journey: Sales person checks their opportunities.
        """
        # Get opportunities in pipeline
        result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "crm.lead",
                "domain": [["type", "=", "opportunity"]],
                "fields": ["name", "expected_revenue", "stage_id", "probability"],
                "limit": 20,
            },
        )

        opportunities = json.loads(result.content[0].text)
        assert isinstance(opportunities, list)

        # Calculate pipeline value
        total_value = sum(
            opp.get("expected_revenue", 0) * opp.get("probability", 0) / 100
            for opp in opportunities
        )

        assert total_value >= 0  # Just verify calculation works

    async def test_salesperson_creates_opportunity(self, authenticated_mcp_client):
        """
        Complete journey: Sales person creates new opportunity.
        """
        # First, get a partner to link the opportunity to
        partners_result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "res.partner",
                "domain": [["is_company", "=", True]],
                "fields": ["id", "name"],
                "limit": 1,
            },
        )

        partners = json.loads(partners_result.content[0].text)
        partner_id = partners[0]["id"] if partners else False

        # Create opportunity
        result = await authenticated_mcp_client.call_tool(
            "create_record",
            arguments={
                "model": "crm.lead",
                "values": {
                    "name": "MCP Test Opportunity",
                    "type": "opportunity",
                    "expected_revenue": 50000,
                    "probability": 25,
                    "partner_id": partner_id,
                },
            },
        )

        opp = json.loads(result.content[0].text)
        assert opp["id"] > 0

        # Cleanup
        await authenticated_mcp_client.call_tool(
            "delete_record",
            arguments={"model": "crm.lead", "record_id": opp["id"]},
        )


class TestInventoryCheckJourney:
    """
    User Story: As a warehouse manager, I want to check
    stock levels for specific products.
    """

    async def test_check_product_stock(self, authenticated_mcp_client):
        """
        Complete journey: Check stock for a product.
        """
        # Search for products
        products = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "product.product",
                "domain": [["type", "=", "product"]],
                "fields": ["name", "default_code", "qty_available"],
                "limit": 5,
            },
        )

        product_list = json.loads(products.content[0].text)

        if len(product_list) > 0:
            # Get detailed stock info for first product
            product_id = product_list[0]["id"]

            stock_quants = await authenticated_mcp_client.call_tool(
                "search_records",
                arguments={
                    "model": "stock.quant",
                    "domain": [["product_id", "=", product_id]],
                    "fields": ["location_id", "quantity", "reserved_quantity"],
                },
            )

            quants = json.loads(stock_quants.content[0].text)
            assert isinstance(quants, list)


class TestContactManagementJourney:
    """
    User Story: As a user, I want to find and update
    contact information through Claude.
    """

    async def test_find_contact_by_name(self, authenticated_mcp_client):
        """
        Journey: Search for a contact by name.
        """
        result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "res.partner",
                "domain": [["name", "ilike", "admin"]],
                "fields": ["name", "email", "phone", "mobile"],
                "limit": 5,
            },
        )

        contacts = json.loads(result.content[0].text)
        assert isinstance(contacts, list)

    async def test_get_contact_details(self, authenticated_mcp_client):
        """
        Journey: Get full details of a specific contact.
        """
        # First search to get a contact ID
        search_result = await authenticated_mcp_client.call_tool(
            "search_records",
            arguments={
                "model": "res.partner",
                "domain": [],
                "fields": ["id"],
                "limit": 1,
            },
        )

        contacts = json.loads(search_result.content[0].text)
        if not contacts:
            pytest.skip("No contacts available")

        contact_id = contacts[0]["id"]

        # Get full details
        result = await authenticated_mcp_client.call_tool(
            "get_record",
            arguments={
                "model": "res.partner",
                "record_id": contact_id,
                "fields": [
                    "name",
                    "email",
                    "phone",
                    "mobile",
                    "street",
                    "city",
                    "country_id",
                    "website",
                    "comment",
                ],
            },
        )

        contact = json.loads(result.content[0].text)
        assert "name" in contact
