"""
JWT Token Validator for OAuth 2.1 Resource Server

Validates access tokens issued by the authorization server.

Performance optimizations:
- Global PyJWKClient singleton with built-in caching
- Token validation result cache (TTL-based)
- Async HTTP client with connection reuse
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import cachetools  # type: ignore[import-untyped]
import httpx

logger = logging.getLogger(__name__)

# Global caches for performance
_jwks_clients: cachetools.LRUCache = cachetools.LRUCache(maxsize=10)  # uri -> PyJWKClient
_token_cache: cachetools.TTLCache = cachetools.TTLCache(maxsize=10000, ttl=300)  # token_hash -> claims
_httpx_client: httpx.AsyncClient | None = None


def _get_token_hash(token: str) -> str:
    """Hash token for cache key (avoid storing raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def _get_cached_claims(token: str) -> dict | None:
    """Get cached token claims if still valid. TTLCache handles expiry automatically."""
    token_hash = _get_token_hash(token)
    claims = _token_cache.get(token_hash)
    if claims is not None:
        logger.debug(f"Token cache hit for hash {token_hash[:8]}...")
    return claims


def _cache_claims(token: str, claims: dict):
    """Cache validated token claims. TTLCache handles expiry and eviction automatically."""
    token_hash = _get_token_hash(token)
    _token_cache[token_hash] = claims
    logger.debug(f"Cached token claims for hash {token_hash[:8]}...")


class TokenValidationError(Exception):
    """Base exception for token validation errors."""
    pass


class TokenExpiredError(TokenValidationError):
    """Token has expired."""
    pass


class InvalidTokenError(TokenValidationError):
    """Token is invalid (bad signature, format, etc.)."""
    pass


class InvalidIssuerError(TokenValidationError):
    """Token issuer doesn't match expected issuer."""
    pass


class InvalidAudienceError(TokenValidationError):
    """Token audience doesn't match expected audience."""
    pass


@dataclass
class TokenValidator:
    """
    Validates JWT access tokens using JWKS from authorization server.

    Supports:
    - RS256, RS384, RS512 (RSA)
    - ES256, ES384, ES512 (ECDSA)
    - Google OAuth (ID tokens with client_id as audience)
    """

    issuer: str
    audience: str
    jwks_uri: str | None = None
    jwks: dict = field(default_factory=dict)
    _jwks_cache_time: float = field(default=0.0, repr=False)
    _jwks_cache_ttl: int = 3600  # 1 hour
    # Google OAuth specific
    is_google: bool = False
    authorized_party: str | None = None  # For Google: must match client_id

    def __post_init__(self):
        """Initialize JWKS URI from issuer if not provided."""
        if not self.jwks_uri:
            # Google uses a different JWKS endpoint
            if self.issuer == "https://accounts.google.com":
                self.jwks_uri = "https://www.googleapis.com/oauth2/v3/certs"
                self.is_google = True
            else:
                self.jwks_uri = f"{self.issuer.rstrip('/')}/.well-known/jwks.json"

    async def fetch_jwks(self) -> dict:
        """
        Fetch JWKS from authorization server.

        Caches the JWKS for _jwks_cache_ttl seconds.
        """
        now = time.time()
        if self.jwks and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self.jwks

        if not self.jwks_uri:
            raise TokenValidationError("JWKS URI not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_uri)
            response.raise_for_status()
            self.jwks = response.json()
            self._jwks_cache_time = now

        return self.jwks

    def validate(self, token: str) -> dict[str, Any]:
        """
        Validate a token synchronously.

        For Google OAuth, handles both:
        - JWT id_tokens (3 parts separated by dots)
        - Opaque access_tokens (validated via Google's tokeninfo endpoint)

        Performance: Uses cached results when available.

        Args:
            token: Token string (JWT or opaque)

        Returns:
            Token claims if valid

        Raises:
            TokenValidationError: If token is invalid
        """
        # Check cache first
        cached = _get_cached_claims(token)
        if cached is not None:
            return cached

        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError:
            raise TokenValidationError(
                "PyJWT library required for token validation"
            )

        # Check if this is a JWT (3 parts) or opaque token
        parts = token.split(".")
        if len(parts) != 3:
            # Not a JWT - for Google, validate via tokeninfo endpoint
            if self.is_google:
                claims = self._validate_google_access_token(token)
                _cache_claims(token, claims)
                return claims
            raise InvalidTokenError("Invalid JWT format")

        try:
            # Ensure JWKS URI is configured
            if not self.jwks_uri:
                raise TokenValidationError("JWKS URI not configured")

            # Get or create cached PyJWKClient for this JWKS URI
            global _jwks_clients
            if self.jwks_uri not in _jwks_clients:
                _jwks_clients[self.jwks_uri] = PyJWKClient(
                    self.jwks_uri,
                    cache_keys=True,
                    lifespan=3600  # Cache keys for 1 hour
                )
            jwks_client = _jwks_clients[self.jwks_uri]
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Google ID tokens use client_id as audience
            if self.is_google:
                # For Google: audience is the client_id
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    issuer=self.issuer,
                    audience=self.audience,  # This is the Google client_id
                    options={
                        "require": ["exp", "iss", "aud", "email"],
                        "verify_exp": True,
                        "verify_iss": True,
                        "verify_aud": True,
                    }
                )

                # Additional Google-specific checks
                # Verify azp (authorized party) if provided
                if self.authorized_party and claims.get("azp"):
                    if claims["azp"] != self.authorized_party:
                        raise InvalidTokenError(
                            f"Invalid authorized party: {claims['azp']}"
                        )

                # Google tokens should have email_verified
                if not claims.get("email_verified", False):
                    email = claims.get("email")
                    logger.warning(f"Google token email not verified: {email}")

                _cache_claims(token, claims)
                return claims
            else:
                # Standard OAuth 2.0 token validation
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                    issuer=self.issuer,
                    audience=self.audience,
                    options={
                        "require": ["exp", "iss", "aud"],
                        "verify_exp": True,
                        "verify_iss": True,
                        "verify_aud": True,
                    }
                )

                _cache_claims(token, claims)
                return claims

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidIssuerError:
            logger.warning("JWT invalid issuer, expected %s", self.issuer)
            raise InvalidIssuerError(f"Invalid issuer, expected {self.issuer}")
        except jwt.InvalidAudienceError:
            logger.warning("JWT invalid audience, expected %s", self.audience)
            raise InvalidAudienceError(f"Invalid audience, expected {self.audience}")
        except jwt.InvalidTokenError as e:
            logger.warning("JWT invalid token: %s", e)
            raise InvalidTokenError(f"Invalid token: {e}")
        except Exception as e:
            logger.error("JWT validation unexpected error: %s: %s", type(e).__name__, e)
            raise TokenValidationError(f"Token validation failed: {e}")

    def _validate_google_access_token(self, token: str) -> dict[str, Any]:
        """
        Validate a Google opaque access token using tokeninfo endpoint (sync).

        Google access tokens are not JWTs, so we validate them by calling
        Google's tokeninfo endpoint which returns user info if valid.

        Note: Prefer using _validate_google_access_token_async for better performance.

        Args:
            token: Google access token (opaque string)

        Returns:
            Token claims including email, sub, etc.

        Raises:
            TokenValidationError: If token is invalid
        """
        import httpx

        try:
            # Call Google's tokeninfo endpoint with connection reuse
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    "https://www.googleapis.com/oauth2/v3/tokeninfo",
                    params={"access_token": token},
                )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                err_msg = error_data.get("error_description", "Unknown error")
                raise InvalidTokenError(f"Google token validation failed: {err_msg}")

            claims = response.json()

            # Verify audience matches our client_id
            token_aud = claims.get("aud") or claims.get("azp")
            if token_aud != self.audience:
                raise InvalidAudienceError(
                    f"Invalid audience: expected {self.audience}, got {token_aud}"
                )

            # Check expiration
            exp = claims.get("expires_in")
            if exp is not None and int(exp) <= 0:
                raise TokenExpiredError("Token has expired")

            # Normalize claims to match JWT format
            normalized = {
                "sub": claims.get("sub"),
                "email": claims.get("email"),
                "email_verified": claims.get("email_verified") == "true",
                "aud": token_aud,
                "iss": "https://accounts.google.com",
                "scope": claims.get("scope", ""),
            }

            logger.info(f"Google access token validated for: {normalized.get('email')}")
            return normalized

        except httpx.RequestError as e:
            raise TokenValidationError(f"Failed to validate token with Google: {e}")

    async def _validate_google_access_token_async(self, token: str) -> dict[str, Any]:
        """
        Validate a Google opaque access token using tokeninfo endpoint (async).

        Uses a shared AsyncClient for connection reuse and better performance.

        Args:
            token: Google access token (opaque string)

        Returns:
            Token claims including email, sub, etc.

        Raises:
            TokenValidationError: If token is invalid
        """
        global _httpx_client

        try:
            # Get or create shared async client
            if _httpx_client is None:
                _httpx_client = httpx.AsyncClient(timeout=5.0)

            response = await _httpx_client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": token},
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                err_msg = error_data.get("error_description", "Unknown error")
                logger.error(
                    "Google tokeninfo FAILED: status=%s error=%s",
                    response.status_code, err_msg,
                )
                raise InvalidTokenError(f"Google token validation failed: {err_msg}")

            claims = response.json()
            logger.info(
                "Google tokeninfo OK: email=%s aud=%s expires_in=%s",
                claims.get("email", "?"), claims.get("aud", "?")[:20], claims.get("expires_in", "?"),
            )

            # Verify audience matches our client_id
            token_aud = claims.get("aud") or claims.get("azp")
            if token_aud != self.audience:
                logger.error(
                    "Audience mismatch: expected=%s got=%s",
                    self.audience, token_aud,
                )
                raise InvalidAudienceError(
                    f"Invalid audience: expected {self.audience}, got {token_aud}"
                )

            # Check expiration
            exp = claims.get("expires_in")
            if exp is not None and int(exp) <= 0:
                raise TokenExpiredError("Token has expired")

            # Normalize claims to match JWT format
            normalized = {
                "sub": claims.get("sub"),
                "email": claims.get("email"),
                "email_verified": claims.get("email_verified") == "true",
                "aud": token_aud,
                "iss": "https://accounts.google.com",
                "scope": claims.get("scope", ""),
            }

            email = normalized.get("email")
            logger.info(f"Google access token validated (async) for: {email}")
            return normalized

        except httpx.RequestError as e:
            logger.error("Google tokeninfo request error: %s", e)
            raise TokenValidationError(f"Failed to validate token with Google: {e}")

    async def validate_async(self, token: str) -> dict[str, Any]:
        """
        Validate a token asynchronously.

        Performance: Uses caching and async HTTP client for Google tokens.
        """
        # Check cache first
        cached = _get_cached_claims(token)
        if cached is not None:
            return cached

        token_hash = _get_token_hash(token)

        # Check if this is an opaque Google access token (not JWT)
        parts = token.split(".")
        logger.info(
            "Token validation: parts=%d is_google=%s audience=%s hash=%s",
            len(parts), self.is_google, self.audience[:20] if self.audience else "none", token_hash[:8],
        )

        if len(parts) != 3 and self.is_google:
            claims = await self._validate_google_access_token_async(token)
            _cache_claims(token, claims)
            return claims

        # For JWT tokens, use sync validation (PyJWT is sync)
        # The cache check above ensures we don't repeat validation
        # Offload CPU-bound validation to executor to avoid blocking event loop
        import asyncio
        from functools import partial

        await self.fetch_jwks()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(self.validate, token))

    def get_claims(self, token: str) -> dict[str, Any]:
        """
        Extract claims from token without full validation.

        WARNING: Only use this for debugging/logging.
        Always use validate() for actual token verification.
        """
        try:
            import jwt
            # Decode without verification
            claims = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            return claims
        except Exception as e:
            raise InvalidTokenError(f"Cannot decode token: {e}")
