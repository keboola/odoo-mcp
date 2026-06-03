"""
OAuth User to Odoo Employee Mapping

Maps authenticated OAuth users to their Odoo employee records.
Uses multiple strategies to find the correct employee.

Performance: Includes in-memory caching to avoid repeated Odoo queries.
"""

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Employee cache: email -> (employee_info, expiry_timestamp)
_employee_cache: dict[str, tuple[dict, float]] = {}
_EMPLOYEE_CACHE_TTL = 300  # 5 minutes


def _get_cached_employee(email: str) -> dict | None:
    """Get cached employee info if still valid."""
    email_lower = email.lower()
    if email_lower in _employee_cache:
        employee_info, expiry = _employee_cache[email_lower]
        if time.time() < expiry:
            logger.debug(f"Employee cache hit for {email_lower}")
            return employee_info
        else:
            del _employee_cache[email_lower]
    return None


def _cache_employee(email: str, employee_info: dict):
    """Cache employee info."""
    email_lower = email.lower()
    expiry = time.time() + _EMPLOYEE_CACHE_TTL
    _employee_cache[email_lower] = (employee_info, expiry)
    logger.debug(f"Cached employee info for {email_lower}")


class EmployeeNotFoundError(Exception):
    """Raised when no employee record matches the OAuth user."""
    pass


class MultipleEmployeesFoundError(Exception):
    """Raised when multiple employee records match the OAuth user."""
    pass


async def get_employee_for_user(
    oauth_claims: dict[str, Any],
    odoo_client: Any,
) -> dict[str, Any]:
    """
    Map OAuth user to Odoo employee.

    Tries multiple strategies in order, with parallel execution where possible:
    1. Match by odoo_employee_id claim (if present)
    2. Parallel search:
       - Match by work_email in hr.employee
       - Match via res.users login (which links to hr.employee)
    3. Fuzzy match on name (last resort)

    Performance: Uses caching and parallel Odoo queries.

    Args:
        oauth_claims: Decoded JWT claims from OAuth token
        odoo_client: Odoo client instance

    Returns:
        Dict with employee info: {id, name, email, department_id}

    Raises:
        EmployeeNotFoundError: If no employee matches
    """
    user_email = oauth_claims.get("email") or oauth_claims.get("sub")
    odoo_employee_id = oauth_claims.get("odoo_employee_id")

    # Check cache first (by email)
    if user_email:
        cached = _get_cached_employee(user_email)
        if cached is not None:
            logger.info(f"Using cached employee mapping for {user_email}")
            return cached

    logger.info(f"Mapping OAuth user to employee: email={user_email}")

    # Strategy 0: If token contains employee ID directly (trusted claim)
    if odoo_employee_id:
        employees = await odoo_client.search_read(
            model="hr.employee",
            domain=[["id", "=", odoo_employee_id]],
            fields=["id", "name", "work_email", "department_id"],
            limit=1,
        )
        if employees:
            logger.info(f"Found employee by token claim: {employees[0]['name']}")
            result = _normalize_employee(employees[0])
            if user_email:
                _cache_employee(user_email, result)
            return result

    if not user_email:
        raise EmployeeNotFoundError("No email in OAuth token to map to employee")

    # Prepare parallel tasks for Strategy 1 and 2
    task_email = odoo_client.search_read(
        model="hr.employee",
        domain=[["work_email", "=ilike", user_email]],
        fields=["id", "name", "work_email", "department_id"],
        limit=2,
    )

    task_user = odoo_client.search_read(
        model="res.users",
        domain=[["login", "=ilike", user_email]],
        fields=["id", "employee_id", "employee_ids"],
        limit=1,
    )

    # Execute parallel searches
    results_email, results_user = await asyncio.gather(task_email, task_user)

    # Strategy 1: Match by work_email in hr.employee
    if len(results_email) > 1:
        logger.warning(f"Multiple employees found for email {user_email}")
        # Use first one but log warning
        result = _normalize_employee(results_email[0])
        _cache_employee(user_email, result)
        return result

    if results_email:
        logger.info(f"Found employee by work_email: {results_email[0]['name']}")
        result = _normalize_employee(results_email[0])
        _cache_employee(user_email, result)
        return result

    # Strategy 2: Match via res.users (login -> employee_id)
    if results_user:
        user = results_user[0]
        emp_id = None

        # Check employee_id (single linked employee)
        if user.get("employee_id"):
            emp_id = user["employee_id"][0]
        # Check employee_ids (multiple linked employees - rare)
        elif user.get("employee_ids") and len(user["employee_ids"]) > 0:
            emp_id = user["employee_ids"][0]

        if emp_id:
            employees = await odoo_client.read(
                model="hr.employee",
                ids=[emp_id],
                fields=["id", "name", "work_email", "department_id"],
            )
            if employees:
                logger.info(f"Found employee via res.users: {employees[0]['name']}")
                result = _normalize_employee(employees[0])
                _cache_employee(user_email, result)
                return result

    # Strategy 3: Fuzzy match on name if email has name part (last resort)
    # e.g., "john.doe@company.com" -> search for "john doe"
    email_name = user_email.split("@")[0].replace(".", " ").replace("_", " ")
    if len(email_name) > 3:
        employees = await odoo_client.search_read(
            model="hr.employee",
            domain=[["name", "ilike", email_name]],
            fields=["id", "name", "work_email", "department_id"],
            limit=1,
        )
        if employees:
            emp_name = employees[0]["name"]
            logger.warning(
                f"Found employee by fuzzy name match: {emp_name} for {user_email}"
            )
            result = _normalize_employee(employees[0])
            _cache_employee(user_email, result)
            return result

    raise EmployeeNotFoundError(f"No employee found for email: {user_email}")


def _normalize_employee(employee: dict) -> dict:
    """Normalize employee record to standard format."""
    dept = employee.get("department_id")
    return {
        "id": employee["id"],
        "name": employee.get("name"),
        "email": employee.get("work_email"),
        "department_id": dept[0] if dept else None,
        "department_name": dept[1] if dept else None,
    }


async def validate_employee_access(
    employee_id: int,
    odoo_client: Any,
) -> bool:
    """
    Validate that an employee ID exists and is active.

    Args:
        employee_id: Employee ID to validate
        odoo_client: Odoo client instance

    Returns:
        True if employee exists and is active
    """
    employees = await odoo_client.search_read(
        model="hr.employee",
        domain=[["id", "=", employee_id], ["active", "=", True]],
        fields=["id"],
        limit=1,
    )
    return len(employees) > 0
