"""OAuth 2.1 Resource Server implementation."""

from .metadata import ProtectedResourceMetadata
from .resource_server import OAuthMiddleware, OAuthResourceServer, extract_user_context
from .token_validator import TokenValidator
from .user_mapping import EmployeeNotFoundError, get_employee_for_user

__all__ = [
    "OAuthResourceServer",
    "OAuthMiddleware",
    "TokenValidator",
    "ProtectedResourceMetadata",
    "extract_user_context",
    "get_employee_for_user",
    "EmployeeNotFoundError",
]
