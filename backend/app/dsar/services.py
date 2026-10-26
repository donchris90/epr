"""
Data Subject Access Request (DSAR) search -- SRS Section 6 / NDPA
Section 34ish territory (which specific NDPA provisions this maps to
is a legal question, not one this code answers; see
docs/DATA_PROTECTION.md's own disclaimer).

Before this existed, "find every record about this person" meant a
platform operator manually querying up to six different tables by
hand, in whichever module happened to hold the relevant data --
personal data isn't centralized in this platform, it lives wherever
the module that created it put it (BDC contacts, WFM employees, CLP
portal users, VNP portal users, internal users). This is a single
entry point across all of them, scoped to one tenant, matching on
email and/or phone.

Deliberately NOT exhaustive of every column in every table that could
ever contain a name or contact detail somewhere in free text (e.g. a
note field mentioning someone) -- it covers the fields structurally
designated to hold a person's own contact information. Extending
coverage to a newly-added module's own contact field is a one-line
addition to SEARCHABLE_MODELS below, not a new subsystem.
"""
from app.models.core import User
from app.modules.bdc.models import Client, Contact
from app.modules.wfm.models import CasualWorker
from app.modules.clp.models import ClientPortalUser
from app.modules.vnp.models import VendorPortalUser
from app.modules.scp.models import SubcontractorPortalUser


def _ci_eq(column, value):
    """Case-insensitive equality -- an email typed with different
    casing is still the same person, and a DSAR search that misses a
    record over capitalization is a real gap, not a technicality."""
    return column.ilike(value)


# Each entry: (result_key, model, {field_name: matches_email_or_phone})
# "email" fields are matched against the email query param, "phone"
# fields against the phone query param. A model can have both (BDC's
# Contact) or just one.
#
# Known gap, stated plainly rather than silently: WFM's permanent/
# contract Employee model (wfm_employees) stores a name but no email
# or phone at all -- there is genuinely nothing on that record to
# match against here. Fuzzy name matching was deliberately left out
# (unreliable, produces both false positives across unrelated people
# who share a name and false negatives for minor spelling variants) --
# a real fix would mean adding a contact-detail field to that model,
# not stretching this search to guess at names.
SEARCHABLE_MODELS = [
    ("users", User, {"email": "email"}),
    ("bdc_clients", Client, {"billing_email": "email"}),
    ("bdc_contacts", Contact, {"email": "email", "phone": "phone"}),
    ("wfm_casual_workers", CasualWorker, {"phone": "phone"}),
    ("clp_portal_users", ClientPortalUser, {"email": "email"}),
    ("vnp_portal_users", VendorPortalUser, {"email": "email"}),
    ("scp_portal_users", SubcontractorPortalUser, {"email": "email"}),
]


def search_by_identifier(tenant_id, *, email=None, phone=None):
    """
    Returns every record in this tenant whose email or phone field
    matches the given query, grouped by table. RLS still applies to
    every query here exactly as it does everywhere else -- this
    performs no bypass, it's just doing in one call what would
    otherwise be six separate ones a human has to know to run.
    """
    if not email and not phone:
        return {"query": {"email": email, "phone": phone}, "results": {}, "total_matches": 0}

    results = {}
    total = 0

    for result_key, model, field_map in SEARCHABLE_MODELS:
        conditions = []
        for field_name, matches in field_map.items():
            if matches == "email" and email:
                conditions.append(_ci_eq(getattr(model, field_name), email))
            elif matches == "phone" and phone:
                conditions.append(_ci_eq(getattr(model, field_name), phone))

        if not conditions:
            continue

        from sqlalchemy import or_

        rows = model.query.filter_by(tenant_id=tenant_id).filter(or_(*conditions)).all()
        if rows:
            results[result_key] = rows
            total += len(rows)

    return {"query": {"email": email, "phone": phone}, "results": results, "total_matches": total}


# --- Request tracking (intake) ---------------------------------------------------

from datetime import datetime, timedelta, timezone

from app.dsar.models import DSARRequest, REQUEST_STATUSES, REQUEST_TYPES, RESPONSE_DAYS
from app.extensions import db
from app.utils.errors import APIError


def create_request(tenant_id, *, user_id, request_type, subject_name, subject_email=None, subject_phone=None, details=None, received_at=None):
    if request_type not in REQUEST_TYPES:
        raise APIError("Invalid request type", status=400)
    received = received_at or datetime.now(timezone.utc)
    req = DSARRequest(
        tenant_id=tenant_id,
        request_type=request_type,
        subject_name=subject_name,
        subject_email=subject_email,
        subject_phone=subject_phone,
        details=details,
        status="open",
        received_at=received,
        due_at=received + timedelta(days=RESPONSE_DAYS),
        actions=[],
        created_by=user_id,
    )
    db.session.add(req)
    db.session.commit()
    return req


def is_overdue(req: DSARRequest, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    return req.status in ("open", "in_progress") and req.due_at < now


def update_request(req: DSARRequest, *, user_id, status=None, resolution_notes=None):
    if req.status in ("completed", "rejected"):
        raise APIError("This request has already been closed", status=409)
    if status is not None:
        if status not in REQUEST_STATUSES:
            raise APIError("Invalid status", status=400)
        if status == "rejected" and not (resolution_notes or req.resolution_notes):
            raise APIError("A reason is required to reject a request", status=400)
        req.status = status
        if status in ("completed", "rejected"):
            req.resolved_at = datetime.now(timezone.utc)
            req.resolved_by = user_id
    if resolution_notes is not None:
        req.resolution_notes = resolution_notes
    db.session.commit()
    return req


# --- Erasure (anonymisation) -----------------------------------------------------
#
# Records are anonymised rather than hard-deleted: other records (attendance,
# quotes, audit trails) reference them, and deleting the row would either fail
# or destroy business records the tenant must keep. Personal fields are
# blanked/replaced, portal access is closed and sessions invalidated.
#
# Deliberately NOT supported here: internal staff `users` (removal goes through
# the organisation user-removal flow) and `bdc_clients` (an organisation record,
# not a person).

ERASED_NAME = "[erased]"


def _erase_contact(row):
    row.name, row.email, row.phone, row.title = ERASED_NAME, None, None, None


def _erase_casual_worker(row):
    row.name, row.phone, row.id_number = ERASED_NAME, None, None


def _erase_portal_user(row, index_model, index_fk, portal_type=None):
    from app.notifications.models import Notification

    row.email = f"erased-{row.id}@erased.invalid"
    row.password_hash = None
    row.is_active = False
    if hasattr(row, "password_changed_at"):
        row.password_changed_at = datetime.now(timezone.utc)  # kills existing sessions
    index_model.query.filter(getattr(index_model, index_fk) == row.id).delete(synchronize_session=False)
    Notification.query.filter_by(tenant_id=row.tenant_id, user_id=row.id).delete(synchronize_session=False)
    if portal_type:
        from app.auth.portal_reset import PortalPasswordResetToken

        PortalPasswordResetToken.query.filter_by(portal_type=portal_type, portal_user_id=row.id).delete(synchronize_session=False)


def _erase_clp(row):
    from app.modules.clp.models import ClientPortalEmailIndex

    _erase_portal_user(row, ClientPortalEmailIndex, "client_user_id")


def _erase_vnp(row):
    from app.modules.vnp.models import VendorPortalEmailIndex

    _erase_portal_user(row, VendorPortalEmailIndex, "vendor_user_id", "vnp")


def _erase_scp(row):
    from app.modules.scp.models import SubcontractorPortalEmailIndex

    _erase_portal_user(row, SubcontractorPortalEmailIndex, "portal_user_id", "scp")


ERASABLE = {
    "bdc_contacts": (Contact, _erase_contact),
    "wfm_casual_workers": (CasualWorker, _erase_casual_worker),
    "clp_portal_users": (ClientPortalUser, _erase_clp),
    "vnp_portal_users": (VendorPortalUser, _erase_vnp),
    "scp_portal_users": (SubcontractorPortalUser, _erase_scp),
}


def erase_records(tenant_id, req: DSARRequest, *, user_id, records):
    """Anonymise the listed {table, id} records on behalf of an open
    erasure request, and log each one (ids only) on the request. All or
    nothing: an unsupported table or an unknown id aborts everything."""
    if req.request_type != "erasure":
        raise APIError("Only erasure requests can erase records", status=400)
    if req.status in ("completed", "rejected"):
        raise APIError("This request has already been closed", status=409)
    if not records:
        raise APIError("No records given", status=400)

    # Resolve everything first so a bad entry aborts before anything is touched.
    resolved = []
    for rec in records:
        table, rid = rec.get("table"), rec.get("id")
        if table not in ERASABLE:
            raise APIError(f"Erasing '{table}' records is not supported here", status=400)
        model, fn = ERASABLE[table]
        row = model.query.filter_by(id=rid, tenant_id=tenant_id).first()
        if not row:
            raise APIError(f"Record {rid} not found in {table}", status=404)
        resolved.append((table, rid, row, fn))

    now = datetime.now(timezone.utc).isoformat()
    log = list(req.actions or [])
    for table, rid, row, fn in resolved:
        fn(row)
        log.append({"table": table, "id": str(rid), "action": "anonymised", "at": now, "by": str(user_id)})

    req.actions = log
    if req.status == "open":
        req.status = "in_progress"
    db.session.commit()
    return req
