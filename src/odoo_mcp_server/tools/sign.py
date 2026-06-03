"""
Sign Module Tools (OCA Sign)

MCP tools for Odoo OCA Sign module (sign_oca) - document signing workflows.
All tools automatically filter to the authenticated user's data.

Note: This uses the OCA community Sign module, not Odoo Enterprise Sign.
Model names use the sign.oca.* prefix.
"""

import json
import logging
from typing import Any

from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

# Sign Module Tools Definition
SIGN_TOOLS = [
    Tool(
        name="get_my_pending_signatures",
        description="Get documents that are waiting for your signature",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_my_signature_requests",
        description="Get signature requests you have sent to others",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "draft", "sent", "signed", "canceled", "refused"],
                    "description": "Filter by request status (default: all)",
                    "default": "all",
                }
            },
        },
    ),
    Tool(
        name="get_signature_request_status",
        description="Get detailed status of a signature request including all signers and their progress",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "integer",
                    "description": "ID of the signature request",
                }
            },
            "required": ["request_id"],
        },
    ),
    Tool(
        name="list_sign_templates",
        description="List available document templates for signature requests",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="send_signature_request",
        description="Send a document for signature based on a template. Specify the template and signers.",
        inputSchema={
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "integer",
                    "description": "ID of the sign template to use (from list_sign_templates)",
                },
                "signers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "Signer's email address",
                            },
                            "role": {
                                "type": "string",
                                "description": "Signer role name (e.g. 'Customer' or 'Employee')",
                            },
                        },
                        "required": ["email"],
                    },
                    "description": "List of signers with their emails and optional roles",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject/reference for the signature request",
                },
                "message": {
                    "type": "string",
                    "description": "Optional message to include in the signing invitation email",
                },
            },
            "required": ["template_id", "signers"],
        },
    ),
    Tool(
        name="download_signed_document",
        description="Download the completed signed PDF document",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "integer",
                    "description": "ID of the completed signature request",
                }
            },
            "required": ["request_id"],
        },
    ),
    Tool(
        name="cancel_signature_request",
        description="Cancel a pending signature request that you created",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "integer",
                    "description": "ID of the signature request to cancel",
                }
            },
            "required": ["request_id"],
        },
    ),
]

# OCA Sign model names
MODEL_TEMPLATE = "sign.oca.template"
MODEL_REQUEST = "sign.oca.request"
MODEL_SIGNER = "sign.oca.request.signer"
MODEL_ROLE = "sign.oca.role"
MODEL_TEMPLATE_ITEM = "sign.oca.template.item"

# Fields to read from sign.oca.request
SIGN_REQUEST_FIELDS = [
    "id",
    "name",
    "template_id",
    "state",
    "create_date",
    "signer_ids",
    "create_uid",
    "employee_id",
    "dms_file_id",
]

# Fields to read from sign.oca.request.signer
# Note: OCA signer has no 'state' field; signed_on indicates completion
SIGN_SIGNER_FIELDS = [
    "id",
    "partner_id",
    "partner_name",
    "role_id",
    "signed_on",
    "request_id",
]

# Fields to read from sign.oca.template
SIGN_TEMPLATE_FIELDS = [
    "id",
    "name",
    "active",
    "item_ids",
    "filename",
]

# Valid status values for get_my_signature_requests filter
VALID_STATUS_FILTERS = {"all", "draft", "sent", "signed", "canceled", "refused"}

# Maximum length for user-supplied subject strings
MAX_SUBJECT_LENGTH = 200


async def _get_partner_id_for_employee(
    odoo_client: Any, employee_id: int
) -> tuple[int | None, str | None]:
    """
    Resolve partner_id and work_email for an employee.

    Resolution chain:
    1. hr.employee -> user_id -> res.users -> partner_id
    2. Fallback: search res.partner by employee's work_email
    3. Returns (None, work_email) if no partner link found

    Returns:
        Tuple of (partner_id, work_email)
    """
    employees = await odoo_client.read(
        model="hr.employee",
        ids=[employee_id],
        fields=["user_id", "work_email"],
    )
    if not employees:
        return None, None

    emp = employees[0]
    work_email = emp.get("work_email")

    # Primary: employee -> user -> partner
    user_id = emp.get("user_id")
    if user_id and isinstance(user_id, list):
        user_id = user_id[0]
    if user_id:
        users = await odoo_client.read(
            model="res.users",
            ids=[user_id],
            fields=["partner_id"],
        )
        if users and users[0].get("partner_id"):
            partner_id = users[0]["partner_id"]
            if isinstance(partner_id, list):
                partner_id = partner_id[0]
            return partner_id, work_email

    # Fallback: search for a partner with the employee's work email
    if work_email:
        partners = await odoo_client.search_read(
            model="res.partner",
            domain=[["email", "=ilike", work_email]],
            fields=["id"],
            limit=1,
        )
        if partners:
            return partners[0]["id"], work_email

    return None, work_email


async def _get_user_id_for_employee(
    odoo_client: Any, employee_id: int
) -> int | None:
    """
    Resolve the res.users id for an employee.

    Returns:
        user_id or None
    """
    employees = await odoo_client.read(
        model="hr.employee",
        ids=[employee_id],
        fields=["user_id"],
    )
    if not employees:
        return None

    user_id = employees[0].get("user_id")
    if user_id and isinstance(user_id, list):
        user_id = user_id[0]
    return user_id


def _extract_many2one_id(field_value: Any) -> int | None:
    """Extract ID from a Many2one field value (returns [id, name] or False)."""
    if field_value and isinstance(field_value, list):
        return field_value[0]
    if field_value and isinstance(field_value, int):
        return field_value
    return None


def _extract_many2one_name(field_value: Any) -> str | None:
    """Extract display name from a Many2one field value."""
    if field_value and isinstance(field_value, list) and len(field_value) > 1:
        return field_value[1]
    return None


async def _verify_sign_request_access(
    odoo_client: Any,
    request_id: int,
    partner_id: int | None,
    user_id: int | None,
    employee_id: int,
) -> dict | None:
    """
    Verify that the employee has access to a sign request.

    Checks (in order):
    1. User is the creator (create_uid matches user_id)
    2. Request is linked to this employee (employee_id field)
    3. User is a signer (partner_id matches)

    Returns:
        The sign.oca.request record if accessible, None otherwise.
    """
    requests = await odoo_client.read(
        model=MODEL_REQUEST,
        ids=[request_id],
        fields=SIGN_REQUEST_FIELDS,
    )
    if not requests:
        return None

    req = requests[0]

    # Check if user is the creator
    create_uid = _extract_many2one_id(req.get("create_uid"))
    if user_id and create_uid == user_id:
        return req

    # Check if request is linked to this employee
    req_employee_id = _extract_many2one_id(req.get("employee_id"))
    if req_employee_id == employee_id:
        return req

    # Check if user is a signer (by partner_id match)
    signer_ids = req.get("signer_ids", [])
    if signer_ids and partner_id:
        signers = await odoo_client.read(
            model=MODEL_SIGNER,
            ids=signer_ids,
            fields=["partner_id"],
        )
        for signer in signers:
            signer_partner = _extract_many2one_id(signer.get("partner_id"))
            if signer_partner == partner_id:
                return req

    return None


async def execute_sign_tool(
    name: str,
    arguments: dict[str, Any],
    odoo_client: Any,
    employee_id: int,
) -> list[TextContent]:
    """
    Execute a Sign module tool with employee context.

    Args:
        name: Tool name
        arguments: Tool arguments
        odoo_client: Odoo client instance
        employee_id: Authenticated employee's ID (from OAuth)
    """

    if name == "get_my_pending_signatures":
        partner_id, email = await _get_partner_id_for_employee(odoo_client, employee_id)

        # Build domain: find signers matching the user who haven't signed yet
        # OCA signer has no 'state' field; signed_on = False means not yet signed
        if not partner_id:
            return [TextContent(type="text", text=json.dumps({
                "error": "Cannot identify your signer identity. No partner linked to your employee record."
            }))]

        domain: list[Any] = [
            ["signed_on", "=", False],
            ["partner_id", "=", partner_id],
        ]

        signers = await odoo_client.search_read(
            model=MODEL_SIGNER,
            domain=domain,
            fields=SIGN_SIGNER_FIELDS,
            limit=50,
        )

        if not signers:
            return [TextContent(type="text", text=json.dumps({
                "pending_signatures": [],
                "count": 0,
                "message": "No documents waiting for your signature",
            }))]

        # Enrich with request details
        request_ids = list({
            _extract_many2one_id(s.get("request_id"))
            for s in signers
            if s.get("request_id")
        })
        request_ids = [rid for rid in request_ids if rid is not None]

        requests_map: dict[int, dict] = {}
        if request_ids:
            reqs = await odoo_client.read(
                model=MODEL_REQUEST,
                ids=request_ids,
                fields=["id", "name", "template_id", "state", "create_date", "create_uid"],
            )
            # Only include requests that are in a pending state
            for r in reqs:
                if r.get("state") in ("draft", "sent"):
                    requests_map[r["id"]] = r

        results = []
        for signer in signers:
            req_id = _extract_many2one_id(signer.get("request_id"))
            req = requests_map.get(req_id, {}) if req_id else {}
            if not req:
                continue  # Skip signers for completed/canceled requests
            template_name = _extract_many2one_name(req.get("template_id"))
            results.append({
                "request_id": req_id,
                "document_name": req.get("name") or template_name or "Unknown",
                "role": _extract_many2one_name(signer.get("role_id")),
                "sent_date": req.get("create_date"),
                "from": _extract_many2one_name(req.get("create_uid")),
            })

        return [TextContent(type="text", text=json.dumps({
            "pending_signatures": results,
            "count": len(results),
        }, default=str))]

    elif name == "get_my_signature_requests":
        status_filter = arguments.get("status", "all")

        # Validate status filter
        if status_filter not in VALID_STATUS_FILTERS:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Invalid status filter. Must be one of: {sorted(VALID_STATUS_FILTERS)}"
            }))]

        user_id = await _get_user_id_for_employee(odoo_client, employee_id)

        if not user_id:
            return [TextContent(type="text", text=json.dumps({
                "error": "No Odoo user linked to your employee record."
            }))]

        # Find requests created by this user OR linked to this employee
        req_domain: list[Any] = [
            "|",
            ["create_uid", "=", user_id],
            ["employee_id", "=", employee_id],
        ]
        if status_filter != "all":
            req_domain.append(["state", "=", status_filter])

        requests = await odoo_client.search_read(
            model=MODEL_REQUEST,
            domain=req_domain,
            fields=SIGN_REQUEST_FIELDS,
            limit=50,
        )

        results = []
        for req in requests:
            template_name = _extract_many2one_name(req.get("template_id"))
            signer_ids = req.get("signer_ids", [])
            # Count signed vs total
            signed_count = 0
            total_count = len(signer_ids)
            if signer_ids:
                signer_records = await odoo_client.read(
                    model=MODEL_SIGNER,
                    ids=signer_ids,
                    fields=["signed_on"],
                )
                signed_count = sum(1 for s in signer_records if s.get("signed_on"))

            results.append({
                "id": req["id"],
                "name": req.get("name") or template_name,
                "template": template_name,
                "state": req.get("state"),
                "created": req.get("create_date"),
                "progress": f"{signed_count}/{total_count} signed",
            })

        return [TextContent(type="text", text=json.dumps({
            "signature_requests": results,
            "count": len(results),
        }, default=str))]

    elif name == "get_signature_request_status":
        request_id = arguments["request_id"]
        partner_id, email = await _get_partner_id_for_employee(odoo_client, employee_id)
        user_id = await _get_user_id_for_employee(odoo_client, employee_id)

        req_data = await _verify_sign_request_access(
            odoo_client, request_id, partner_id, user_id, employee_id
        )
        if not req_data:
            return [TextContent(type="text", text=json.dumps({
                "error": "Signature request not found or you don't have access to it."
            }))]

        # Get all signers
        signer_ids = req_data.get("signer_ids", [])
        signers = []
        signed_count = 0
        if signer_ids:
            signer_records = await odoo_client.read(
                model=MODEL_SIGNER,
                ids=signer_ids,
                fields=SIGN_SIGNER_FIELDS,
            )
            for signer in signer_records:
                has_signed = bool(signer.get("signed_on"))
                if has_signed:
                    signed_count += 1
                signers.append({
                    "name": signer.get("partner_name") or _extract_many2one_name(signer.get("partner_id")),
                    "partner": _extract_many2one_name(signer.get("partner_id")),
                    "role": _extract_many2one_name(signer.get("role_id")),
                    "signed": has_signed,
                    "signed_on": signer.get("signed_on"),
                })

        template_name = _extract_many2one_name(req_data.get("template_id"))
        return [TextContent(type="text", text=json.dumps({
            "id": req_data["id"],
            "name": req_data.get("name") or template_name,
            "template": template_name,
            "state": req_data.get("state"),
            "created": req_data.get("create_date"),
            "progress": f"{signed_count}/{len(signer_ids)} signed",
            "signers": signers,
        }, default=str))]

    elif name == "list_sign_templates":
        # Templates are shared resources in Odoo; access is controlled by Odoo's
        # own ACL rules via the service account. All authenticated users with
        # odoo.sign.read scope can list active templates.
        templates = await odoo_client.search_read(
            model=MODEL_TEMPLATE,
            domain=[["active", "=", True]],
            fields=SIGN_TEMPLATE_FIELDS,
            limit=50,
        )

        results = []
        for t in templates:
            item_count = len(t.get("item_ids", []))
            results.append({
                "id": t["id"],
                "name": t.get("name"),
                "filename": t.get("filename"),
                "signature_fields": item_count,
            })

        return [TextContent(type="text", text=json.dumps({
            "templates": results,
            "count": len(results),
        }, default=str))]

    elif name == "send_signature_request":
        template_id = arguments["template_id"]
        signers_input = arguments["signers"]
        subject = arguments.get("subject")

        # Sanitize subject length
        if subject:
            subject = subject[:MAX_SUBJECT_LENGTH]

        # Verify template exists and is active
        templates = await odoo_client.read(
            model=MODEL_TEMPLATE,
            ids=[template_id],
            fields=["id", "name", "active", "item_ids"],
        )
        if not templates or not templates[0].get("active", True):
            return [TextContent(type="text", text=json.dumps({
                "error": "Template not found or is inactive."
            }))]

        template = templates[0]
        request_name = subject or template.get("name", f"Signature Request #{template_id}")

        # Get template roles from template items
        item_ids = template.get("item_ids", [])
        role_map: dict[int, str] = {}
        if item_ids:
            template_items = await odoo_client.read(
                model=MODEL_TEMPLATE_ITEM,
                ids=item_ids,
                fields=["role_id"],
            )
            # Get unique role IDs
            role_ids = list({
                _extract_many2one_id(item.get("role_id"))
                for item in template_items
                if item.get("role_id")
            })
            role_ids = [rid for rid in role_ids if rid is not None]
            if role_ids:
                roles = await odoo_client.read(
                    model=MODEL_ROLE,
                    ids=role_ids,
                    fields=["id", "name"],
                )
                role_map = {r["id"]: r["name"] for r in roles}

        # If no roles from template items, fetch all available roles
        if not role_map:
            all_roles = await odoo_client.search_read(
                model=MODEL_ROLE,
                domain=[],
                fields=["id", "name"],
                limit=10,
            )
            role_map = {r["id"]: r["name"] for r in all_roles}

        # Resolve signer partners and map to roles
        signers_info: list[dict[str, Any]] = []
        for signer in signers_input:
            signer_email = signer["email"]

            # Find partner by email
            partners = await odoo_client.search_read(
                model="res.partner",
                domain=[["email", "=ilike", signer_email]],
                fields=["id", "name"],
                limit=1,
            )
            if not partners:
                return [TextContent(type="text", text=json.dumps({
                    "error": "One or more signers could not be found as contacts in Odoo."
                }))]

            partner_id = partners[0]["id"]

            # Map to role
            signer_role = signer.get("role")
            role_id = None
            if signer_role:
                for rid, rname in role_map.items():
                    if rname.lower() == signer_role.lower():
                        role_id = rid
                        break
                if not role_id:
                    return [TextContent(type="text", text=json.dumps({
                        "error": f"Role not found. Available roles: {list(role_map.values())}"
                    }))]
            elif role_map:
                # Auto-assign to first available role not yet used
                used_roles = {s.get("role_id") for s in signers_info}
                for rid in role_map:
                    if rid not in used_roles:
                        role_id = rid
                        break
                if role_id is None:
                    role_id = next(iter(role_map))

            signers_info.append({
                "partner_id": partner_id,
                "role_id": role_id,
                "email": signer_email,
            })

        # Create the signature request with employee_id for ownership tracking
        request_vals: dict[str, Any] = {
            "template_id": template_id,
            "name": request_name,
            "employee_id": employee_id,
        }
        request_id = await odoo_client.create(
            model=MODEL_REQUEST,
            values=request_vals,
        )

        # Create signers
        for signer_info in signers_info:
            signer_vals: dict[str, Any] = {
                "request_id": request_id,
                "partner_id": signer_info["partner_id"],
            }
            if signer_info.get("role_id"):
                signer_vals["role_id"] = signer_info["role_id"]
            await odoo_client.create(
                model=MODEL_SIGNER,
                values=signer_vals,
            )

        # Try to send the request
        sent = False
        for method_name in ("action_sent", "send_request", "action_send"):
            try:
                await odoo_client.execute(
                    MODEL_REQUEST,
                    method_name,
                    [request_id],
                )
                sent = True
                break
            except Exception:
                continue

        logger.info(
            "sign_request_created: employee_id=%s request_id=%s template_id=%s signer_count=%s sent=%s",
            employee_id, request_id, template_id, len(signers_info), sent,
        )

        return [TextContent(type="text", text=json.dumps({
            "request_id": request_id,
            "name": request_name,
            "status": "sent" if sent else "created",
            "message": "Signature request sent successfully"
            if sent else "Request created but may need to be sent manually from Odoo",
            "signers": [s["email"] for s in signers_info],
        }, default=str))]

    elif name == "download_signed_document":
        request_id = arguments["request_id"]
        partner_id, email = await _get_partner_id_for_employee(odoo_client, employee_id)
        user_id = await _get_user_id_for_employee(odoo_client, employee_id)

        dl_req = await _verify_sign_request_access(
            odoo_client, request_id, partner_id, user_id, employee_id
        )
        if not dl_req:
            return [TextContent(type="text", text=json.dumps({
                "error": "Signature request not found or you don't have access to it."
            }))]

        if dl_req.get("state") != "signed":
            return [TextContent(type="text", text=json.dumps({
                "error": f"Document is not fully signed yet. Current state: {dl_req.get('state')}"
            }))]

        # Try to get the signed document from DMS first
        dms_file_id = _extract_many2one_id(dl_req.get("dms_file_id"))
        if dms_file_id:
            files = await odoo_client.read(
                model="dms.file",
                ids=[dms_file_id],
                fields=["name", "content", "mimetype"],
            )
            if files and files[0].get("content"):
                return [TextContent(type="text", text=json.dumps({
                    "filename": files[0].get("name", "signed_document.pdf"),
                    "content_base64": files[0]["content"],
                    "mimetype": files[0].get("mimetype", "application/pdf"),
                }, default=str))]

        # Fallback: read the data field from the request itself
        doc = await odoo_client.read(
            model=MODEL_REQUEST,
            ids=[request_id],
            fields=["data", "filename", "name", "template_id"],
        )

        if not doc or not doc[0].get("data"):
            return [TextContent(type="text", text=json.dumps({
                "error": "Signed document content not available."
            }))]

        template_name = _extract_many2one_name(doc[0].get("template_id"))
        filename = (
            doc[0].get("filename")
            or f"{doc[0].get('name') or template_name or 'signed_document'}.pdf"
        )

        return [TextContent(type="text", text=json.dumps({
            "filename": filename,
            "content_base64": doc[0]["data"],
            "mimetype": "application/pdf",
        }, default=str))]

    elif name == "cancel_signature_request":
        request_id = arguments["request_id"]

        # Read the request and verify ownership via employee_id or create_uid
        requests = await odoo_client.read(
            model=MODEL_REQUEST,
            ids=[request_id],
            fields=["id", "state", "create_uid", "employee_id", "name"],
        )
        if not requests:
            return [TextContent(type="text", text=json.dumps({
                "error": "Signature request not found."
            }))]

        req = requests[0]

        # Verify ownership: employee_id match OR create_uid match
        req_employee_id = _extract_many2one_id(req.get("employee_id"))
        user_id = await _get_user_id_for_employee(odoo_client, employee_id)
        create_uid = _extract_many2one_id(req.get("create_uid"))

        is_owner = (
            (req_employee_id is not None and req_employee_id == employee_id)
            or (user_id is not None and create_uid == user_id)
        )
        if not is_owner:
            return [TextContent(type="text", text=json.dumps({
                "error": "You can only cancel signature requests you created."
            }))]

        # Verify state allows cancellation
        if req.get("state") not in ("draft", "sent"):
            return [TextContent(type="text", text=json.dumps({
                "error": f"Cannot cancel request in state '{req.get('state')}'. Only 'draft' or 'sent' requests can be cancelled."
            }))]

        # Cancel the request
        for method_name in ("action_cancel", "cancel", "action_canceled"):
            try:
                await odoo_client.execute(
                    MODEL_REQUEST,
                    method_name,
                    [request_id],
                )
                break
            except Exception:
                continue
        else:
            # Fallback: try writing the state directly
            await odoo_client.write(
                model=MODEL_REQUEST,
                ids=[request_id],
                values={"state": "canceled"},
            )

        logger.info(
            "sign_request_cancelled: employee_id=%s request_id=%s",
            employee_id, request_id,
        )

        return [TextContent(type="text", text=json.dumps({
            "status": "canceled",
            "request_id": request_id,
            "name": req.get("name"),
            "message": "Signature request cancelled successfully",
        }))]

    else:
        raise ValueError(f"Unknown sign tool: {name}")
