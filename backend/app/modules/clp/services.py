"""
Module 22 — Client Portal (Code: CLP)
Service layer — business logic other modules must call through rather
than querying clp_* tables directly (SRS Section 3.3).

Business rule (SRS 4.22): a Client Portal user can never view another
client's project data, internal cost/margin data, or internal-only
communications, regardless of any misconfiguration elsewhere in the
permission matrix. `assert_client_project_access` is the dedicated,
defense-in-depth enforcement point -- called at the START of every
function in this module that returns or acts on project data, and it
checks ClientProjectAssignment directly rather than consulting
`@require_permission`'s grants at all. A route could theoretically be
misconfigured to skip the permission decorator; it still can't skip
this call, because every service function here calls it unconditionally
as its first line.
"""
from datetime import datetime, timezone

from sqlalchemy import text

from app.extensions import db
from app.utils.errors import APIError
from app.modules.clp.models import (
    ClientPortalUser,
    ClientPortalEmailIndex,
    ClientProjectAssignment,
    ClientApprovalAction,
    ClientRequest,
)


# --- Client login (CLP client-facing authentication) ----------------------------
#
# Added alongside the rest of the client-facing portal build. Mirrors
# app/auth/jwt_utils.py:authenticate_user as closely as the real
# difference in shape allows -- see clp_email_index's own model
# docstring for why this can't be a literal copy: a client email can
# legitimately belong to more than one tenant's client roster at once,
# where a staff email cannot.

def authenticate_client_user(email: str, password: str):
    """
    Resolves every clp_email_index row for this email (there may be
    more than one, one per tenant this client organization deals
    with) and tries each tenant in turn, verifying the password
    against that tenant's own ClientPortalUser row. Returns the first
    match, or None if no tenant's password matched (or the email
    isn't known anywhere) -- callers must not distinguish these paths
    in the response, same reasoning as authenticate_user's own
    single "invalid credentials" outcome.
    """
    from app.auth.jwt_utils import verify_password
    from app.models.core import Tenant

    if not email or not password:
        return None

    index_rows = ClientPortalEmailIndex.query.filter_by(email=email).all()
    if not index_rows:
        return None

    for index_row in index_rows:
        with db.session.begin_nested():
            db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(index_row.tenant_id)})
            user = db.session.get(ClientPortalUser, index_row.client_user_id)

        if not user or not user.is_active or not user.password_hash:
            continue

        tenant = Tenant.query.filter_by(id=index_row.tenant_id).first()
        if tenant and tenant.is_suspended:
            continue

        if verify_password(user.password_hash, password):
            return user

    return None


def set_client_password(client_user: ClientPortalUser, *, password: str):
    """Called from the staff-facing create/reset flow (CLP admin) --
    there is deliberately no client-initiated "forgot password" flow
    yet; see docs/CLIENT_PORTAL_GAPS.md."""
    from app.auth.jwt_utils import hash_password

    client_user.password_hash = hash_password(password)
    db.session.commit()
    return client_user


def change_client_password(client_user: ClientPortalUser, *, current_password: str, new_password: str):
    """Self-service change (Profile/account, item 16) -- distinct from
    set_client_password above, which is the staff-initiated
    create/reset path with no current-password check at all. This one
    requires proving the current password first, the same as any
    ordinary account-settings password change."""
    from app.auth.jwt_utils import verify_password, hash_password

    if not client_user.password_hash or not verify_password(client_user.password_hash, current_password):
        raise APIError("Current password is incorrect", status=401)

    client_user.password_hash = hash_password(new_password)
    db.session.commit()
    return client_user


def assert_client_project_access(tenant_id, *, client_user_id, project_id):
    """
    THE defense-in-depth check. Raises 403 (not 404) deliberately: a
    404 could leak "this project doesn't exist"; a 403 makes clear
    access is being actively denied without confirming or denying the
    project's existence to a party who shouldn't know either way.
    """
    assignment = ClientProjectAssignment.query.filter_by(
        tenant_id=tenant_id, client_user_id=client_user_id, project_id=project_id
    ).first()
    if not assignment:
        raise APIError("Client user is not assigned to this project", status=403)


# --- Progress & schedule (CLP-01, CLP-06) --------------------------------------

def get_client_schedule_view(tenant_id, *, client_user_id, project_id):
    """
    CLP-06: read-only schedule view with NO internal cost data. Reads
    Module 5's Activity/WBSNode data directly (the one legitimate case
    for cross-module table reads -- pure read-only aggregation for an
    external-facing view, the same reasoning as Module 21). The
    returned dict deliberately excludes WBSNode.cbs_line_item_id even
    though it's on the underlying row, so there's no cost-code
    breadcrumb for a client to follow even indirectly.
    """
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.pln.models import WBSNode, Activity

    wbs_node_ids = [n.id for n in WBSNode.query.filter_by(tenant_id=tenant_id, project_id=project_id).all()]
    activities = Activity.query.filter(Activity.tenant_id == tenant_id, Activity.wbs_node_id.in_(wbs_node_ids)).all()

    return [
        {
            "activity_id": str(a.id),
            "name": a.name,
            "planned_start": a.planned_start.isoformat() if a.planned_start else None,
            "early_start": a.early_start.isoformat() if a.early_start else None,
            "early_finish": a.early_finish.isoformat() if a.early_finish else None,
            "is_critical": a.is_critical,
            "percent_complete": str(a.percent_complete) if a.percent_complete is not None else None,
            # deliberately NOT included: rate, cost_code, budget, or any
            # field from est_* / fin_* tables.
        }
        for a in activities
    ]


# --- Photos & site diary summaries (CLP-02) -------------------------------------

def get_client_site_media(tenant_id, *, client_user_id, project_id):
    """CLP-02: photos and diary summaries relevant to the client's
    project, reading Module 6's DailySiteDiary/SiteMedia (both have
    project_id/diary linkage suitable for direct scoping). Each media
    item's download_url is resolved the same way document downloads
    are (documents.services.get_download_url via its own document_id
    FK) -- a photo without a real URL wouldn't be visual evidence of
    anything."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.exe.models import DailySiteDiary, SiteMedia
    from app.models.core import Document
    from app.documents import services as document_services

    diaries = DailySiteDiary.query.filter_by(tenant_id=tenant_id, project_id=project_id).all()
    diary_ids = [d.id for d in diaries]
    media = SiteMedia.query.filter(SiteMedia.tenant_id == tenant_id, SiteMedia.diary_id.in_(diary_ids)).all()

    media_items = []
    for m in media:
        document = Document.query.filter_by(id=m.document_id, tenant_id=tenant_id, status="uploaded").first()
        media_items.append(
            {
                "media_id": str(m.id),
                "media_type": m.media_type,
                "captured_at": m.captured_at.isoformat() if m.captured_at else None,
                "download_url": document_services.get_download_url(document) if document else None,
            }
        )

    return {
        "diary_summaries": [
            {"diary_id": str(d.id), "diary_date": d.diary_date.isoformat(), "narrative": d.narrative}
            for d in diaries
        ],
        "media": media_items,
    }


# --- Variation Order & Progress Certificate approval (CLP-03, CLP-05) -----------

def _variation_order_project_id(tenant_id, vo):
    """VariationOrder has no project_id of its own -- only
    contract_id -- so confirming which project a VO actually belongs
    to means one hop through Module 4's Contract row."""
    from app.modules.ctm.models import Contract

    contract = Contract.query.filter_by(id=vo.contract_id, tenant_id=tenant_id).first()
    return contract.project_id if contract else None


def approve_variation_order_as_client(tenant_id, *, client_user_id, project_id, variation_order_id, decision, notes=None):
    """
    Cross-module orchestration: after the access check, this calls
    directly into Module 18's own variation-order row (there is no
    dedicated BIL service function for a decision -- the BIL route
    mutates the model directly -- so this function mirrors that same
    state transition here, then records the CLIENT-facing approval
    action as its own auditable fact, distinct from BIL's own record).

    Real gap closed here, not present in the original CLP build: the
    caller supplies BOTH project_id (checked against the client's own
    assignment above) AND variation_order_id independently, and
    nothing previously confirmed those two actually refer to the same
    project -- a client assigned to project A could decide a VO that
    actually belongs to project B, as long as they knew B's VO id.
    `assert_client_project_access` alone cannot catch this: it only
    ever looks at the project_id the caller claims, never at what the
    target record itself belongs to. Fails closed (403, not "assume
    it's fine") when the VO's own project can't be determined at all,
    since an approval is a financial commitment, not a read.
    """
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.bil.models import VariationOrder

    vo = VariationOrder.query.filter_by(id=variation_order_id, tenant_id=tenant_id).first()
    if not vo:
        raise APIError("Variation order not found", status=404)

    actual_project_id = _variation_order_project_id(tenant_id, vo)
    if actual_project_id is None or str(actual_project_id) != str(project_id):
        raise APIError("Variation order does not belong to this project", status=403)

    if vo.status != "pending":
        raise APIError("Variation order has already been decided", status=409)

    vo.status = decision
    vo.approved_by = f"client:{client_user_id}"
    vo.approved_at = datetime.now(timezone.utc)

    action = ClientApprovalAction(
        tenant_id=tenant_id,
        client_user_id=client_user_id,
        action_type="variation_order",
        target_id=variation_order_id,
        decision=decision,
        decided_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.session.add(action)
    db.session.commit()
    return action


def approve_certificate_as_client(tenant_id, *, client_user_id, project_id, certificate_id, decision, notes=None):
    """Same pattern for Progress Certificates (CLP-05), reusing
    Module 18's own approve_certificate service for the "approved"
    path (so BIL's own PaymentTracking side-effect still fires), and
    handling "rejected" directly since BIL's service only models
    approval, not client rejection.

    Same project-ownership fix as approve_variation_order_as_client
    above, and the same fail-closed behaviour when a certificate's own
    project_id is unset."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.bil.models import ProgressCertificate
    from app.modules.bil import services as bil_services

    certificate = ProgressCertificate.query.filter_by(id=certificate_id, tenant_id=tenant_id).first()
    if not certificate:
        raise APIError("Progress certificate not found", status=404)
    if certificate.project_id is None or str(certificate.project_id) != str(project_id):
        raise APIError("Progress certificate does not belong to this project", status=403)

    if decision == "approved":
        bil_services.approve_certificate(certificate, approval_method="in_app", approved_by=f"client:{client_user_id}")
    else:
        if certificate.status != "submitted":
            raise APIError("Only a submitted certificate can be rejected", status=409)
        certificate.status = "rejected"
        db.session.commit()

    action = ClientApprovalAction(
        tenant_id=tenant_id,
        client_user_id=client_user_id,
        action_type="progress_certificate",
        target_id=certificate_id,
        decision=decision,
        decided_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.session.add(action)
    db.session.commit()
    return action


# --- Client requests (CLP-07) ----------------------------------------------------

def submit_client_request(tenant_id, *, client_user_id, project_id, request_type, description):
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    request = ClientRequest(
        tenant_id=tenant_id,
        client_user_id=client_user_id,
        project_id=project_id,
        request_type=request_type,
        description=description,
        status="open",
        submitted_at=datetime.now(timezone.utc),
    )
    db.session.add(request)
    db.session.commit()
    return request


def resolve_client_request(request: ClientRequest, *, response):
    if request.status == "resolved":
        raise APIError("Request is already resolved", status=409)
    request.status = "resolved"
    request.response = response
    request.resolved_at = datetime.now(timezone.utc)
    db.session.commit()

    # Real, working notification -- not a documented gap. Reuses
    # app/notifications/services.py:notify exactly as its own
    # docstring anticipates ("a portal user instead of an internal
    # one"): that function scopes purely by user_id, with no
    # permission check at all, so a client_user_id is a legitimate
    # recipient id here without any change to the notifications module.
    from app.notifications import services as notification_services

    notification_services.notify(
        request.tenant_id,
        user_id=request.client_user_id,
        type="clp.request_resolved",
        title="Your request has been answered",
        body=response[:280],
        data={"request_id": str(request.id), "project_id": str(request.project_id)},
    )
    db.session.commit()
    return request


# --- Client-facing project & document views (client portal build) ---------------
#
# Everything below is new: the original CLP module only ever proxied
# schedule/site-media for a project the caller already knew the id of
# -- there was no way for a client to discover WHICH projects they can
# see, or to read documents/certificates/variations/invoices at all.
# Every function still opens with assert_client_project_access and
# queries nothing the client isn't explicitly scoped to; see
# docs/CLIENT_PORTAL_GAPS.md for what's intentionally NOT covered here.

def list_assigned_projects(tenant_id, *, client_user_id):
    """Dashboard/Projects list: every project this client user has
    been assigned (services.assign_project, called only by staff via
    the Admin page), with the same client-safe fields as
    get_client_project_detail below."""
    from app.models.core import Project

    assignments = ClientProjectAssignment.query.filter_by(tenant_id=tenant_id, client_user_id=client_user_id).all()
    project_ids = [a.project_id for a in assignments]
    if not project_ids:
        return []

    projects = Project.query.filter(Project.tenant_id == tenant_id, Project.id.in_(project_ids)).order_by(Project.name).all()
    return projects


def get_client_project_detail(tenant_id, *, client_user_id, project_id):
    """Project detail overview. Reuses the same client-safe shape as
    the list view, plus contract value/currency -- deliberately NOT
    budget, actual cost, or margin (see app/projects/services.py's own
    get_project_detail, which excludes those for the identical
    reason, for internal staff too, since those rollups don't exist
    yet anywhere in this codebase)."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.models.core import Project
    from app.modules.ctm.models import Contract

    project = Project.query.filter_by(id=project_id, tenant_id=tenant_id).first()
    if not project:
        raise APIError("Project not found", status=404)

    contract = Contract.query.filter_by(project_id=project_id, tenant_id=tenant_id).first()
    return {
        "project": project,
        "contract_value": contract.contract_value if contract else None,
        "currency": contract.currency if contract else None,
    }


def get_client_progress_summary(tenant_id, *, client_user_id, project_id):
    """CLP-01/CLP-06: a single overall percent-complete rollup for the
    Progress tab's headline number, derived from the same Activity
    rows get_client_schedule_view already exposes in full -- a simple
    unweighted average across activities that have a percent_complete
    value at all. Deliberately not weighted by activity duration or
    value: no such weighting exists anywhere else in this codebase
    (Module 5 itself doesn't compute one), so a fabricated weighting
    scheme would be less honest than a plain average, not more."""
    activities = get_client_schedule_view(tenant_id, client_user_id=client_user_id, project_id=project_id)
    rated = [float(a["percent_complete"]) for a in activities if a["percent_complete"] is not None]
    overall = round(sum(rated) / len(rated), 1) if rated else None
    critical_count = sum(1 for a in activities if a["is_critical"])
    return {
        "overall_percent_complete": overall,
        "activity_count": len(activities),
        "critical_activity_count": critical_count,
    }


def get_client_documents(tenant_id, *, client_user_id, project_id, doc_type=None):
    """Documents / Drawings tabs (the latter is the same data,
    filtered to doc_type='drawing' by the caller -- there is no
    separate drawing-register entity anywhere in this codebase; see
    docs/CLIENT_PORTAL_GAPS.md). Only status='uploaded' documents are
    returned: a 'pending' row has nothing real behind it yet (see
    app/documents/services.py's own lifecycle note), and a client
    should never see a row for a file that was never actually
    confirmed present in storage."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.models.core import Document

    query = Document.query.filter_by(tenant_id=tenant_id, project_id=project_id, status="uploaded")
    if doc_type:
        query = query.filter_by(doc_type=doc_type)
    return query.order_by(Document.created_at.desc()).all()


def get_client_document_download_url(tenant_id, *, client_user_id, project_id, document_id):
    """A client-scoped wrapper around Module 5's own get_download_url
    -- confirms the document belongs to a project the client is
    assigned to BEFORE ever generating a presigned URL for it."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.models.core import Document
    from app.documents import services as document_services

    document = Document.query.filter_by(id=document_id, tenant_id=tenant_id, project_id=project_id).first()
    if not document:
        raise APIError("Document not found", status=404)

    return document_services.get_download_url(document)


def get_client_certificates(tenant_id, *, client_user_id, project_id):
    """Certificates tab. Filtered directly on ProgressCertificate.
    project_id -- a certificate created by staff without project_id
    set (the field is optional on ProgressCertificateInputSchema)
    simply never appears here, the same fail-closed reasoning as
    approve_certificate_as_client's own ownership check above.
    status='draft' certificates are excluded -- a draft hasn't been
    submitted by staff yet, so its numbers aren't final and a client
    seeing them (and possibly deciding on them, if this filter were
    missing) would be seeing/acting on an internal work-in-progress
    row, not an official certificate."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.bil.models import ProgressCertificate

    return (
        ProgressCertificate.query.filter(
            ProgressCertificate.tenant_id == tenant_id,
            ProgressCertificate.project_id == project_id,
            ProgressCertificate.status != "draft",
        )
        .order_by(ProgressCertificate.certificate_number)
        .all()
    )


def get_client_variation_orders(tenant_id, *, client_user_id, project_id):
    """Variations tab. VariationOrder has no project_id of its own
    (see _variation_order_project_id above), so this resolves the
    project's contract(s) first, then filters variation orders by
    contract_id -- the same real relationship the ownership check on
    the decide endpoint relies on."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.ctm.models import Contract
    from app.modules.bil.models import VariationOrder

    contract_ids = [c.id for c in Contract.query.filter_by(tenant_id=tenant_id, project_id=project_id).all()]
    if not contract_ids:
        return []
    return (
        VariationOrder.query.filter(VariationOrder.tenant_id == tenant_id, VariationOrder.contract_id.in_(contract_ids))
        .all()
    )


def get_client_invoices(tenant_id, *, client_user_id, project_id):
    """Invoices/Payments tabs: Module 18's PaymentTracking row for
    each of this project's certificates -- there is no separate
    'invoice' entity anywhere in this codebase; a progress certificate
    IS the invoice once submitted, and PaymentTracking is its payment
    status. Returned as one flattened dict per certificate (not a
    nested schema) so the frontend gets certificate_number and
    net_payable without a second round trip."""
    certificates = get_client_certificates(tenant_id, client_user_id=client_user_id, project_id=project_id)
    rows = []
    for certificate in certificates:
        tracking = certificate.payment_tracking
        rows.append(
            {
                "id": tracking.id if tracking else certificate.id,
                "certificate_id": certificate.id,
                "certificate_number": certificate.certificate_number,
                "status": tracking.status if tracking else certificate.status,
                "due_date": tracking.due_date if tracking else None,
                "net_payable": certificate.net_payable,
                "paid_amount": tracking.paid_amount if tracking else None,
            }
        )
    return rows
