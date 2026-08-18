"""
Real permission catalog for role management (Settings -> Roles).

Every code below was confirmed against an actual grep of every
@require_permission(...) call across the whole backend -- not
invented. Presented with friendly labels because the raw strings
(e.g. "hse:officer", "fin:manual_exception") are genuinely not
self-explanatory to someone who isn't reading the route code, and
this app's whole redesign this session has been toward friendlier,
easier-to-navigate -- showing 92 raw permission strings in a settings
page would undercut that.

Kept as a hand-maintained list, not scanned from the codebase at
runtime: a runtime scan would need to import every route module just
to read decorator arguments, which is slower and more fragile than a
short, reviewable list that's updated the same time a new
@require_permission(...) is added elsewhere. If this list and the
real routes drift apart, the real enforcement (require_permission
itself) is still authoritative either way -- this catalog only
controls what a role CAN be granted through the UI, never what's
actually checked at request time.
"""

MODULE_LABELS = {
    "ai": "AI Assistant",
    "ast": "Assets",
    "bdc": "Business Development",
    "bil": "Client Billing",
    "billing": "Subscription & Billing",
    "clp": "Client Portal",
    "ctm": "Contracts",
    "documents": "Documents",
    "dsar": "Data Subject Access Requests",
    "eqp": "Equipment & Fleet",
    "est": "Estimating",
    "exd": "Executive Dashboard",
    "exe": "Execution",
    "fin": "Financial Management",
    "fuel": "Fuel Management",
    "hse": "Health, Safety & Environment",
    "inv": "Inventory & Warehouse",
    "mfa": "Mobile Sync",
    "org": "Organization & Users",
    "pc": "Project Controls",
    "pln": "Planning",
    "pq": "Plant & Quarry",
    "prc": "Procurement",
    "procurement": "Procurement (legacy)",
    "projects": "Projects",
    "qms": "Quality",
    "scp": "Site Compliance",
    "sub": "Subcontractors",
    "svy": "Survey & Engineering",
    "tbm": "Tenders",
    "vnp": "Vendor Portal",
    "wfm": "Workforce",
    "workflow": "Approval Workflow",
}

ACTION_LABELS = {
    "read": "View",
    "write": "Create & Edit",
    "approve": "Approve",
    "manage": "Manage",
    "create": "Create",
    "submit": "Submit",
    "sign": "Sign off",
    "search": "Search",
    "officer": "HSE Officer actions",
    "medical": "Medical records access",
    "finance_approve": "Approve (finance)",
    "manual_exception": "Manual exceptions",
    "admin": "Administer",
}

# The real, confirmed list -- every @require_permission("...") string
# found across app/ as of this pass. See this file's own docstring on
# why this is hand-maintained rather than scanned at runtime.
ALL_PERMISSIONS = [
    "ai:approve", "ai:read", "ai:write",
    "ast:approve", "ast:read", "ast:write",
    "bdc:read", "bdc:write",
    "bil:approve", "bil:read", "bil:write",
    "billing:manage", "billing:read",
    "clp:approve", "clp:read", "clp:write",
    "ctm:approve", "ctm:read", "ctm:write",
    "documents:read", "documents:write",
    "dsar:search",
    "eqp:approve", "eqp:read", "eqp:write",
    "est:approve", "est:read", "est:write",
    "exd:approve", "exd:read",
    "exe:read", "exe:sign", "exe:write",
    "fin:approve", "fin:manual_exception", "fin:read", "fin:write",
    "fuel:approve", "fuel:read", "fuel:write",
    "hse:approve", "hse:officer", "hse:read", "hse:write",
    "inv:approve", "inv:read", "inv:write",
    "mfa:approve", "mfa:read", "mfa:write",
    "org:manage", "org:read",
    "pc:read", "pc:write",
    "pln:approve", "pln:read", "pln:write",
    "pq:approve", "pq:read", "pq:write",
    "prc:approve", "prc:read", "prc:write",
    "procurement:create",
    "projects:manage", "projects:read",
    "qms:approve", "qms:read", "qms:write",
    "scp:approve", "scp:read", "scp:write",
    "sub:approve", "sub:read", "sub:write",
    "svy:approve", "svy:read", "svy:write",
    "tbm:approve", "tbm:read", "tbm:submit", "tbm:write",
    "vnp:approve", "vnp:finance_approve", "vnp:read", "vnp:write",
    "wfm:approve", "wfm:medical", "wfm:read", "wfm:write",
    "workflow:admin", "workflow:approve",
]


def _label_for(permission: str) -> str:
    module_code, _, action = permission.partition(":")
    module_label = MODULE_LABELS.get(module_code, module_code)
    action_label = ACTION_LABELS.get(action, action.replace("_", " ").title())
    return f"{module_label} — {action_label}"


def get_permission_catalog():
    """Grouped by module, in the same order as MODULE_LABELS, for a
    real Settings -> Roles checkbox UI. Each entry is
    {code, label, module_label}."""
    groups = []
    for module_code, module_label in MODULE_LABELS.items():
        perms = [p for p in ALL_PERMISSIONS if p.startswith(f"{module_code}:")]
        if not perms:
            continue
        groups.append({
            "module_code": module_code,
            "module_label": module_label,
            "permissions": [{"code": p, "label": _label_for(p)} for p in perms],
        })
    return groups
