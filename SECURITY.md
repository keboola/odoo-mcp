# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability** to open a private advisory.

Include as much detail as you can: affected version/commit, reproduction steps,
impact, and any suggested mitigation. We aim to acknowledge reports within a few
business days and will coordinate a fix and disclosure timeline with you.

## Scope

This project is an OAuth 2.1 MCP server that brokers access to an Odoo ERP
instance. Of particular interest:

- Authentication / token validation bypass
- Cross-user data access (an authenticated user reading another user's records)
- Privilege escalation via OAuth scopes
- Injection through tool arguments into Odoo domain filters or XML-RPC calls
- Leakage of credentials, tokens, or PII in logs or error responses

See [docs/SECURITY.md](docs/SECURITY.md) for the security architecture and the
invariants the server is designed to preserve (e.g. employee identity is always
derived from the token, never from tool input).

## Supported versions

Security fixes are applied to the latest release on the `main` branch.
