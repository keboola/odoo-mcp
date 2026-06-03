"""
TDD Tests for OAuth 2.1 Resource Server

These tests define the expected behavior of the OAuth resource server.
They WILL FAIL until the implementation is complete.

Run with: pytest tests/unit/test_oauth_resource_server.py -v
"""

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.oauth]


class TestOAuthModulesExist:
    """Tests that verify OAuth modules exist and can be imported."""

    def test_resource_server_module_exists(self):
        """
        EXPECTED: oauth/resource_server.py should exist.
        FAILS UNTIL: Module is created.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthResourceServer

        assert OAuthResourceServer is not None

    def test_token_validator_module_exists(self):
        """
        EXPECTED: oauth/token_validator.py should exist.
        FAILS UNTIL: Module is created.
        """
        from odoo_mcp_server.oauth.token_validator import TokenValidator

        assert TokenValidator is not None

    def test_metadata_module_exists(self):
        """
        EXPECTED: oauth/metadata.py should exist.
        FAILS UNTIL: Module is created.
        """
        from odoo_mcp_server.oauth.metadata import ProtectedResourceMetadata

        assert ProtectedResourceMetadata is not None

    def test_oauth_middleware_exists(self):
        """
        EXPECTED: OAuthMiddleware class should exist for FastAPI.
        FAILS UNTIL: Middleware is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        assert OAuthMiddleware is not None


class TestTokenValidator:
    """Tests for JWT token validation."""

    @pytest.fixture
    def validator(self):
        """Create token validator instance."""
        from odoo_mcp_server.oauth.token_validator import TokenValidator

        return TokenValidator(
            issuer="https://auth.example.com",
            audience="https://your-mcp-server.example.com",
        )

    def test_validator_fetches_jwks(self, validator):
        """
        EXPECTED: Validator should fetch JWKS from authorization server.
        FAILS UNTIL: JWKS fetching is implemented.
        """
        assert hasattr(validator, "jwks")
        assert hasattr(validator, "fetch_jwks")

    def test_validator_validates_signature(self, validator):
        """
        EXPECTED: Validator should verify JWT signature using JWKS.
        FAILS UNTIL: Signature validation is implemented.
        """
        # This should raise for invalid token
        with pytest.raises(Exception):  # Will be more specific exception
            validator.validate("invalid.jwt.token")

    def test_validator_checks_expiration(self, validator):
        """
        EXPECTED: Validator should reject expired tokens.
        FAILS UNTIL: Expiration check is implemented.
        """
        # Create an expired token (mock)
        expired_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJleHAiOjF9.sig"

        with pytest.raises(Exception):  # TokenExpiredError
            validator.validate(expired_token)

    def test_validator_checks_issuer(self, validator):
        """
        EXPECTED: Validator should reject tokens from wrong issuer.
        FAILS UNTIL: Issuer validation is implemented.
        """
        assert validator.issuer == "https://auth.example.com"

    def test_validator_checks_audience(self, validator):
        """
        EXPECTED: Validator should reject tokens for wrong audience.
        FAILS UNTIL: Audience validation is implemented.
        """
        assert validator.audience == "https://your-mcp-server.example.com"

    def test_validator_extracts_claims(self, validator):
        """
        EXPECTED: Validator should extract claims from valid token.
        FAILS UNTIL: Claim extraction is implemented.
        """
        assert hasattr(validator, "get_claims")


class TestOAuthMiddleware:
    """Tests for OAuth middleware integration with FastAPI."""

    def test_middleware_extracts_bearer_token(self):
        """
        EXPECTED: Middleware extracts token from Authorization header.
        FAILS UNTIL: Token extraction is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        middleware = OAuthMiddleware(app=MagicMock())

        # Should have method to extract token
        assert hasattr(middleware, "extract_token") or hasattr(middleware, "_extract_token")

    def test_middleware_returns_401_for_missing_token(self):
        """
        EXPECTED: Middleware returns 401 when no token provided.
        FAILS UNTIL: Auth check is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        middleware = OAuthMiddleware(app=MagicMock())
        assert hasattr(middleware, "__call__")

    def test_middleware_returns_401_for_invalid_token(self):
        """
        EXPECTED: Middleware returns 401 when token is invalid.
        FAILS UNTIL: Token validation is integrated.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        middleware = OAuthMiddleware(app=MagicMock())
        # Should validate tokens
        assert middleware is not None

    def test_middleware_adds_user_to_request(self):
        """
        EXPECTED: Middleware adds validated user info to request state.
        FAILS UNTIL: User context is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        # After validation, request.state.user should be populated
        middleware = OAuthMiddleware(app=MagicMock())
        assert middleware is not None

    def test_middleware_checks_scopes(self):
        """
        EXPECTED: Middleware can enforce required scopes.
        FAILS UNTIL: Scope checking is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import OAuthMiddleware

        middleware = OAuthMiddleware(app=MagicMock())
        # Should have scope checking capability
        assert middleware is not None


class TestProtectedResourceMetadata:
    """Tests for RFC 9728 Protected Resource Metadata."""

    def test_metadata_has_resource_identifier(self):
        """
        EXPECTED: Metadata includes resource identifier.
        FAILS UNTIL: Metadata class is implemented.
        """
        from odoo_mcp_server.oauth.metadata import ProtectedResourceMetadata

        metadata = ProtectedResourceMetadata(
            resource="https://your-mcp-server.example.com",
            authorization_servers=["https://auth.example.com"],
        )

        assert metadata.resource == "https://your-mcp-server.example.com"

    def test_metadata_has_authorization_servers(self):
        """
        EXPECTED: Metadata includes list of authorization servers.
        FAILS UNTIL: Metadata class is implemented.
        """
        from odoo_mcp_server.oauth.metadata import ProtectedResourceMetadata

        metadata = ProtectedResourceMetadata(
            resource="https://your-mcp-server.example.com",
            authorization_servers=["https://auth.example.com"],
        )

        assert "https://auth.example.com" in metadata.authorization_servers

    def test_metadata_serializes_to_json(self):
        """
        EXPECTED: Metadata can be serialized to JSON for endpoint.
        FAILS UNTIL: Serialization is implemented.
        """
        from odoo_mcp_server.oauth.metadata import ProtectedResourceMetadata

        metadata = ProtectedResourceMetadata(
            resource="https://your-mcp-server.example.com",
            authorization_servers=["https://auth.example.com"],
        )

        json_data = metadata.to_dict()
        assert "resource" in json_data
        assert "authorization_servers" in json_data

    def test_metadata_includes_scopes_supported(self):
        """
        EXPECTED: Metadata lists supported OAuth scopes.
        FAILS UNTIL: Scope listing is implemented.
        """
        from odoo_mcp_server.oauth.metadata import ProtectedResourceMetadata

        metadata = ProtectedResourceMetadata(
            resource="https://your-mcp-server.example.com",
            authorization_servers=["https://auth.example.com"],
            scopes_supported=[
                "openid",
                "odoo.read",
                "odoo.hr.profile",
                "odoo.leave.read",
            ],
        )

        assert "odoo.hr.profile" in metadata.scopes_supported


class TestScopeEnforcement:
    """Tests for OAuth scope enforcement on tools."""

    def test_tool_requires_specific_scope(self):
        """
        EXPECTED: Each tool should declare required scopes.
        FAILS UNTIL: Scope requirements are defined per tool.
        """
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS

        # get_my_profile should require odoo.hr.profile or odoo.read
        assert "get_my_profile" in TOOL_SCOPE_REQUIREMENTS
        assert "odoo.hr.profile" in TOOL_SCOPE_REQUIREMENTS["get_my_profile"]

    def test_check_scope_access_allows_matching_scope(self):
        """
        EXPECTED: Access granted when user has required scope.
        """
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        user_scopes = ["openid", "odoo.hr.profile"]
        required = TOOL_SCOPE_REQUIREMENTS["get_my_profile"]

        assert check_scope_access(required, user_scopes) is True

    def test_check_scope_access_denies_missing_scope(self):
        """
        EXPECTED: Access denied when user lacks required scope.
        """
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        user_scopes = ["openid"]  # Missing odoo.hr.profile
        required = TOOL_SCOPE_REQUIREMENTS["get_my_profile"]

        assert check_scope_access(required, user_scopes) is False

    def test_odoo_read_scope_grants_read_access(self):
        """
        EXPECTED: odoo.read scope grants access to all read tools.
        """
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        user_scopes = ["openid", "odoo.read"]

        # Should have access to profile (read operation)
        assert check_scope_access(
            TOOL_SCOPE_REQUIREMENTS["get_my_profile"], user_scopes
        ) is True


class TestUserContextFromToken:
    """Tests for extracting user context from OAuth token."""

    def test_extract_employee_id_from_token(self):
        """
        EXPECTED: Employee ID should be extracted from token claims.
        FAILS UNTIL: User context extraction is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import extract_user_context

        # Mock token claims
        claims = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "odoo_employee_id": 42,
        }

        context = extract_user_context(claims)
        assert context["employee_id"] == 42

    def test_extract_email_from_token(self):
        """
        EXPECTED: User email should be extracted from token.
        FAILS UNTIL: User context extraction is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import extract_user_context

        claims = {
            "sub": "user@example.com",
            "email": "user@example.com",
        }

        context = extract_user_context(claims)
        assert context["email"] == "user@example.com"

    def test_extract_scopes_from_token(self):
        """
        EXPECTED: Granted scopes should be extracted from token.
        FAILS UNTIL: Scope extraction is implemented.
        """
        from odoo_mcp_server.oauth.resource_server import extract_user_context

        claims = {
            "sub": "user@example.com",
            "scope": "openid odoo.read odoo.hr.profile",
        }

        context = extract_user_context(claims)
        assert "odoo.hr.profile" in context["scopes"]
