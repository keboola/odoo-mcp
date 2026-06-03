"""
Odoo Record CRUD Tools

MCP tools for creating, reading, updating, and deleting Odoo records.
"""
import json
from typing import Any

from mcp.types import TextContent, Tool

from ..odoo.client import OdooClient

TOOLS = [
    Tool(
        name="search_records",
        description="Search for records in an Odoo model with filters",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name (e.g., 'res.partner')"
                },
                "domain": {
                    "type": "array",
                    "description": "Search domain filters",
                    "default": []
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to return"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum records to return",
                    "default": 20
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of records to skip",
                    "default": 0
                }
            },
            "required": ["model"]
        }
    ),
    Tool(
        name="get_record",
        description="Get a single record by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name"
                },
                "record_id": {
                    "type": "integer",
                    "description": "Record ID"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to return"
                }
            },
            "required": ["model", "record_id"]
        }
    ),
    Tool(
        name="create_record",
        description="Create a new record in Odoo",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name"
                },
                "values": {
                    "type": "object",
                    "description": "Field values for new record"
                }
            },
            "required": ["model", "values"]
        }
    ),
    Tool(
        name="update_record",
        description="Update an existing record",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name"
                },
                "record_id": {
                    "type": "integer",
                    "description": "Record ID to update"
                },
                "values": {
                    "type": "object",
                    "description": "Field values to update"
                }
            },
            "required": ["model", "record_id", "values"]
        }
    ),
    Tool(
        name="delete_record",
        description="Delete a record",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name"
                },
                "record_id": {
                    "type": "integer",
                    "description": "Record ID to delete"
                }
            },
            "required": ["model", "record_id"]
        }
    ),
    Tool(
        name="count_records",
        description="Count records matching criteria",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model name"
                },
                "domain": {
                    "type": "array",
                    "description": "Search domain filters",
                    "default": []
                }
            },
            "required": ["model"]
        }
    ),
    Tool(
        name="list_models",
        description="List available Odoo models",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    )
]


async def execute_tool(
    name: str,
    arguments: dict[str, Any],
    client: OdooClient
) -> list[TextContent]:
    """Execute a tool and return results"""

    if name == "search_records":
        records = await client.search_read(
            model=arguments["model"],
            domain=arguments.get("domain", []),
            fields=arguments.get("fields"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0)
        )
        return [TextContent(type="text", text=json.dumps(records, default=str))]

    elif name == "get_record":
        records = await client.read(
            model=arguments["model"],
            ids=[arguments["record_id"]],
            fields=arguments.get("fields")
        )
        if not records:
            return [TextContent(type="text", text=json.dumps({"error": "Record not found"}))]
        return [TextContent(type="text", text=json.dumps(records[0], default=str))]

    elif name == "create_record":
        record_id = await client.create(
            model=arguments["model"],
            values=arguments["values"]
        )
        return [TextContent(type="text", text=json.dumps({"id": record_id}))]

    elif name == "update_record":
        success = await client.write(
            model=arguments["model"],
            ids=[arguments["record_id"]],
            values=arguments["values"]
        )
        return [TextContent(type="text", text=json.dumps({"success": success}))]

    elif name == "delete_record":
        success = await client.unlink(
            model=arguments["model"],
            ids=[arguments["record_id"]]
        )
        return [TextContent(type="text", text=json.dumps({"success": success}))]

    elif name == "count_records":
        count = await client.search_count(
            model=arguments["model"],
            domain=arguments.get("domain", [])
        )
        return [TextContent(type="text", text=json.dumps({"count": count}))]

    elif name == "list_models":
        # Get accessible models
        models = await client.search_read(
            model="ir.model",
            domain=[["transient", "=", False]],
            fields=["model", "name"],
            limit=100
        )
        return [TextContent(type="text", text=json.dumps(models, default=str))]

    raise ValueError(f"Unknown tool: {name}")
