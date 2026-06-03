# Security Architecture

This document describes the security architecture of the Odoo MCP Server, addressing feedback on token storage, scope granularity, and error handling.

## Token Storage Strategy (Feedback 4.1)

### Overview

The MCP server acts as an **OAuth 2.1 Resource Server**. It validates tokens but does NOT issue them. Token storage needs differ based on deployment context:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Client (Claude/Slack)                        │
│                    Stores: access_token, refresh_token          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (Resource Server)                 │
│                    Caches: validated token claims (short TTL)   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Authorization Server                         │
│                    Stores: all tokens, user sessions            │
└─────────────────────────────────────────────────────────────────┘
```

### Storage Backends

Configure via `TOKEN_STORAGE_BACKEND` environment variable:

#### 1. Memory (Default)

```python
TOKEN_STORAGE_BACKEND=memory
```

- **Use case**: Single-instance deployments, development
- **Pros**: Fast, no external dependencies
- **Cons**: Lost on restart, not shared across instances
- **Security**: Tokens in process memory only

#### 2. Redis (Production)

```python
TOKEN_STORAGE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
TOKEN_CACHE_TTL=300  # 5 minutes
```

- **Use case**: Multi-instance deployments, production
- **Pros**: Shared cache, survives restarts, automatic expiry
- **Cons**: Requires Redis infrastructure
- **Security**: Use Redis AUTH and TLS in production

#### 3. Encrypted File (Air-gapped)

```python
TOKEN_STORAGE_BACKEND=encrypted_file
TOKEN_ENCRYPTION_KEY=<base64-encoded-32-byte-key>
TOKEN_STORAGE_PATH=/secure/tokens.enc
```

- **Use case**: Air-gapped environments, compliance requirements
- **Pros**: No network dependencies, encrypted at rest
- **Cons**: Slower, single-instance only
- **Security**: AES-256-GCM encryption

### What We Cache (and Why)

The MCP server caches **validated token claims**, NOT the tokens themselves:

```python
# Cached structure (example)
{
    "sub": "user123",                    # User ID
    "email": "user@example.com",         # For employee mapping
    "scope": ["odoo.hr.profile", "odoo.leave.read"],
    "exp": 1735689600,                   # Expiration (for cache TTL)
    "employee_id": 42,                   # Resolved Odoo employee ID
    "cached_at": 1735686000,
}
```

**Why cache claims, not tokens?**
1. Reduces token validation overhead (no repeated JWT verification)
2. Avoids storing sensitive bearer tokens
3. Employee ID resolution is expensive (Odoo lookup)

### Cache Invalidation

- **TTL-based**: Claims cached for min(token_exp, 5 minutes)
- **On error**: Cache entry removed if Odoo returns permission error
- **Manual**: Admin endpoint to clear cache (if needed)

---

## OAuth Scope Granularity (Feedback 4.1)

### Scope Hierarchy

```
openid                      # Required for OIDC
├── odoo.read               # Broad: read any Odoo data
├── odoo.write              # Broad: write any Odoo data
│
├── odoo.hr.profile         # Narrow: own profile only
├── odoo.hr.team            # Narrow: team members
├── odoo.hr.directory       # Narrow: employee search
│
├── odoo.leave.read         # Narrow: own leave data
├── odoo.leave.write        # Narrow: create/cancel leave
├── odoo.leave.approve      # Narrow: manager approval
│
├── odoo.documents.read     # Narrow: own documents
└── odoo.documents.write    # Narrow: upload identity docs
```

### Scope-to-Tool Mapping

Each MCP tool requires at least one of the listed scopes:

| Tool | Required Scopes (any) |
|------|----------------------|
| `get_my_profile` | `odoo.hr.profile`, `odoo.read` |
| `get_my_manager` | `odoo.hr.profile`, `odoo.read` |
| `get_my_team` | `odoo.hr.team`, `odoo.read` |
| `find_colleague` | `odoo.hr.directory`, `odoo.read` |
| `get_my_leave_balance` | `odoo.leave.read`, `odoo.read` |
| `get_my_leave_requests` | `odoo.leave.read`, `odoo.read` |
| `request_leave` | `odoo.leave.write`, `odoo.write` |
| `cancel_leave_request` | `odoo.leave.write`, `odoo.write` |
| `get_my_documents` | `odoo.documents.read`, `odoo.read` |
| `get_document_categories` | `odoo.documents.read`, `odoo.read` |
| `upload_identity_document` | `odoo.documents.write`, `odoo.write` |
| `download_document` | `odoo.documents.read`, `odoo.read` |

### Recommended Client Configurations

**Minimal (Read-only employee self-service)**:
```
scope: openid odoo.hr.profile odoo.leave.read odoo.documents.read
```

**Standard (Employee self-service)**:
```
scope: openid odoo.hr.profile odoo.hr.directory odoo.leave.read odoo.leave.write odoo.documents.read odoo.documents.write
```

**Manager (Team management)**:
```
scope: openid odoo.hr.profile odoo.hr.team odoo.leave.read odoo.leave.write odoo.leave.approve
```

**Admin/Integration (Full access)**:
```
scope: openid odoo.read odoo.write
```

---

## Error Handling (Feedback 4.2)

### Error Hierarchy

```
OdooError (base)
├── OdooAuthenticationError    # Invalid credentials (code: ACCESS_DENIED)
├── OdooPermissionError        # Insufficient access (code: PERMISSION_DENIED)
├── OdooRecordNotFoundError    # Record doesn't exist (code: RECORD_NOT_FOUND)
├── OdooValidationError        # Data validation failed (code: VALIDATION_ERROR)
├── OdooConnectionError        # Network issues (code: CONNECTION_ERROR)
│   └── OdooTimeoutError       # Request timeout (code: CONNECTION_TIMEOUT)
└── OdooServerError            # Odoo internal error (code: SERVER_ERROR)
```

### XML-RPC Fault Mapping

| Odoo Fault Code | Fault String Contains | Maps To |
|-----------------|----------------------|---------|
| 3 | "Access Denied" | `OdooAuthenticationError` |
| 4 | "AccessError" | `OdooPermissionError` |
| 2 | "MissingError" | `OdooRecordNotFoundError` |
| 1 | "UserError", "ValidationError" | `OdooValidationError` |
| * | (network errors) | `OdooConnectionError` |

### MCP Error Response Format

All errors are converted to MCP-friendly JSON:

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Leave request overlaps with existing approved leave",
        "field": "date_from"
    }
}
```

### Retryable Errors

| Error Type | Retryable | Recommendation |
|------------|-----------|----------------|
| `OdooConnectionError` | Yes | Retry with exponential backoff |
| `OdooTimeoutError` | Yes | Retry with longer timeout |
| `OdooServerError` | Yes | Retry after delay |
| `OdooAuthenticationError` | No | Re-authenticate |
| `OdooPermissionError` | No | Request additional scopes |
| `OdooValidationError` | No | Fix input data |

---

## Concurrency Safety (Feedback 4.3)

### OdooClient Thread Safety

The `OdooClient` is designed for async usage with FastAPI:

```python
class OdooClient:
    def __init__(self, ...):
        self._uid: int | None = None
        self._uid_lock = asyncio.Lock()  # Protects UID caching

    async def authenticate(self) -> int:
        if self._uid:
            return self._uid  # Fast path

        async with self._uid_lock:  # Thread-safe
            if self._uid:
                return self._uid  # Double-check after lock
            # ... authentication logic ...
```

### Safe Patterns

**Shared client (recommended for FastAPI lifespan)**:
```python
# Single client instance, reused across requests
async with OdooClient(...) as client:
    app.state.odoo = client
```

**Request-scoped client (alternative)**:
```python
# New client per request (more isolation, more overhead)
async def get_odoo():
    async with OdooClient(...) as client:
        yield client
```

### What's NOT Thread-Safe

- Do not modify `_uid` directly
- Do not share client across different event loops
- Do not use synchronous XML-RPC calls in async context

---

## Data Isolation

### Employee Self-Service

All tools automatically filter to the authenticated employee's data:

```python
async def get_my_leave_balance(employee_id: int, client: OdooClient):
    # employee_id comes from OAuth token, NOT from user input
    return await client.search_read(
        model="hr.leave.allocation",
        domain=[["employee_id", "=", employee_id]],  # Auto-filtered
        fields=["holiday_status_id", "number_of_days", "leaves_taken"]
    )
```

### Field-Level Security

| Field Category | Visible To |
|---------------|------------|
| Public (name, work_email, department) | All employees |
| Private (private_email, emergency_contact) | Self only |
| Restricted (bank_account, identification_id) | Never via MCP |

### Document Folder Restrictions

| Folder | Visibility |
|--------|------------|
| Contracts | Read-only (self) |
| Identity | Read/Upload (self) |
| Background Checks | Hidden |
| Offboarding Documents | Hidden |

---

## Rate Limiting

```python
RATE_LIMITS = {
    "requests_per_minute": 30,
    "write_operations_per_hour": 10,
    "document_uploads_per_day": 5,
}
```

---

## Audit Logging

All operations are logged for compliance:

```python
{
    "timestamp": "2025-01-15T10:30:00Z",
    "employee_id": 42,
    "operation": "request_leave",
    "model": "hr.leave",
    "record_ids": [123],
    "success": true,
    "scopes_used": ["odoo.leave.write"]
}
```

---

## Security Checklist

- [ ] OAuth tokens validated on every request
- [ ] Employee ID derived from token, not user input
- [ ] Scopes checked before tool execution
- [ ] Sensitive fields excluded from responses
- [ ] Rate limits enforced
- [ ] Audit logging enabled
- [ ] HTTPS required in production
- [ ] XML-RPC errors mapped to safe messages
