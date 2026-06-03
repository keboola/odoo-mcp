# Claude.ai MCP Integration Guide

This guide explains how to connect the Odoo MCP Server to Claude.ai using Google OAuth authentication.

## Prerequisites

- Odoo MCP Server deployed and accessible via HTTPS
- Google Cloud project with OAuth 2.0 credentials configured
- Access to Claude.ai with MCP server capabilities

## Quick Setup

### 1. Configure Google OAuth

Your Google OAuth client must have these redirect URIs configured:

```
https://claude.ai/oauth/callback
https://claude.ai/api/auth/callback
https://api.claude.ai/oauth/callback
https://claude.ai/auth/callback
https://claude.ai/api/mcp/auth_callback
https://your-mcp-server-url/oauth/callback
```

### 2. Deploy MCP Server

Set these environment variables on your server:

```bash
# Google OAuth (required)
OAUTH_PROVIDER=google
OAUTH_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=your-google-client-secret

# Server identity (required)
OAUTH_RESOURCE_IDENTIFIER=https://your-mcp-server-url
OAUTH_REDIRECT_URI=https://your-mcp-server-url/oauth/callback

# Odoo connection (required)
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your-database
ODOO_API_KEY=your-odoo-api-key
```

### 3. Add to Claude.ai

1. Go to **Claude.ai** > **Settings** > **MCP Servers**
2. Click **Add Server**
3. Configure:
   - **Name**: Odoo MCP (or your preferred name)
   - **URL**: `https://your-mcp-server-url/mcp`
   - **Transport**: `streamable-http`
   - **Authentication**: OAuth 2.0

4. Click **Connect** - you'll be redirected to Google sign-in
5. Sign in with your Google account
6. Once authenticated, the server will be connected

## Available Tools

After connecting, Claude will have access to these tools:

### Employee Self-Service
| Tool | Description | Required Scope |
|------|-------------|----------------|
| `get_my_profile` | Get your employee profile | `odoo.hr.profile` |
| `get_my_manager` | Get your manager's info | `odoo.hr.profile` |
| `get_my_team` | List your team members | `odoo.hr.team` |
| `find_colleague` | Search employee directory | `odoo.hr.directory` |

### Leave Management
| Tool | Description | Required Scope |
|------|-------------|----------------|
| `get_my_leave_balance` | Check leave balances | `odoo.leave.read` |
| `get_my_leave_requests` | List your leave requests | `odoo.leave.read` |
| `request_leave` | Submit a leave request | `odoo.leave.write` |
| `cancel_leave_request` | Cancel a pending request | `odoo.leave.write` |

### Document Management
| Tool | Description | Required Scope |
|------|-------------|----------------|
| `get_my_documents` | List your HR documents | `odoo.documents.read` |
| `get_document_categories` | List document categories | `odoo.documents.read` |
| `upload_identity_document` | Upload ID documents | `odoo.documents.write` |

## Example Conversations

### Check Leave Balance
> **You**: How much vacation do I have left?
>
> **Claude**: Let me check your leave balance...
>
> You have 15.5 days of Paid Time Off remaining and 3 days of Sick Leave.

### Request Time Off
> **You**: I'd like to take vacation from Dec 23-27
>
> **Claude**: I'll submit a leave request for you...
>
> Your leave request has been submitted:
> - Type: Paid Time Off
> - From: December 23, 2025
> - To: December 27, 2025
> - Status: Pending approval

### Find a Colleague
> **You**: Can you find John Smith's contact info?
>
> **Claude**: Let me search the directory...
>
> Found John Smith:
> - Email: john.smith@example.com
> - Department: Engineering
> - Position: Senior Developer
> - Phone: +1 555-0123

## Scope Permissions

Your access level depends on your Google account's email domain:

### Internal Users (@yourcompany.com)
Full access to all employee self-service features including write operations.

### External Users (other domains)
Read-only access to profile information and directory search.

## Troubleshooting

### "Authentication failed"
- Verify your Google OAuth client ID and secret are correct
- Check that redirect URIs match exactly in Google Console
- Ensure the MCP server is accessible via HTTPS

### "No employee found"
- Your Google email must match an employee record in Odoo
- Contact your Odoo administrator to link your email

### "Insufficient scope"
- Your email domain may not have write access
- Contact your administrator for elevated permissions

### "Token expired"
- Claude.ai should automatically refresh tokens
- Try disconnecting and reconnecting the MCP server

## Server Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |
| `GET /.well-known/oauth-protected-resource` | OAuth resource metadata (RFC 9728) |
| `GET /oauth/callback` | OAuth authorization callback |
| `POST /mcp` | MCP JSON-RPC endpoint |

## Security Considerations

1. **Email Verification**: Only Google accounts with verified emails are accepted
2. **Domain-based Access**: Write permissions are restricted by email domain
3. **Employee Mapping**: Users can only access their own data (matched by email)
4. **Token Validation**: All tokens are validated against Google's JWKS
5. **No Credential Storage**: Tokens are validated on each request; no passwords stored

## Support

For issues with:
- **MCP Server**: Check logs at `docker logs odoo-mcp-server`
- **OAuth**: Verify Google Console configuration
- **Odoo Access**: Contact your Odoo administrator
- **Claude.ai**: Visit [Claude Support](https://support.claude.com)
