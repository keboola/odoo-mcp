# E2E Testing with Claude Code Chrome Integration

This directory contains end-to-end test scenarios for testing the Odoo MCP server integration with Claude.ai.

## Overview

E2E tests use **Claude Code's Chrome integration** (`/chrome` command) instead of traditional browser automation frameworks. This provides:

- **Native browser control** via Claude in Chrome extension
- **Shared login state** - no need for auth scripts
- **Natural language test execution** - describe actions, Claude executes them
- **Real browser testing** - uses your actual Chrome with all extensions/state

## Test Coverage

### Test Categories (62 scenarios total)

| Category | Count | Description |
|----------|-------|-------------|
| Setup & Auth | 4 | Login, add server, OAuth, verify tools |
| Profile & Organization | 12 | Employee profile, manager, team, directory, custom fields |
| Leave Management | 22 | Balance, requests, sick leave, unpaid, public holidays |
| Documents | 12 | Categories, list, download, upload, multiple types |
| Error Handling | 12 | Invalid IDs, permissions, validation, edge cases |
| Cleanup | 2 | Disconnect, remove server |

### HR Self-Service Tools Tested

**Profile & Organization (12 tests):**
- `get_my_profile` - Get employee profile, custom fields, coach info
- `get_my_manager` - Get manager info
- `get_my_team` - List department colleagues
- `find_colleague` - Search employees by name
- `get_direct_reports` - Get direct reports
- `update_my_contact` - Update contact info
- `search_records` - Search across departments

**Time Off / Leave (22 tests):**
- `get_my_leave_balance` - Check leave balance (all types: PTO, Sick, Unpaid)
- `get_my_leave_requests` - View leave requests (pending, approved, history)
- `request_leave` - Submit new request (vacation, sick, unpaid, single/multi-day)
- `cancel_leave_request` - Cancel pending request
- `search_holidays` - Team availability
- `get_public_holidays` - Company holidays and planning

**Documents (12 tests):**
- `get_document_categories` - List document folders with counts
- `get_my_documents` - List HR documents (contracts, identity, recent)
- `download_document` - Download document content
- `upload_identity_document` - Upload ID documents (passport, ID card, license)
- `get_document_details` - Document metadata

### Tests Requiring Staging Configuration

The following tests require additional Odoo staging configuration:
- **Sick leave tests** (L02, L07, L15, L16): Requires sick leave allocation
- **Unpaid leave tests** (L13): Requires unpaid leave type enabled
- **Public holiday tests** (L17, L18, L19): Requires 2026 holidays configured

## Prerequisites

### Required Software

| Component | Minimum Version | Check Command |
|-----------|----------------|---------------|
| Claude Code CLI | v2.0.73+ | `claude --version` |
| Claude in Chrome | v1.0.36+ | Check Chrome extensions |
| Google Chrome | Latest | Chrome only (not Brave/Arc) |

### Required Accounts

- **Claude Pro/Team/Enterprise** subscription (for Chrome integration)
- **Google account** for OAuth with Odoo MCP server

### Installation

1. **Update Claude Code:**
   ```bash
   claude update
   ```

2. **Install Claude in Chrome extension:**
   - Visit: https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn
   - Click "Add to Chrome"

3. **Start the MCP server:**
   ```bash
   python -m odoo_mcp_server.http_server
   ```

## Running Tests

### Quick Start

```bash
# Run the interactive test runner
./scripts/run_e2e_tests.sh
```

### Manual Testing

```bash
# Start Claude Code with Chrome integration
claude --chrome

# Verify Chrome connection
/chrome

# Then execute test scenarios manually
```

## Test Scenarios

See `scenarios.json` for the complete test configuration.

### Setup Tests (S01-S04)

| ID | Name | Description |
|----|------|-------------|
| S01 | Verify Login | Check Claude.ai chat interface is accessible |
| S02 | Add MCP Server | Add custom connector with OAuth config |
| S03 | OAuth Connect | Complete Google OAuth authentication |
| S04 | Verify Tools | Confirm all 19+ tools are loaded |

### Profile Tests (P01-P12)

| ID | Name | Tool | Modifies Data |
|----|------|------|---------------|
| P01 | Get My Profile | get_my_profile | No |
| P02 | Get My Manager | get_my_manager | No |
| P03 | Get My Team | get_my_team | No |
| P04 | Find Colleague | find_colleague | No |
| P05 | Find by Department | search_employees | No |
| P06 | Get Direct Reports | get_direct_reports | No |
| P07 | Update Contact | update_my_contact | Yes |
| P08 | Search Directory | search_employees | No |
| P09 | Custom Fields | get_my_profile | No |
| P10 | Coach Info | get_my_profile | No |
| P11 | Find All Managers | search_records | No |
| P12 | Revert Contact | update_my_contact | Yes |

### Leave Tests (L01-L22)

| ID | Name | Tool | Modifies Data | Requires Staging |
|----|------|------|---------------|------------------|
| L01 | Get Leave Balance | get_my_leave_balance | No | - |
| L02 | Specific Balance (Sick) | get_my_leave_balance | No | Sick leave |
| L03 | Leave History | get_my_leave_requests | No | - |
| L04 | Pending Leave | get_my_leave_requests | No | - |
| L05 | Upcoming Leave | get_my_leave_requests | No | - |
| L06 | Request Vacation | request_leave | Yes | - |
| L07 | Request Sick | request_leave | Yes | Sick leave |
| L08 | Request Half Day | request_leave | Yes | - |
| L09 | Cancel Leave | cancel_leave_request | Yes | - |
| L10 | Team Availability | search_holidays | No | - |
| L11 | Public Holidays | get_public_holidays | No | Holidays |
| L12 | Leave with Reason | request_leave | Yes | - |
| L13 | Request Unpaid | request_leave | Yes | Unpaid leave |
| L14 | All Leave Balances | get_my_leave_balance | No | - |
| L15 | Sick Same Day | request_leave | Yes | Sick leave |
| L16 | Multi-Day Sick | request_leave | Yes | Sick leave |
| L17 | Leave Over Holiday | request_leave | Yes | Holidays |
| L18 | Holiday in Range | get_public_holidays | No | Holidays |
| L19 | Year Holidays | get_public_holidays | No | Holidays |
| L20 | Single Day Leave | request_leave | Yes | - |
| L21 | Balance After Request | get_my_leave_balance | No | - |
| L22 | Multiple Pending | get_my_leave_requests | No | - |

### Document Tests (D01-D12)

| ID | Name | Tool | Modifies Data |
|----|------|------|---------------|
| D01 | Document Categories | get_document_categories | No |
| D02 | List All Documents | get_my_documents | No |
| D03 | List Contracts | get_my_documents | No |
| D04 | List Identity Docs | get_my_documents | No |
| D05 | Download Document | download_document | No |
| D06 | Upload Identity | upload_identity_document | Yes |
| D07 | Document Details | get_document_details | No |
| D08 | Expiring Documents | get_my_documents | No |
| D09 | Upload ID Card | upload_identity_document | Yes |
| D10 | Upload Driving License | upload_identity_document | Yes |
| D11 | Document Count | get_document_categories | No |
| D12 | Recent Documents | get_my_documents | No |

### Error Tests (E01-E12)

| ID | Name | Tests |
|----|------|-------|
| E01 | Invalid Employee | Non-existent record handling |
| E02 | Overlapping Dates | Leave date conflict validation |
| E03 | Insufficient Balance | Leave balance validation |
| E04 | Cancel Approved | Policy restriction handling |
| E05 | Access Denied | Document permission handling |
| E06 | Invalid Dates | Date validation (Feb 30) |
| E07 | End Before Start | Date order validation |
| E08 | Past Date Request | Past date rejection |
| E09 | Invalid Leave Type | Non-existent leave type |
| E10 | Cancel Non-Existent | Invalid request ID |
| E11 | Empty Document Upload | Missing content validation |
| E12 | Invalid Document Type | Wrong document type |

### Cleanup Tests (C01-C02)

| ID | Name | Description |
|----|------|-------------|
| C01 | Disconnect | Disconnect MCP server |
| C02 | Remove Server | Remove integration completely |

## Test Suites

Predefined test suites in `scenarios.json`:

| Suite | Count | Description |
|-------|-------|-------------|
| `smoke` | 4 | Quick validation (login, profile, leave, docs) |
| `setup` | 4 | Server setup and OAuth |
| `profile` | 12 | All profile/organization tests |
| `leave` | 22 | All leave management tests |
| `documents` | 12 | All document tests |
| `errors` | 12 | Error handling tests |
| `cleanup` | 2 | Disconnect and remove |
| `read_only` | 30 | Tests that don't modify data |
| `write_tests` | 15 | Tests that modify data |
| `all_leave_types` | 8 | Tests for PTO, Sick, Unpaid leave |
| `public_holidays` | 4 | Holiday-related tests |
| `requires_staging_config` | 8 | Tests needing staging data |
| `comprehensive` | 58 | All tests except cleanup |
| `full` | 25 | Core test run |

## Test Data Requirements

### Odoo Staging Environment

| Data | Requirement |
|------|-------------|
| Employees | Full profile data with department and manager |
| Departments | Structure with managers assigned |
| Leave Types | PTO, Sick, Unpaid configured |
| Leave Allocations | Assigned to test employees |
| Documents | HR docs in Contracts and Identity folders |
| Public Holidays | Configured for 2026 |

### Test User Requirements

- Must be linked to an employee record
- Must have leave allocations for multiple types
- Must have documents in at least 2 categories
- Must have a manager assigned
- Must belong to a department with colleagues

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_MCP_SERVER_URL` | `http://localhost:8080` | MCP server URL |
| `TEST_MCP_SERVER_NAME` | `Odoo MCP Staging` | Integration name in Claude |

Example:
```bash
TEST_MCP_SERVER_URL=https://mcp.example.com ./scripts/run_e2e_tests.sh
```

## Test Execution Flow

1. **Setup Phase:**
   - Navigate to Claude.ai
   - Add MCP server as custom integration
   - Complete OAuth authentication
   - Verify all tools are loaded

2. **Test Phase:**
   - Execute MCP tool tests via chat
   - Verify tool invocation and results
   - Test error handling scenarios

3. **Cleanup Phase:**
   - Disconnect integration
   - Remove integration from Claude

## Writing New Test Scenarios

Add scenarios to `scenarios.json`:

```json
{
  "id": "P99_my_test",
  "name": "My Test Name",
  "description": "What this test validates",
  "prompt": "Natural language instruction for Claude to execute",
  "expected": "What the expected outcome should be",
  "category": "profile",
  "tool": "tool_name",
  "modifies_data": false
}
```

### ID Prefixes

- `S##` - Setup tests
- `P##` - Profile/organization tests
- `L##` - Leave management tests
- `D##` - Document tests
- `E##` - Error handling tests
- `C##` - Cleanup tests

### Categories

- `setup` - Initial setup steps
- `profile` - Employee/organization tests
- `leave` - Time-off management tests
- `documents` - HR document tests
- `errors` - Error handling tests
- `cleanup` - Teardown steps

## Troubleshooting

### Chrome Extension Not Detected

```bash
# Check connection status
/chrome

# Reconnect if needed
/chrome → "Reconnect extension"
```

### Modal Dialogs Blocking

JavaScript alerts/confirms block Claude's communication with Chrome. Dismiss them manually and tell Claude to continue.

### Browser Not Responding

1. Check for modal dialogs
2. Create a new tab
3. Restart the Chrome extension

### MCP Tool Timeouts

If tool calls timeout:
1. Create a new chat tab
2. Try the prompt again
3. Check MCP server logs

## CI/CD Note

E2E tests require interactive browser access and cannot run in headless CI environments. They should be run manually or in environments with display access.

For automated CI testing, use the unit and integration tests:
```bash
pytest tests/unit tests/integration -v
```

## References

- [Claude Code Chrome Docs](https://code.claude.com/docs/en/chrome)
- [Claude in Chrome Extension](https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
