#!/bin/bash
#
# Run MCP Inspector to visually test the Odoo MCP server
#
# Usage:
#   ./scripts/run_inspector.sh
#
# This opens a browser UI at http://localhost:6274 where you can:
#   - List all available tools
#   - Call tools with arguments
#   - See responses and debug issues
#
# No Claude login required!
#

set -e

cd "$(dirname "$0")/.."

# Ensure virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Load environment variables
if [ -f .env ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
fi

echo "=============================================="
echo "MCP Inspector - Odoo MCP Server Testing"
echo "=============================================="
echo ""
echo "Starting MCP Inspector..."
echo "Browser UI will open at: http://localhost:6274"
echo ""
echo "Available tools:"
echo "  - get_my_profile"
echo "  - get_my_manager"
echo "  - find_colleague"
echo "  - get_my_leave_balance"
echo "  - get_my_leave_requests"
echo "  - get_my_documents"
echo "  - get_document_categories"
echo ""

# Run MCP Inspector with our server
npx @modelcontextprotocol/inspector python -m odoo_mcp_server.server
