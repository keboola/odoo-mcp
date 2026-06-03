"""
Pytest Fixtures for Odoo MCP Server Tests

Provides reusable fixtures for authentication, MCP clients,
and test data management.
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator

import httpx
import pytest


@pytest.fixture(scope="session", autouse=True)
def _default_test_env():
    """Provide dummy required settings so the app imports without live config.

    ``Settings`` requires ODOO_URL/ODOO_DB with no defaults (fail-fast at startup).
    Unit tests don't talk to a real Odoo, so we set placeholders here. Real
    integration/CI runs override these via actual environment variables.
    """
    os.environ.setdefault("ODOO_URL", "http://localhost:8069")
    os.environ.setdefault("ODOO_DB", "test_db")
    yield


# Configuration from environment
TEST_CONFIG = {
    "mcp_server_url": os.getenv("TEST_MCP_SERVER_URL", "http://localhost:8000"),
    "auth_server_url": os.getenv("TEST_AUTH_SERVER_URL", "https://auth.example.com"),
    "odoo_url": os.getenv("TEST_ODOO_URL", "http://localhost:8069"),
    "odoo_db": os.getenv("TEST_ODOO_DB", "test_db"),
    "test_user_email": os.getenv("TEST_USER_EMAIL"),
    "test_user_password": os.getenv("TEST_USER_PASSWORD"),
    "test_api_key": os.getenv("TEST_ODOO_API_KEY"),
    "test_client_id": os.getenv("TEST_CLIENT_ID"),
    "test_client_secret": os.getenv("TEST_CLIENT_SECRET"),
}


@pytest.fixture
def test_config() -> dict:
    """Return test configuration."""
    return TEST_CONFIG


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide async HTTP client."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
async def valid_access_token() -> str | None:
    """
    Obtain a valid OAuth access token for testing.

    In CI/CD, this uses client credentials grant.
    """
    if not TEST_CONFIG["test_client_id"]:
        pytest.skip("TEST_CLIENT_ID not configured")
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TEST_CONFIG['auth_server_url']}/token",
            data={
                "grant_type": "client_credentials",
                "client_id": TEST_CONFIG["test_client_id"],
                "client_secret": TEST_CONFIG["test_client_secret"],
                "scope": "openid odoo.read odoo.write",
            },
        )

        if response.status_code != 200:
            pytest.skip("Could not obtain test access token")
            return None

        tokens = response.json()
        return tokens["access_token"]


@pytest.fixture
async def valid_refresh_token() -> str | None:
    """Obtain a valid refresh token for testing."""
    if not TEST_CONFIG["test_client_id"]:
        pytest.skip("TEST_CLIENT_ID not configured")
        return None

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TEST_CONFIG['auth_server_url']}/token",
            data={
                "grant_type": "client_credentials",
                "client_id": TEST_CONFIG["test_client_id"],
                "client_secret": TEST_CONFIG["test_client_secret"],
                "scope": "openid odoo.read odoo.write offline_access",
            },
        )

        if response.status_code != 200:
            pytest.skip("Could not obtain test refresh token")
            return None

        tokens = response.json()
        return tokens.get("refresh_token")


@pytest.fixture
def pkce_challenge() -> dict:
    """Generate PKCE code verifier and challenge."""
    import base64
    import hashlib
    import secrets

    code_verifier = secrets.token_urlsafe(32)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return {"verifier": code_verifier, "challenge": code_challenge}


# Placeholder fixtures for MCP client - implement when MCP library is installed


@pytest.fixture
async def mcp_client():
    """Create unauthenticated MCP client for protocol tests."""
    # TODO: Implement with actual MCP client
    pytest.skip("MCP client not yet implemented")
    yield None


@pytest.fixture
async def authenticated_mcp_client(valid_access_token: str | None):
    """Create authenticated MCP client."""
    if not valid_access_token:
        pytest.skip("No valid access token available")

    # TODO: Implement with actual MCP client
    pytest.skip("Authenticated MCP client not yet implemented")
    yield None


@pytest.fixture
async def odoo_client():
    """Create direct Odoo client for integration tests."""
    if not TEST_CONFIG["test_api_key"]:
        pytest.skip("TEST_ODOO_API_KEY not configured")

    # TODO: Import and create OdooClient when implemented
    pytest.skip("Odoo client not yet implemented")
    yield None


@pytest.fixture
async def test_partner_id(authenticated_mcp_client) -> int:
    """Create a test partner and return its ID, cleanup after test."""
    if not authenticated_mcp_client:
        pytest.skip("No authenticated MCP client")
        yield 0

    result = await authenticated_mcp_client.call_tool(
        "create_record",
        arguments={
            "model": "res.partner",
            "values": {
                "name": f"Test Partner {asyncio.current_task().get_name()}",
                "email": "test_fixture@example.com",
            },
        },
    )

    record = json.loads(result.content[0].text)
    record_id = record["id"]

    yield record_id

    # Cleanup
    try:
        await authenticated_mcp_client.call_tool(
            "delete_record",
            arguments={"model": "res.partner", "record_id": record_id},
        )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def test_employee_id(authenticated_mcp_client) -> int:
    """Get or create a test employee."""
    if not authenticated_mcp_client:
        pytest.skip("No authenticated MCP client")
        return 0

    # Try to find existing test employee
    result = await authenticated_mcp_client.call_tool(
        "search_records",
        arguments={
            "model": "hr.employee",
            "domain": [["name", "=", "MCP Test Employee"]],
            "limit": 1,
        },
    )

    employees = json.loads(result.content[0].text)

    if employees:
        return employees[0]["id"]

    # Create if not exists
    create_result = await authenticated_mcp_client.call_tool(
        "create_record",
        arguments={"model": "hr.employee", "values": {"name": "MCP Test Employee"}},
    )

    employee = json.loads(create_result.content[0].text)
    return employee["id"]


@pytest.fixture
async def authenticated_employee_client(valid_access_token: str | None):
    """
    Create authenticated MCP client configured for employee self-service.

    This client has the employee_id automatically set based on the OAuth token.
    """
    if not valid_access_token:
        pytest.skip("No valid access token available")

    # TODO: Implement with actual MCP client that:
    # 1. Uses employee tools instead of CRUD tools
    # 2. Automatically maps OAuth user to employee_id
    # 3. Filters all operations to user's own data
    pytest.skip("Authenticated employee MCP client not yet implemented")
    yield None


@pytest.fixture
def employee_test_config() -> dict:
    """Return test configuration for employee scenarios."""
    return {
        "features": {
            "profile": True,
            "directory": True,
            "leave": True,
            "documents": True,
        },
        "test_employee": {
            "name": "Test Employee",
            "email": TEST_CONFIG.get("test_user_email"),
        },
    }
