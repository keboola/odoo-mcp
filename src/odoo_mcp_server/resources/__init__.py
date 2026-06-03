"""MCP resources for Odoo data."""

__all__ = ["register_resources", "read_resource"]


def register_resources():
    """Return list of available resources."""
    from mcp.types import Resource

    return [
        Resource(
            uri="odoo://models",
            name="Odoo Models",
            description="List of available Odoo models",
            mimeType="application/json",
        ),
    ]


async def read_resource(uri: str, client) -> str:
    """Read a resource by URI."""
    import json

    if uri == "odoo://models":
        models = await client.search_read(
            model="ir.model",
            domain=[["transient", "=", False]],
            fields=["model", "name"],
            limit=100,
        )
        return json.dumps(models, default=str)

    raise ValueError(f"Unknown resource: {uri}")
