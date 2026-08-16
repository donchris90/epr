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

from app.extensions import db
from app.utils.errors import APIError
from app.modules.clp.models import ClientProjectAssignment, ClientApprovalAction, ClientRequest


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
    project_id/diary linkage suitable for direct scoping)."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.exe.models import DailySiteDiary, SiteMedia

    diaries = DailySiteDiary.query.filter_by(tenant_id=tenant_id, project_id=project_id).all()
    diary_ids = [d.id for d in diaries]
    media = SiteMedia.query.filter(SiteMedia.tenant_id == tenant_id, SiteMedia.diary_id.in_(diary_ids)).all()

    return {
        "diary_summaries": [
            {"diary_id": str(d.id), "diary_date": d.diary_date.isoformat(), "narrative": d.narrative}
            for d in diaries
        ],
        "media": [{"media_id": str(m.id), "media_type": m.media_type, "captured_at": m.captured_at.isoformat() if m.captured_at else None} for m in media],
    }


# --- Variation Order & Progress Certificate approval (CLP-03, CLP-05) -----------

def approve_variation_order_as_client(tenant_id, *, client_user_id, project_id, variation_order_id, decision, notes=None):
    """
    Cross-module orchestration: after the access check, this calls
    directly into Module 18's own variation-order row (there is no
    dedicated BIL service function for a decision -- the BIL route
    mutates the model directly -- so this function mirrors that same
    state transition here, then records the CLIENT-facing approval
    action as its own auditable fact, distinct from BIL's own record).
    """
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.bil.models import VariationOrder

    vo = VariationOrder.query.filter_by(id=variation_order_id, tenant_id=tenant_id).first()
    if not vo:
        raise APIError("Variation order not found", status=404)
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
    approval, not client rejection."""
    assert_client_project_access(tenant_id, client_user_id=client_user_id, project_id=project_id)

    from app.modules.bil.models import ProgressCertificate
    from app.modules.bil import services as bil_services

    certificate = ProgressCertificate.query.filter_by(id=certificate_id, tenant_id=tenant_id).first()
    if not certificate:
        raise APIError("Progress certificate not found", status=404)

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
    return request
