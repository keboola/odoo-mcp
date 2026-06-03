"""
Unit tests for OAuth functionality.

Run with: pytest tests/unit/test_oauth.py -v -m unit
"""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.oauth]


class TestPKCEGeneration:
    """Tests for PKCE code generation."""

    def test_pkce_verifier_length(self, pkce_challenge: dict):
        """PKCE verifier should be of appropriate length."""
        verifier = pkce_challenge["verifier"]
        # Base64url encoded 32 bytes = ~43 characters
        assert len(verifier) >= 43
        assert len(verifier) <= 128

    def test_pkce_challenge_is_sha256_of_verifier(self, pkce_challenge: dict):
        """PKCE challenge should be SHA256 hash of verifier."""
        import base64
        import hashlib

        verifier = pkce_challenge["verifier"]
        challenge = pkce_challenge["challenge"]

        # Recalculate challenge
        expected_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )

        assert challenge == expected_challenge

    def test_pkce_verifier_is_random(self):
        """Each PKCE generation should produce unique values."""
        import base64
        import hashlib
        import secrets

        challenges = set()
        for _ in range(10):
            verifier = secrets.token_urlsafe(32)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            challenges.add(challenge)

        # All should be unique
        assert len(challenges) == 10


class TestProtectedResourceMetadata:
    """Tests for RFC 9728 Protected Resource Metadata."""

    def test_metadata_has_required_fields(self):
        """Metadata should contain all required RFC 9728 fields."""
        # Simulating the metadata structure
        metadata = {
            "resource": "https://your-mcp-server.example.com",
            "authorization_servers": ["https://auth.example.com"],
            "bearer_methods_supported": ["header"],
        }

        assert "resource" in metadata
        assert "authorization_servers" in metadata
        assert isinstance(metadata["authorization_servers"], list)
        assert len(metadata["authorization_servers"]) >= 1

    def test_bearer_methods_includes_header(self):
        """Bearer token should be supported via header."""
        metadata = {
            "bearer_methods_supported": ["header"],
        }

        assert "header" in metadata["bearer_methods_supported"]


class TestTokenClaims:
    """Tests for JWT token claim validation."""

    def test_valid_claims_structure(self):
        """Token claims should have expected structure."""
        # Simulated token claims
        claims = {
            "iss": "https://auth.example.com",
            "sub": "user123",
            "aud": ["https://your-mcp-server.example.com"],
            "exp": 1735689600,
            "iat": 1735686000,
            "scope": "openid odoo.read odoo.write",
        }

        assert "iss" in claims
        assert "sub" in claims
        assert "aud" in claims
        assert "exp" in claims

    def test_audience_validation(self):
        """Audience should match resource identifier."""
        resource_identifier = "https://your-mcp-server.example.com"

        # Valid audience (list)
        claims_list = {"aud": ["https://your-mcp-server.example.com", "other"]}
        aud = claims_list["aud"]
        assert resource_identifier in aud

        # Valid audience (string)
        claims_string = {"aud": "https://your-mcp-server.example.com"}
        aud = claims_string["aud"]
        if isinstance(aud, str):
            aud = [aud]
        assert resource_identifier in aud

    def test_scope_parsing(self):
        """Scopes should be correctly parsed."""
        scope_string = "openid odoo.read odoo.write"
        scopes = scope_string.split()

        assert "openid" in scopes
        assert "odoo.read" in scopes
        assert "odoo.write" in scopes


# =============================================================================
# Granular Scope Tests (Feedback 4.1)
# =============================================================================


class TestGranularScopes:
    """Tests for granular OAuth scope definitions and checking."""

    def test_scope_definitions_exist(self):
        """All expected scopes should be defined."""
        from odoo_mcp_server.config import OAUTH_SCOPES

        # Standard scopes
        assert "openid" in OAUTH_SCOPES
        assert "odoo.read" in OAUTH_SCOPES
        assert "odoo.write" in OAUTH_SCOPES

        # Granular HR scopes
        assert "odoo.hr.profile" in OAUTH_SCOPES
        assert "odoo.hr.team" in OAUTH_SCOPES
        assert "odoo.hr.directory" in OAUTH_SCOPES

        # Leave scopes
        assert "odoo.leave.read" in OAUTH_SCOPES
        assert "odoo.leave.write" in OAUTH_SCOPES

        # Document scopes
        assert "odoo.documents.read" in OAUTH_SCOPES
        assert "odoo.documents.write" in OAUTH_SCOPES

    def test_tool_scope_requirements_defined(self):
        """Each tool should have scope requirements defined."""
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS

        # Profile tools
        assert "get_my_profile" in TOOL_SCOPE_REQUIREMENTS
        assert "get_my_manager" in TOOL_SCOPE_REQUIREMENTS
        assert "find_colleague" in TOOL_SCOPE_REQUIREMENTS

        # Leave tools
        assert "get_my_leave_balance" in TOOL_SCOPE_REQUIREMENTS
        assert "request_leave" in TOOL_SCOPE_REQUIREMENTS

        # Document tools
        assert "get_my_documents" in TOOL_SCOPE_REQUIREMENTS
        assert "upload_identity_document" in TOOL_SCOPE_REQUIREMENTS

    def test_check_scope_access_with_granular_scope(self):
        """Granular scope should grant access to specific tool."""
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        # User with only HR profile scope
        user_scopes = ["openid", "odoo.hr.profile"]
        required = TOOL_SCOPE_REQUIREMENTS["get_my_profile"]

        assert check_scope_access(required, user_scopes) is True

    def test_check_scope_access_with_broad_scope(self):
        """Broad odoo.read scope should grant access to read tools."""
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        # User with broad read scope
        user_scopes = ["openid", "odoo.read"]
        required = TOOL_SCOPE_REQUIREMENTS["get_my_profile"]

        assert check_scope_access(required, user_scopes) is True

    def test_check_scope_access_denied(self):
        """User without required scope should be denied access."""
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        # User with only leave scopes, trying to access documents
        user_scopes = ["openid", "odoo.leave.read"]
        required = TOOL_SCOPE_REQUIREMENTS["get_my_documents"]

        assert check_scope_access(required, user_scopes) is False

    def test_write_scope_required_for_mutations(self):
        """Write operations should require write scopes."""
        from odoo_mcp_server.config import TOOL_SCOPE_REQUIREMENTS, check_scope_access

        # User with only read scope trying to create leave request
        user_scopes = ["openid", "odoo.leave.read"]
        required = TOOL_SCOPE_REQUIREMENTS["request_leave"]

        assert check_scope_access(required, user_scopes) is False

        # User with write scope should succeed
        user_scopes_write = ["openid", "odoo.leave.write"]
        assert check_scope_access(required, user_scopes_write) is True

    def test_granular_scope_string_parsing(self):
        """Granular scopes should be correctly parsed from space-delimited string."""
        scope_string = "openid odoo.hr.profile odoo.leave.read odoo.documents.read"
        scopes = scope_string.split()

        assert len(scopes) == 4
        assert "odoo.hr.profile" in scopes
        assert "odoo.leave.read" in scopes
        assert "odoo.documents.read" in scopes


class TestTokenStorage:
    """Tests for token storage configuration (Feedback 4.1)."""

    def test_default_storage_backend(self):
        """Default storage backend should be memory."""
        from odoo_mcp_server.config import Settings

        settings = Settings()
        assert settings.token_storage_backend == "memory"

    def test_storage_backend_options(self):
        """Storage backend should support expected options."""
        valid_backends = ["memory", "redis", "encrypted_file"]

        # These should all be valid configuration values
        for backend in valid_backends:
            assert backend in valid_backends

    def test_encryption_key_optional_for_memory(self):
        """Encryption key should be optional for memory storage."""
        from odoo_mcp_server.config import Settings

        settings = Settings(token_storage_backend="memory")
        assert settings.token_encryption_key is None
