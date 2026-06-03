"""
Odoo Error Handling

Maps Odoo XML-RPC faults to clean, MCP-friendly exceptions.
Provides standard error patterns for the MCP server.

Error Code Reference (Odoo XML-RPC):
- Fault 1: UserError / ValidationError
- Fault 2: MissingError (record not found)
- Fault 3: AccessDenied (authentication)
- Fault 4: AccessError (permission denied)
"""

import socket
from typing import Any
from xmlrpc.client import Fault  # nosec B411 - used for error handling with trusted Odoo server


class OdooError(Exception):
    """Base exception for all Odoo-related errors."""

    error_code: str = "ODOO_ERROR"
    is_retryable: bool = False

    def __init__(self, message: str, **kwargs: Any):
        super().__init__(message)
        self.message = message
        self.details = kwargs

    def to_mcp_response(self) -> dict:
        """Convert error to MCP-friendly JSON response."""
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message,
            }
        }
        # Add any additional details
        for key, value in self.details.items():
            response["error"][key] = value
        return response

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class OdooAuthenticationError(OdooError):
    """Authentication failed - invalid credentials or API key."""

    error_code = "ACCESS_DENIED"
    is_retryable = False


class OdooPermissionError(OdooError):
    """User lacks permission to access/modify the resource."""

    error_code = "PERMISSION_DENIED"
    is_retryable = False


class OdooRecordNotFoundError(OdooError):
    """Requested record does not exist."""

    error_code = "RECORD_NOT_FOUND"
    is_retryable = False


class OdooValidationError(OdooError):
    """Data validation failed (UserError, ValidationError)."""

    error_code = "VALIDATION_ERROR"
    is_retryable = False

    def __init__(self, message: str, field: str | None = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        if field:
            self.details["field"] = field


class OdooConnectionError(OdooError):
    """Network or connection error communicating with Odoo."""

    error_code = "CONNECTION_ERROR"
    is_retryable = True


class OdooTimeoutError(OdooConnectionError):
    """Request timed out."""

    error_code = "CONNECTION_TIMEOUT"
    is_retryable = True


class OdooServerError(OdooError):
    """Internal server error from Odoo."""

    error_code = "SERVER_ERROR"
    is_retryable = True


def map_odoo_fault(fault: Fault) -> OdooError:
    """
    Map XML-RPC Fault to appropriate OdooError subclass.

    Odoo fault codes:
    - 1: UserError, ValidationError
    - 2: MissingError
    - 3: AccessDenied
    - 4: AccessError

    Args:
        fault: XML-RPC Fault from Odoo

    Returns:
        Appropriate OdooError subclass
    """
    fault_code = fault.faultCode
    fault_string = fault.faultString

    # Extract meaningful message from fault string
    message = _extract_error_message(fault_string)

    # Map by fault code
    if fault_code == 3:
        return OdooAuthenticationError(message, original_fault=fault_string)

    if fault_code == 4 or "AccessError" in fault_string:
        return OdooPermissionError(message, original_fault=fault_string)

    if fault_code == 2 or "MissingError" in fault_string:
        return OdooRecordNotFoundError(message, original_fault=fault_string)

    if fault_code == 1 or "UserError" in fault_string or "ValidationError" in fault_string:
        return OdooValidationError(message, original_fault=fault_string)

    # Unknown fault - return generic error with details
    return OdooError(
        f"Odoo error (code {fault_code}): {message}",
        error_code="UNKNOWN_ERROR",
        fault_code=fault_code,
        original_fault=fault_string,
    )


def map_connection_error(error: Exception) -> OdooError:
    """
    Map connection/network errors to appropriate OdooError.

    Args:
        error: Original exception (socket.timeout, ConnectionError, etc.)

    Returns:
        Appropriate OdooError subclass
    """
    if isinstance(error, socket.timeout):
        return OdooTimeoutError(
            f"Connection timed out: {error}",
            original_error=str(error),
        )

    if isinstance(error, ConnectionRefusedError):
        return OdooConnectionError(
            "Connection refused - Odoo server may be down",
            original_error=str(error),
        )

    if isinstance(error, (ConnectionError, OSError)):
        return OdooConnectionError(
            f"Network error: {error}",
            original_error=str(error),
        )

    # Generic connection error
    return OdooConnectionError(
        f"Connection error: {error}",
        original_error=str(error),
    )


def _extract_error_message(fault_string: str) -> str:
    """
    Extract clean error message from Odoo fault string.

    Odoo fault strings often contain Python tracebacks and error class names.
    This extracts just the meaningful message.

    Args:
        fault_string: Raw fault string from XML-RPC

    Returns:
        Clean error message
    """
    # Handle common patterns

    # Pattern: "UserError: Message here"
    for prefix in ["UserError:", "ValidationError:", "MissingError:", "AccessError:", "AccessDenied:"]:
        if prefix in fault_string:
            parts = fault_string.split(prefix, 1)
            if len(parts) > 1:
                return parts[1].strip().split("\n")[0].strip()

    # Pattern: Just return first line if multiline
    first_line = fault_string.split("\n")[0].strip()

    # Remove common noise
    noise_prefixes = ["Traceback ", "File ", "  "]
    for prefix in noise_prefixes:
        if first_line.startswith(prefix):
            # Try to find actual error message later in string
            lines = fault_string.split("\n")
            for line in reversed(lines):
                line = line.strip()
                if line and not any(line.startswith(p) for p in noise_prefixes):
                    return line
            break

    return first_line or fault_string
