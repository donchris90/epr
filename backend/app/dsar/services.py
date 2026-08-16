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
