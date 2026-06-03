#!/bin/bash
#
# Odoo MCP Server - E2E Test Runner
# Uses Claude Code Chrome integration for browser automation
#
# Prerequisites:
#   - Claude Code CLI v2.0.73+ (run: claude --version)
#   - Claude in Chrome extension v1.0.36+
#   - Google Chrome browser
#   - Claude Pro/Team/Enterprise plan
#   - MCP server running
#
# Usage:
#   ./scripts/run_e2e_tests.sh              # Run all tests
#   ./scripts/run_e2e_tests.sh --scenario auth  # Run specific scenario
#
# Environment Variables:
#   TEST_MCP_SERVER_URL  - MCP server URL (default: http://localhost:8080)
#   TEST_MCP_SERVER_NAME - Integration name (default: Odoo MCP Test)
#

set -e

# Configuration
MCP_SERVER_URL="${TEST_MCP_SERVER_URL:-http://localhost:8080}"
MCP_SERVER_NAME="${TEST_MCP_SERVER_NAME:-Odoo MCP Test}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SCENARIOS_FILE="$PROJECT_DIR/tests/e2e/scenarios.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Odoo MCP Server - E2E Test Runner                     ║${NC}"
echo -e "${BLUE}║        Using Claude Code Chrome Integration                  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "MCP Server URL:  ${GREEN}$MCP_SERVER_URL${NC}"
echo -e "Integration Name: ${GREEN}$MCP_SERVER_NAME${NC}"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check Claude Code version
    if ! command -v claude &> /dev/null; then
        echo -e "${RED}Error: Claude Code CLI not found${NC}"
        echo "Install: https://claude.ai/download"
        exit 1
    fi

    CLAUDE_VERSION=$(claude --version 2>/dev/null | head -1 || echo "unknown")
    echo -e "  Claude Code: ${GREEN}$CLAUDE_VERSION${NC}"

    # Check if MCP server is running
    if curl -s "$MCP_SERVER_URL/health" > /dev/null 2>&1; then
        echo -e "  MCP Server:  ${GREEN}Running at $MCP_SERVER_URL${NC}"
    else
        echo -e "  MCP Server:  ${RED}Not running at $MCP_SERVER_URL${NC}"
        echo ""
        echo -e "${YELLOW}Start the MCP server first:${NC}"
        echo "  python -m odoo_mcp_server.http_server"
        exit 1
    fi

    echo ""
}

# Print test scenarios
print_scenarios() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                     TEST SCENARIOS                            ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""

    cat << EOF
${YELLOW}1. AUTHENTICATION TEST${NC}
   Prompt: "Navigate to claude.ai and verify I'm logged in (not on login page)"
   Expected: Page shows chat interface, not login form

${YELLOW}2. ADD MCP SERVER${NC}
   Prompt: "Go to claude.ai/settings/integrations, click 'Add Custom Integration',
            fill name '$MCP_SERVER_NAME' and URL '$MCP_SERVER_URL', submit the form"
   Expected: Integration appears in list

${YELLOW}3. CONNECT MCP SERVER (OAuth)${NC}
   Prompt: "On integrations page, find '$MCP_SERVER_NAME' and click Connect.
            If OAuth appears, complete Google sign-in"
   Expected: Integration shows as Connected

${YELLOW}4. TEST: Search Employees${NC}
   Prompt: "Go to claude.ai/new, send 'Use Odoo integration to search employees'.
            Verify tool is invoked and returns employee data"
   Expected: Tool called, employee data returned

${YELLOW}5. TEST: Get Employee Profile${NC}
   Prompt: "In a new chat, send 'Get my employee profile from Odoo'.
            Verify profile data is returned"
   Expected: Profile with name, email, department shown

${YELLOW}6. TEST: Search Holidays${NC}
   Prompt: "Send 'Show upcoming holidays from Odoo for next month'.
            Verify holiday data is returned"
   Expected: Holiday/leave information displayed

${YELLOW}7. CLEANUP: Remove MCP Server${NC}
   Prompt: "Go to claude.ai/settings/integrations, find '$MCP_SERVER_NAME',
            click Remove and confirm deletion"
   Expected: Integration removed from list

EOF
}

# Run tests with Claude Code
run_tests() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                   STARTING TEST SESSION                       ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Instructions:${NC}"
    echo "  1. Claude Code will start with Chrome integration enabled"
    echo "  2. Run /chrome to verify browser connection"
    echo "  3. Execute each test scenario by copying the prompts above"
    echo "  4. Report results for each test"
    echo ""
    echo -e "${GREEN}Starting Claude Code with Chrome...${NC}"
    echo ""

    # Start Claude Code with Chrome and initial prompt
    exec claude --chrome -p "
You are running E2E tests for the Odoo MCP Server integration with Claude.ai.

MCP Server URL: $MCP_SERVER_URL
Integration Name: $MCP_SERVER_NAME

Please run the following test scenarios in order:

1. Navigate to claude.ai and verify you're logged in
2. Go to settings/integrations and add a new custom integration with name '$MCP_SERVER_NAME' and URL '$MCP_SERVER_URL'
3. Connect the integration (complete OAuth if needed)
4. Test the search_employee tool by asking to search for employees
5. Test getting employee profile
6. Test searching for holidays
7. Clean up by removing the integration

Report PASS or FAIL for each test with a brief explanation.
"
}

# Main
main() {
    check_prerequisites
    print_scenarios

    echo ""
    echo -e "${YELLOW}Press Enter to start the test session, or Ctrl+C to cancel...${NC}"
    read -r

    run_tests
}

# Handle arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [--scenario <id>]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help"
        echo "  --scenarios    Print test scenarios only"
        echo ""
        echo "Environment Variables:"
        echo "  TEST_MCP_SERVER_URL   MCP server URL (default: http://localhost:8080)"
        echo "  TEST_MCP_SERVER_NAME  Integration name (default: Odoo MCP Test)"
        exit 0
        ;;
    --scenarios)
        print_scenarios
        exit 0
        ;;
    *)
        main
        ;;
esac
