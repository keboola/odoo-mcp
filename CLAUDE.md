# Odoo MCP Server

A Model Context Protocol (MCP) server that enables AI assistants like Claude to securely interact with your Odoo 18 ERP instance.

## Development Workflow

### Branching & PRs
1. Create a feature/fix branch from `main`
2. Make changes and commit
3. Push branch and create PR
4. Merge PR (squash preferred)

### Deployment
**IMPORTANT: Do NOT deploy manually with gcloud commands.**

Deployments are handled automatically by GitHub CI:
- Merging to `main` triggers automatic deployment to staging
- Production deployments require manual approval in GitHub Actions

### Testing
```bash
# Unit tests
pytest tests/unit/ -v

# Type checking
mypy src/

# All tests
pytest
```

## Project Structure

```
odoo-mcp-server/
├── src/odoo_mcp_server/
│   ├── server.py          # Main MCP server
│   ├── http_server.py     # HTTP transport
│   ├── config.py          # Configuration
│   ├── odoo/              # Odoo XML-RPC client
│   └── tools/             # MCP tools (employee.py, etc.)
├── tests/
│   ├── unit/              # Unit tests
│   └── e2e/               # E2E tests
├── docker/                # Docker config (production)
└── Dockerfile             # Root Dockerfile (Cloud Run)
```

## Key Files

- `src/odoo_mcp_server/http_server.py` - FastAPI app, OAuth flow, `/mcp` handler
- `src/odoo_mcp_server/tools/employee.py` - Employee self-service tools (profile, leave, documents)
- `src/odoo_mcp_server/tools/records.py` - Generic CRUD tools
- `src/odoo_mcp_server/tools/sign.py` - Optional OCA Sign tools
- `src/odoo_mcp_server/config.py` - Settings, OAuth scopes, per-tool scope requirements
- `src/odoo_mcp_server/odoo/client.py` - Odoo XML-RPC client wrapper

## Configuration Notes

- Required settings (`ODOO_URL`, `ODOO_DB`, auth) are validated at startup and
  fail fast — never add silent defaults.
- Per-instance behaviour is opt-in via env vars: `EMPLOYEE_CUSTOM_FIELDS`,
  `DMS_ALLOWED_FOLDERS` / `DMS_RESTRICTED_FOLDERS`, `SIGN_MODULE_ENABLED`,
  `INTERNAL_EMAIL_DOMAIN`. Defaults are stock-Odoo-safe.

## Deployment

A reference Cloud Run deployment runs from `.github/workflows/ci.yml` on merge
to `main`. See `docs/CI_CD.md` for required secrets and repository variables.
