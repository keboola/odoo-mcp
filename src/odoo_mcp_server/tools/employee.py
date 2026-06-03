"""
Employee Self-Service Tools

MCP tools designed for employee self-service scenarios.
All tools automatically filter to the authenticated user's data.
"""

import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from mcp.types import TextContent, Tool

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and injection."""
    # Take only the basename (strip any directory components)
    filename = os.path.basename(filename)
    # Remove null bytes and control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    # Remove path traversal sequences that might survive basename
    filename = filename.replace('..', '')
    # Fallback if filename is empty after sanitization
    if not filename or filename.startswith('.'):
        filename = f"upload_{filename}" if filename else "upload"
    return filename


# Employee Self-Service Tools Definition
EMPLOYEE_TOOLS = [
    # === Profile & Organization ===
    Tool(
        name="get_my_profile",
        description="Get your employee profile information including name, email, department, job title, and manager",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_my_manager",
        description="Get information about your direct manager including their name, email, and phone",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_my_team",
        description="Get list of colleagues in your department/team",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="find_colleague",
        description="Find a colleague by name and get their contact information (email, phone, department)",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name or partial name to search for",
                }
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="get_direct_reports",
        description="Get employees who report directly to you (for managers). Returns empty list if you're not a manager.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="update_my_contact",
        description="Update your contact information (work phone, mobile phone, or work email)",
        inputSchema={
            "type": "object",
            "properties": {
                "work_phone": {
                    "type": "string",
                    "description": "Work phone number",
                },
                "mobile_phone": {
                    "type": "string",
                    "description": "Mobile phone number",
                },
                "work_email": {
                    "type": "string",
                    "format": "email",
                    "description": "Work email address",
                },
            },
        },
    ),
    # === Time Off / Leave ===
    Tool(
        name="get_my_leave_balance",
        description="Get your remaining leave balance for all leave types (vacation, sick leave, etc.) for a specific year",
        inputSchema={
            "type": "object",
            "properties": {
                "leave_type": {
                    "type": "string",
                    "description": "Optional: specific leave type to check (e.g., 'Paid Time Off', 'Sick Leave')",
                },
                "year": {
                    "type": "integer",
                    "description": "Year to check balance for (default: current year)",
                },
            },
        },
    ),
    Tool(
        name="get_my_leave_requests",
        description="Get your leave/time-off requests and their status",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "pending", "approved", "rejected"],
                    "default": "all",
                    "description": "Filter by request status",
                }
            },
        },
    ),
    Tool(
        name="request_leave",
        description="Submit a new leave/time-off request",
        inputSchema={
            "type": "object",
            "properties": {
                "leave_type": {
                    "type": "string",
                    "description": "Type of leave (e.g., 'Paid Time Off', 'Sick Leave', 'Vacation')",
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End date in YYYY-MM-DD format",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the leave request",
                },
            },
            "required": ["leave_type", "start_date", "end_date"],
        },
    ),
    Tool(
        name="cancel_leave_request",
        description="Cancel a pending leave request",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "integer",
                    "description": "ID of the leave request to cancel",
                }
            },
            "required": ["request_id"],
        },
    ),
    Tool(
        name="get_public_holidays",
        description="Get company public holidays for a specific year",
        inputSchema={
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Year to get holidays for (default: current year)",
                }
            },
        },
    ),
    # === Documents (DMS) ===
    Tool(
        name="get_my_documents",
        description="Get your personal HR documents (contracts, identity documents, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "Contracts", "Identity"],
                    "default": "all",
                    "description": "Filter by document category. Note: Background Checks and Offboarding Documents are restricted.",
                }
            },
        },
    ),
    Tool(
        name="get_document_categories",
        description="Get list of your available document categories/folders",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="upload_identity_document",
        description="Upload an identity document (passport, ID card, etc.) to your personal folder",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file being uploaded",
                },
                "content_base64": {
                    "type": "string",
                    "description": "Base64-encoded file content",
                },
                "document_type": {
                    "type": "string",
                    "enum": ["passport", "id_card", "driving_license", "other"],
                    "description": "Type of identity document",
                },
            },
            "required": ["filename", "content_base64", "document_type"],
        },
    ),
    Tool(
        name="download_document",
        description="Download a specific document from your personal folder",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "integer",
                    "description": "ID of the document to download",
                }
            },
            "required": ["document_id"],
        },
    ),
    Tool(
        name="get_document_details",
        description="Get detailed metadata for a specific document (without downloading content)",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "integer",
                    "description": "ID of the document",
                }
            },
            "required": ["document_id"],
        },
    ),
]

# Public fields visible when viewing other employees (standard hr.employee fields)
PUBLIC_EMPLOYEE_FIELDS = [
    "id",
    "name",
    "work_email",
    "mobile_phone",
    "work_phone",
    "department_id",
    "job_id",
    "job_title",
    "parent_id",
    "coach_id",
    "image_128",
]

# Full fields visible for own profile (standard hr.employee fields)
SELF_EMPLOYEE_FIELDS = PUBLIC_EMPLOYEE_FIELDS + [
    "private_email",
    "emergency_contact",
    "emergency_phone",
]

# --- Per-instance configuration (defaults = stock Odoo; override via configure()) ---
# Extra hr.employee fields surfaced on the self profile: output key -> Odoo field name.
EMPLOYEE_CUSTOM_FIELDS: dict[str, str] = {}

# DMS folders employees can view/upload vs. must never see.
DMS_ALLOWED_FOLDERS = ["Contracts", "Identity"]
DMS_RESTRICTED_FOLDERS = ["Background Checks", "Offboarding Documents"]


def configure(
    custom_fields: dict[str, str] | None = None,
    dms_allowed_folders: list[str] | None = None,
    dms_restricted_folders: list[str] | None = None,
) -> None:
    """Apply per-instance configuration. Call once at server startup.

    Args left as None keep their current value, so a stock Odoo deployment works
    with no configuration at all.
    """
    global EMPLOYEE_CUSTOM_FIELDS, DMS_ALLOWED_FOLDERS, DMS_RESTRICTED_FOLDERS
    if custom_fields is not None:
        EMPLOYEE_CUSTOM_FIELDS = custom_fields
    if dms_allowed_folders is not None:
        DMS_ALLOWED_FOLDERS = dms_allowed_folders
    if dms_restricted_folders is not None:
        DMS_RESTRICTED_FOLDERS = dms_restricted_folders


def _get_date_range(period: str) -> tuple[date, date]:
    """Get date range for a period."""
    today = date.today()

    if period == "today":
        return today, today
    elif period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == "this_month":
        start = today.replace(day=1)
        return start, today
    elif period == "last_month":
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    else:
        return today - timedelta(days=7), today


async def execute_employee_tool(
    name: str,
    arguments: dict[str, Any],
    odoo_client: Any,
    employee_id: int,
) -> list[TextContent]:
    """
    Execute an employee self-service tool.

    Args:
        name: Tool name
        arguments: Tool arguments
        odoo_client: Odoo client instance
        employee_id: Authenticated employee's ID (from OAuth)
    """

    # === Profile & Organization ===

    if name == "get_my_profile":
        # Standard fields plus any configured custom fields for this instance.
        fields = SELF_EMPLOYEE_FIELDS + list(EMPLOYEE_CUSTOM_FIELDS.values())
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=fields,
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        emp = employees[0]
        profile = {
            "name": emp.get("name"),
            "work_email": emp.get("work_email"),
            "mobile_phone": emp.get("mobile_phone"),
            "work_phone": emp.get("work_phone"),
            "department": emp.get("department_id", [None, None])[1] if emp.get("department_id") else None,
            "job_title": emp.get("job_title") or (emp.get("job_id", [None, None])[1] if emp.get("job_id") else None),
            "manager": emp.get("parent_id", [None, None])[1] if emp.get("parent_id") else None,
            "coach": emp.get("coach_id", [None, None])[1] if emp.get("coach_id") else None,
        }
        # Surface configured custom fields (e.g. preferred_name, division) generically.
        for out_key, odoo_field in EMPLOYEE_CUSTOM_FIELDS.items():
            profile[out_key] = emp.get(odoo_field)
        return [TextContent(type="text", text=json.dumps(profile, default=str))]

    elif name == "get_my_manager":
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["parent_id"],
        )
        if not employees or not employees[0].get("parent_id"):
            return [TextContent(type="text", text=json.dumps({"message": "No manager assigned"}))]

        manager_id = employees[0]["parent_id"][0]
        managers = await odoo_client.read(
            model="hr.employee",
            ids=[manager_id],
            fields=PUBLIC_EMPLOYEE_FIELDS,
        )

        if managers:
            mgr = managers[0]
            manager_info = {
                "name": mgr.get("name"),
                "email": mgr.get("work_email"),
                "phone": mgr.get("work_phone") or mgr.get("mobile_phone"),
                "department": mgr.get("department_id", [None, None])[1] if mgr.get("department_id") else None,
                "job_title": mgr.get("job_title"),
            }
            return [TextContent(type="text", text=json.dumps(manager_info, default=str))]

        return [TextContent(type="text", text=json.dumps({"error": "Manager not found"}))]

    elif name == "get_my_team":
        # Get my department
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["department_id"],
        )
        if not employees or not employees[0].get("department_id"):
            return [TextContent(type="text", text=json.dumps([]))]

        dept_id = employees[0]["department_id"][0]

        # Get team members in same department
        team = await odoo_client.search_read(
            model="hr.employee",
            domain=[["department_id", "=", dept_id], ["id", "!=", employee_id]],
            fields=["name", "work_email", "job_title", "parent_id"],
            limit=50,
        )

        team_list = [
            {
                "name": t.get("name"),
                "email": t.get("work_email"),
                "job_title": t.get("job_title"),
                "is_manager": t.get("parent_id", [None])[0] == employee_id if t.get("parent_id") else False,
            }
            for t in team
        ]
        return [TextContent(type="text", text=json.dumps(team_list, default=str))]

    elif name == "find_colleague":
        search_name = arguments.get("name", "")
        colleagues = await odoo_client.search_read(
            model="hr.employee",
            domain=[["name", "ilike", search_name]],
            fields=["name", "work_email", "mobile_phone", "department_id", "job_title"],
            limit=10,
        )

        result = [
            {
                "name": c.get("name"),
                "work_email": c.get("work_email"),
                "phone": c.get("mobile_phone"),
                "department": c.get("department_id", [None, None])[1] if c.get("department_id") else None,
                "job_title": c.get("job_title"),
            }
            for c in colleagues
        ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    elif name == "get_direct_reports":
        # Find employees who have this employee as their manager (parent_id)
        direct_reports = await odoo_client.search_read(
            model="hr.employee",
            domain=[["parent_id", "=", employee_id]],
            fields=["name", "work_email", "mobile_phone", "department_id", "job_title"],
            limit=50,
        )

        result = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "email": r.get("work_email"),
                "phone": r.get("mobile_phone"),
                "department": r.get("department_id", [None, None])[1] if r.get("department_id") else None,
                "job_title": r.get("job_title"),
            }
            for r in direct_reports
        ]

        return [TextContent(type="text", text=json.dumps({
            "direct_reports": result,
            "count": len(result),
            "message": "You have no direct reports" if not result else None,
        }, default=str))]

    elif name == "update_my_contact":
        import re

        # Get the fields to update
        updates = {}

        if "work_phone" in arguments and arguments["work_phone"]:
            updates["work_phone"] = arguments["work_phone"]

        if "mobile_phone" in arguments and arguments["mobile_phone"]:
            updates["mobile_phone"] = arguments["mobile_phone"]

        if "work_email" in arguments and arguments["work_email"]:
            email = arguments["work_email"]
            # Basic email validation
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                return [TextContent(type="text", text=json.dumps({"error": "Invalid email format"}))]
            updates["work_email"] = email

        if not updates:
            return [TextContent(type="text", text=json.dumps({
                "error": "No fields to update. Provide work_phone, mobile_phone, or work_email."
            }))]

        # Update the employee record
        await odoo_client.write(
            model="hr.employee",
            ids=[employee_id],
            values=updates,
        )

        # Return the updated profile
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name", "work_email", "mobile_phone", "work_phone"],
        )

        if employees:
            emp = employees[0]
            return [TextContent(type="text", text=json.dumps({
                "status": "updated",
                "updated_fields": list(updates.keys()),
                "profile": {
                    "name": emp.get("name"),
                    "work_email": emp.get("work_email"),
                    "mobile_phone": emp.get("mobile_phone"),
                    "work_phone": emp.get("work_phone"),
                },
            }, default=str))]

        return [TextContent(type="text", text=json.dumps({"status": "updated", "updated_fields": list(updates.keys())}))]

    # === Time Off / Leave ===

    elif name == "get_my_leave_balance":
        leave_type_filter = arguments.get("leave_type")
        year = arguments.get("year", date.today().year)

        # Use Odoo's native computed fields on hr.leave.type with date context
        # This matches how the Odoo Time Off Dashboard calculates balances
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"

        # Query leave types with employee and date context
        # The context params make Odoo compute balances for the specific employee and date range
        leave_types = await odoo_client.execute(
            "hr.leave.type",
            "search_read",
            [["requires_allocation", "=", "yes"]],
            fields=["id", "name", "max_leaves", "leaves_taken", "virtual_remaining_leaves"],
            context={
                "employee_id": employee_id,
                "default_employee_id": employee_id,
                "default_date_from": year_start,
                "default_date_to": year_end,
            },
        )

        balances = []
        for lt in leave_types:
            if leave_type_filter and leave_type_filter.lower() not in lt.get("name", "").lower():
                continue

            allocated = lt.get("max_leaves", 0)
            taken = lt.get("leaves_taken", 0)
            remaining = lt.get("virtual_remaining_leaves", 0)

            # Only include types with allocations
            if allocated > 0 or taken > 0:
                balances.append({
                    "leave_type": lt.get("name"),
                    "allocated": allocated,
                    "taken": taken,
                    "remaining": remaining,
                })

        leave_result = {
            "year": year,
            "balances": balances,
            "note": f"Balance as of {year}" if balances else f"No leave allocations found for {year}",
            "version": "v7-native-odoo-fields",
        }
        return [TextContent(type="text", text=json.dumps(leave_result, default=str))]

    elif name == "get_my_leave_requests":
        status_filter = arguments.get("status", "all")

        domain = [["employee_id", "=", employee_id]]
        if status_filter == "pending":
            domain.append(["state", "in", ["draft", "confirm", "validate1"]])
        elif status_filter == "approved":
            domain.append(["state", "=", "validate"])
        elif status_filter == "rejected":
            domain.append(["state", "=", "refuse"])

        requests = await odoo_client.search_read(
            model="hr.leave",
            domain=domain,
            fields=["holiday_status_id", "date_from", "date_to", "number_of_days", "state", "name"],
            limit=50,
        )

        result = [
            {
                "id": r["id"],
                "leave_type": r.get("holiday_status_id", [None, None])[1] if r.get("holiday_status_id") else None,
                "start_date": r.get("date_from"),
                "end_date": r.get("date_to"),
                "days": r.get("number_of_days"),
                "state": r.get("state"),
                "reason": r.get("name"),
            }
            for r in requests
        ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    elif name == "request_leave":
        leave_type_name = arguments["leave_type"]
        start_date = arguments["start_date"]
        end_date = arguments["end_date"]
        reason = arguments.get("reason", "")

        # Validate dates
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        if end < start:
            return [TextContent(type="text", text=json.dumps({"error": "End date must be after start date"}))]

        # Find leave type
        leave_types = await odoo_client.search_read(
            model="hr.leave.type",
            domain=[["name", "ilike", leave_type_name]],
            fields=["id", "name"],
            limit=1,
        )
        if not leave_types:
            return [TextContent(type="text", text=json.dumps({"error": f"Leave type '{leave_type_name}' not found"}))]

        leave_type_id = leave_types[0]["id"]

        # Create leave request
        leave_id = await odoo_client.create(
            model="hr.leave",
            values={
                "employee_id": employee_id,
                "holiday_status_id": leave_type_id,
                "date_from": f"{start_date} 08:00:00",
                "date_to": f"{end_date} 17:00:00",
                "name": reason,
            },
        )

        return [TextContent(type="text", text=json.dumps({
            "request_id": leave_id,
            "status": "submitted",
            "message": "Leave request submitted successfully",
        }))]

    elif name == "cancel_leave_request":
        request_id = arguments["request_id"]

        # Verify ownership
        requests = await odoo_client.search_read(
            model="hr.leave",
            domain=[["id", "=", request_id], ["employee_id", "=", employee_id]],
            fields=["state"],
            limit=1,
        )

        if not requests:
            return [TextContent(type="text", text=json.dumps({"error": "Leave request not found or not yours"}))]

        if requests[0]["state"] not in ["draft", "confirm"]:
            return [TextContent(type="text", text=json.dumps({"error": "Cannot cancel approved or refused requests"}))]

        # Cancel (unlink or set to refuse)
        await odoo_client.unlink(model="hr.leave", ids=[request_id])

        return [TextContent(type="text", text=json.dumps({"status": "cancelled", "message": "Leave request cancelled"}))]

    elif name == "get_public_holidays":
        year = arguments.get("year", date.today().year)

        # Public holidays in Odoo are stored as resource.calendar.leaves
        # with resource_id = False (global/company-wide holidays)
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        holidays = await odoo_client.search_read(
            model="resource.calendar.leaves",
            domain=[
                ["resource_id", "=", False],  # Global holidays (not employee-specific)
                ["date_from", ">=", start_date],
                ["date_to", "<=", f"{end_date} 23:59:59"],
            ],
            fields=["name", "date_from", "date_to"],
            order="date_from asc",
        )

        result = [
            {
                "name": h.get("name"),
                "date_from": h.get("date_from"),
                "date_to": h.get("date_to"),
            }
            for h in holidays
        ]

        return [TextContent(type="text", text=json.dumps({
            "year": year,
            "holidays": result,
            "count": len(result),
        }, default=str))]

    # === Documents (DMS) ===

    elif name == "get_my_documents":
        category_filter = arguments.get("category", "all")

        # First, find the employee's personal DMS directory
        # The structure is: Employee Name > Category folders
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name"],
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        employee_name = employees[0]["name"]

        # Find the employee's directory in DMS
        # Structure: HR Documents (root) > Employee Name > Category folders
        # First find the HR Documents root, then find employee folder under it
        hr_root = await odoo_client.search_read(
            model="dms.directory",
            domain=[["name", "=", "HR Documents"], ["is_root_directory", "=", True]],
            fields=["id"],
            limit=1,
        )

        if hr_root:
            # Find employee folder under HR Documents
            root_dirs = await odoo_client.search_read(
                model="dms.directory",
                domain=[["name", "=", employee_name], ["parent_id", "=", hr_root[0]["id"]]],
                fields=["id", "name"],
                limit=1,
            )
        else:
            # Fallback: try to find employee folder directly (legacy structure)
            root_dirs = await odoo_client.search_read(
                model="dms.directory",
                domain=[["name", "=", employee_name]],
                fields=["id", "name"],
                limit=1,
            )

        if not root_dirs:
            return [TextContent(type="text", text=json.dumps({
                "documents": [],
                "message": "No personal document folder found",
            }))]

        root_dir_id = root_dirs[0]["id"]

        # Find category subdirectories (excluding restricted ones)
        subdirs = await odoo_client.search_read(
            model="dms.directory",
            domain=[
                ["parent_id", "=", root_dir_id],
                ["name", "not in", DMS_RESTRICTED_FOLDERS],
            ],
            fields=["id", "name"],
        )

        # Apply category filter
        if category_filter != "all":
            subdirs = [d for d in subdirs if d["name"] == category_filter]

        subdir_ids = [d["id"] for d in subdirs]

        if not subdir_ids:
            return [TextContent(type="text", text=json.dumps({
                "documents": [],
                "message": "No accessible document folders found",
            }))]

        # Get files from allowed directories
        files = await odoo_client.search_read(
            model="dms.file",
            domain=[["directory_id", "in", subdir_ids]],
            fields=["id", "name", "directory_id", "mimetype", "size", "create_date"],
            limit=100,
        )

        # Map directory IDs to names
        dir_names = {d["id"]: d["name"] for d in subdirs}

        documents = [
            {
                "id": f["id"],
                "filename": f["name"],
                "category": dir_names.get(f["directory_id"][0] if f.get("directory_id") else None, "Unknown"),
                "mimetype": f.get("mimetype"),
                "size_bytes": f.get("size"),
                "uploaded_at": f.get("create_date"),
            }
            for f in files
        ]

        return [TextContent(type="text", text=json.dumps({
            "documents": documents,
            "total": len(documents),
        }, default=str))]

    elif name == "get_document_categories":
        # Find the employee's directory
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name"],
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        employee_name = employees[0]["name"]

        # Structure: HR Documents (root) > Employee Name > Category folders
        hr_root = await odoo_client.search_read(
            model="dms.directory",
            domain=[["name", "=", "HR Documents"], ["is_root_directory", "=", True]],
            fields=["id"],
            limit=1,
        )

        if hr_root:
            root_dirs = await odoo_client.search_read(
                model="dms.directory",
                domain=[["name", "=", employee_name], ["parent_id", "=", hr_root[0]["id"]]],
                fields=["id"],
                limit=1,
            )
        else:
            root_dirs = await odoo_client.search_read(
                model="dms.directory",
                domain=[["name", "=", employee_name]],
                fields=["id"],
                limit=1,
            )

        if not root_dirs:
            return [TextContent(type="text", text=json.dumps({
                "categories": [],
                "message": "No personal document folder found",
            }))]

        # Get accessible subdirectories
        subdirs = await odoo_client.search_read(
            model="dms.directory",
            domain=[
                ["parent_id", "=", root_dirs[0]["id"]],
                ["name", "not in", DMS_RESTRICTED_FOLDERS],
            ],
            fields=["id", "name"],
        )

        # Batch count files per directory (avoid N+1 queries)
        subdir_ids = [d["id"] for d in subdirs]
        file_counts: dict[int, int] = {dir_id: 0 for dir_id in subdir_ids}

        if subdir_ids:
            # Single query to get all files in any of the subdirectories
            files = await odoo_client.search_read(
                model="dms.file",
                domain=[["directory_id", "in", subdir_ids]],
                fields=["directory_id"],
            )
            # Count files per directory locally
            for f in files:
                dir_id = f.get("directory_id")
                if dir_id and isinstance(dir_id, list):
                    dir_id = dir_id[0]  # Many2one field returns [id, name]
                if dir_id in file_counts:
                    file_counts[dir_id] += 1

        categories = [
            {
                "name": d["name"],
                "document_count": file_counts.get(d["id"], 0),
                "can_upload": d["name"] == "Identity",  # Only Identity folder allows uploads
            }
            for d in subdirs
        ]

        return [TextContent(type="text", text=json.dumps({"categories": categories}))]

    elif name == "upload_identity_document":
        filename = arguments["filename"]
        content_base64 = arguments["content_base64"]
        document_type = arguments["document_type"]

        # Sanitize filename to prevent path traversal and injection
        safe_filename = _sanitize_filename(filename)

        # Validate base64 content and file size
        try:
            decoded = base64.b64decode(content_base64)
        except Exception:
            return [TextContent(type="text", text=json.dumps({"error": "Invalid base64 content"}))]

        if len(decoded) > MAX_UPLOAD_SIZE_BYTES:
            return [TextContent(type="text", text=json.dumps({
                "error": f"File too large: {len(decoded)} bytes exceeds maximum of {MAX_UPLOAD_SIZE_BYTES} bytes"
            }))]

        # Find employee's Identity folder
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name"],
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        employee_name = employees[0]["name"]

        root_dirs = await odoo_client.search_read(
            model="dms.directory",
            domain=[["name", "=", employee_name], ["is_root_directory", "=", True]],
            fields=["id"],
            limit=1,
        )

        if not root_dirs:
            return [TextContent(type="text", text=json.dumps({"error": "Personal folder not found"}))]

        identity_dirs = await odoo_client.search_read(
            model="dms.directory",
            domain=[["parent_id", "=", root_dirs[0]["id"]], ["name", "=", "Identity"]],
            fields=["id"],
            limit=1,
        )

        if not identity_dirs:
            return [TextContent(type="text", text=json.dumps({"error": "Identity folder not found"}))]

        # Create the file with document type prefix
        prefixed_filename = f"{document_type}_{safe_filename}"
        file_id = await odoo_client.create(
            model="dms.file",
            values={
                "name": prefixed_filename,
                "directory_id": identity_dirs[0]["id"],
                "content": content_base64,
            },
        )

        return [TextContent(type="text", text=json.dumps({
            "status": "uploaded",
            "file_id": file_id,
            "filename": prefixed_filename,
            "message": "Identity document uploaded successfully",
        }))]

    elif name == "download_document":
        document_id = arguments["document_id"]

        # Get the file and verify access
        files = await odoo_client.search_read(
            model="dms.file",
            domain=[["id", "=", document_id]],
            fields=["id", "name", "directory_id", "content", "mimetype"],
            limit=1,
        )

        if not files:
            return [TextContent(type="text", text=json.dumps({"error": "Document not found"}))]

        file = files[0]
        directory_id = file["directory_id"][0] if file.get("directory_id") else None

        # Verify this file belongs to the employee's folder
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name"],
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        employee_name = employees[0]["name"]

        # Get the directory hierarchy to verify ownership
        if directory_id:
            directory = await odoo_client.read(
                model="dms.directory",
                ids=[directory_id],
                fields=["name", "parent_id"],
            )

            if directory:
                dir_info = directory[0]
                # Check if parent is employee's root folder and not restricted
                if dir_info.get("name") in DMS_RESTRICTED_FOLDERS:
                    return [TextContent(type="text", text=json.dumps({"error": "Access denied to restricted folder"}))]

                parent_id = dir_info.get("parent_id", [None])[0] if dir_info.get("parent_id") else None
                if parent_id:
                    parent_dir = await odoo_client.read(
                        model="dms.directory",
                        ids=[parent_id],
                        fields=["name", "is_root_directory"],
                    )
                    if parent_dir and parent_dir[0].get("name") != employee_name:
                        return [TextContent(type="text", text=json.dumps({"error": "Access denied - not your document"}))]

        return [TextContent(type="text", text=json.dumps({
            "id": file["id"],
            "filename": file["name"],
            "mimetype": file.get("mimetype"),
            "content_base64": file.get("content"),
        }, default=str))]

    elif name == "get_document_details":
        document_id = arguments["document_id"]

        # Get the file metadata (without content)
        files = await odoo_client.search_read(
            model="dms.file",
            domain=[["id", "=", document_id]],
            fields=["id", "name", "directory_id", "mimetype", "size", "create_date", "create_uid", "write_date"],
            limit=1,
        )

        if not files:
            return [TextContent(type="text", text=json.dumps({"error": "Document not found"}))]

        file = files[0]
        directory_id = file["directory_id"][0] if file.get("directory_id") else None

        # Verify this file belongs to the employee's accessible folders
        employees = await odoo_client.read(
            model="hr.employee",
            ids=[employee_id],
            fields=["name"],
        )
        if not employees:
            return [TextContent(type="text", text=json.dumps({"error": "Employee not found"}))]

        employee_name = employees[0]["name"]
        category_name = None

        # Get the directory hierarchy to verify ownership and get category
        if directory_id:
            directory = await odoo_client.read(
                model="dms.directory",
                ids=[directory_id],
                fields=["name", "parent_id"],
            )

            if directory:
                dir_info = directory[0]
                category_name = dir_info.get("name")

                # Check if this is a restricted folder
                if category_name in DMS_RESTRICTED_FOLDERS:
                    return [TextContent(type="text", text=json.dumps({"error": "Access denied to restricted folder"}))]

                # Verify parent is employee's root folder
                parent_id = dir_info.get("parent_id", [None])[0] if dir_info.get("parent_id") else None
                if parent_id:
                    parent_dir = await odoo_client.read(
                        model="dms.directory",
                        ids=[parent_id],
                        fields=["name"],
                    )
                    if parent_dir and parent_dir[0].get("name") != employee_name:
                        return [TextContent(type="text", text=json.dumps({"error": "Access denied - not your document"}))]

        return [TextContent(type="text", text=json.dumps({
            "id": file["id"],
            "filename": file["name"],
            "category": category_name,
            "mimetype": file.get("mimetype"),
            "size_bytes": file.get("size"),
            "created_at": file.get("create_date"),
            "created_by": file.get("create_uid", [None, None])[1] if file.get("create_uid") else None,
            "modified_at": file.get("write_date"),
        }, default=str))]

    else:
        raise ValueError(f"Unknown employee tool: {name}")
