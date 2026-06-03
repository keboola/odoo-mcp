# Accepted Security Risks

This document records security findings that have been reviewed and accepted. The security reviewer should NOT flag these issues in future reviews.

---

## ADR-001: allow-unauthenticated on Cloud Run

**Status:** Accepted
**Date:** 2026-03-07

### Context

Cloud Run is set to `--allow-unauthenticated` because the MCP server handles its own OAuth Bearer token validation. Cloud Run IAM is not used for access control.

### Decision

Accepted - The MCP server validates OAuth tokens at the application layer. Cloud Run IAM authentication would be redundant and would prevent the OAuth 2.1 flow from working correctly.

### Consequences

- The application MUST validate OAuth tokens on every request
- Token validation bypass (YOLO mode) is restricted to development only
- Any regression in token validation could expose all endpoints

---

## Template for Future Accepted Risks

```markdown
## ADR-XXX: [Title]

**Status:** Accepted | Superseded | Deprecated
**Date:** YYYY-MM-DD

### Context
[Why was this flagged?]

### Decision
[Accept / Reject / Defer]

### Rationale
[Why is this acceptable?]

### Consequences
[What are the implications?]
```
