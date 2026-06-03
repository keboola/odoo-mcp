# Odoo MCP Server - Security Context

## System Overview

This system is an MCP (Model Context Protocol) server providing Odoo ERP self-service capabilities:

- **Authentication:** Google OAuth 2.1 with JWT validation (JWKS + tokeninfo)
- **Backend:** XML-RPC to Odoo ERP (shared service account)
- **Transport:** HTTP (Starlette/uvicorn) + stdio
- **Protocol:** MCP (Model Context Protocol) with tools and resources

## Data Classification

### CRITICAL - Credentials
| Credential | Purpose | Risk if Exposed |
|------------|---------|-----------------|
| `ODOO_API_KEY` | XML-RPC authentication to Odoo | Full Odoo access |
| `ODOO_PASSWORD` | Alternative XML-RPC authentication | Full Odoo access |
| `OAUTH_CLIENT_SECRET` | Google OAuth client secret | Token forgery |
| OAuth Bearer tokens | Per-request user authentication | User impersonation |

### HIGH - PII (Personally Identifiable Information)
- Employee names (first, last)
- Email addresses (work and personal)
- Phone numbers
- Employee IDs
- Leave records (dates, types, status)
- Department and job title

### MEDIUM - Operational Data
- Odoo model/field names
- Department structure
- Document metadata (DMS)
- Attendance records

### LOW - Public Data
- Public employee directory info
- Company structure

## Sensitive Operations

### 1. OAuth Token Validation
Validates Google-issued JWT tokens:
- JWKS key fetching from Google
- Token signature verification
- Audience and issuer validation
- Email extraction for user mapping

**Security Risks:**
- Token replay attacks
- JWKS key rotation failures
- Audience confusion

### 2. XML-RPC Calls to Odoo
All Odoo operations use `execute_kw` via XML-RPC:
- Shared service account with elevated permissions
- Domain filters control data access

**Security Risks:**
- XML-RPC injection via user input in domain filters
- Over-privileged service account
- Missing employee_id constraint in filters

### 3. Employee Data Filtering
MCP tools return employee data filtered by authenticated user:
- employee_id derived from OAuth token email
- Domain filters always include employee_id constraint

**Security Risks:**
- employee_id from user input instead of token
- Missing or incorrect domain filters
- Cross-employee data access

### 4. Document Operations (DMS)
Upload/download of identity documents:
- Access control tied to employee_id

**Security Risks:**
- Unauthorized document access
- Document upload without proper validation

## Security Patterns to Preserve

### 1. Employee ID from Token (REQUIRED)
```python
employee_id = user_context.employee_id  # Derived from OAuth token
```
employee_id must ALWAYS come from the authenticated OAuth token, NEVER from user input.

### 2. Domain Filter Constraint (REQUIRED)
```python
domain = [('employee_id', '=', employee_id)]  # Always filter by authenticated user
```
All Odoo queries MUST include the employee_id constraint.

### 3. Sensitive Field Exclusion (REQUIRED)
Fields like `bank_account_id`, `identification_id` are NEVER returned via MCP tools.

### 4. YOLO Mode Scope (IMPORTANT)
YOLO_MODE bypasses OAuth authentication ONLY. Data filtering by employee_id is NEVER bypassed.

### 5. Credential Loading from Environment
```python
api_key = settings.odoo_api_key  # From environment via pydantic-settings
```
Credentials loaded from environment variables via pydantic-settings, never hardcoded.

## Security Anti-Patterns to Flag

### CRITICAL - Must Block PR
1. Logging OAuth tokens: `logger.info(f"Token: {token}")`
2. Logging API keys: `logger.debug(f"Using key: {api_key}")`
3. Hardcoded credentials: `api_key = "sk-1234..."`
4. employee_id from user input: `employee_id = arguments.get('employee_id')`
5. Missing domain filter constraint in Odoo queries

### HIGH - Should Request Changes
1. PII in info/debug logs: `logger.info(f"Processing {email}")`
2. Verbose exception messages exposing internals
3. Missing input validation on tool arguments
4. OAuth token contents in error messages

### MEDIUM - Should Comment
1. Missing audit logging for privileged operations
2. Overly broad exception handling
3. Missing rate limiting on token validation
4. Inconsistent error responses

## File Sensitivity Classification

| File Pattern | Sensitivity | Reason |
|--------------|-------------|--------|
| `config.py` | CRITICAL | Credential loading, environment config |
| `http_server.py` | CRITICAL | OAuth validation, request handling |
| `token_validator.py` | CRITICAL | JWT validation, JWKS handling |
| `resource_server.py` | CRITICAL | MCP resource server with auth |
| `odoo_client.py` / `client.py` | HIGH | XML-RPC auth, Odoo operations |
| `user_mapping.py` | HIGH | OAuth email to employee_id mapping |
| `server.py` | MEDIUM | MCP server setup |
| `tools.py` | MEDIUM | MCP tool implementations |
| `resources.py` | MEDIUM | MCP resource implementations |
| `*_test.py`, `test_*.py` | LOW | Test files |
