"""MCP tools for Odoo operations."""

from .employee import EMPLOYEE_TOOLS, execute_employee_tool
from .records import TOOLS as CRUD_TOOLS
from .records import execute_tool as execute_crud_tool
from .sign import SIGN_TOOLS, execute_sign_tool

__all__ = [
    "CRUD_TOOLS",
    "EMPLOYEE_TOOLS",
    "SIGN_TOOLS",
    "execute_crud_tool",
    "execute_employee_tool",
    "execute_sign_tool",
    "register_tools",
    "register_employee_tools",
    "execute_tool",
]


def register_tools(include_sign: bool = True):
    """Return list of all available tools.

    Sign tools require the optional OCA `sign_oca` addon and are only included
    when ``include_sign`` is True (driven by SIGN_MODULE_ENABLED).
    """
    tools = CRUD_TOOLS + EMPLOYEE_TOOLS
    if include_sign:
        tools = tools + SIGN_TOOLS
    return tools


def register_employee_tools(include_sign: bool = True):
    """Return list of employee self-service tools."""
    tools = list(EMPLOYEE_TOOLS)
    if include_sign:
        tools = tools + SIGN_TOOLS
    return tools


async def execute_tool(name: str, arguments: dict, odoo_client):  # type: ignore[type-arg]
    """
    Execute a tool by name (CRUD tools only).

    Employee tools require employee context and should be called via
    execute_employee_tool directly with the employee_id parameter.
    """
    # Employee tools require employee context - raise error
    employee_tool_names = [t.name for t in EMPLOYEE_TOOLS]
    if name in employee_tool_names:
        raise ValueError(f"Employee tool '{name}' requires employee context. Use execute_employee_tool instead.")

    # Sign tools require employee context - raise error
    sign_tool_names = [t.name for t in SIGN_TOOLS]
    if name in sign_tool_names:
        raise ValueError(f"Sign tool '{name}' requires employee context. Use execute_sign_tool instead.")

    # Execute CRUD tools
    crud_tool_names = [t.name for t in CRUD_TOOLS]
    if name in crud_tool_names:
        return await execute_crud_tool(name, arguments, odoo_client)

    raise ValueError(f"Unknown tool: {name}")
