"""Odoo XML-RPC client and utilities."""

from .client import OdooClient
from .exceptions import (
    OdooAuthenticationError,
    OdooConnectionError,
    OdooError,
    OdooPermissionError,
    OdooRecordNotFoundError,
    OdooServerError,
    OdooTimeoutError,
    OdooValidationError,
    map_connection_error,
    map_odoo_fault,
)

__all__ = [
    "OdooClient",
    # Exceptions
    "OdooError",
    "OdooAuthenticationError",
    "OdooConnectionError",
    "OdooPermissionError",
    "OdooRecordNotFoundError",
    "OdooServerError",
    "OdooTimeoutError",
    "OdooValidationError",
    # Utilities
    "map_connection_error",
    "map_odoo_fault",
]
