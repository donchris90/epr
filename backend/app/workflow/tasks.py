"""
Celery tasks for the Workflow Engine (Module 26).

Closes the "recorded, not yet enforced by a scheduler" gap on
WorkflowStep.timeout_hours / auto_escalate (see
docs/WORKFLOW_BUILDER_GAPS.md): a step's timeout becomes
WorkflowInstance.step_due_at when an instance enters it, and this task
escalates anything overdue whose step has auto_escalate on.

Same shape as app/modules/inv/tasks.py: per-tenant, tenant context set
by hand (no HTTP request to do it), and a summary dict instead of an
exception when one tenant fails.
"""
from sqlalchemy import text

from app.extensions import db, celery
from app.models.core import Tenant
from app.workflow import services as workflow_services


def _as_tenant(tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


@celery.task(name="workflow.escalate_overdue_approvals")
def escalate_overdue_approvals():
    escalated = 0
    skipped_no_target = 0
    errors = []

    for tenant in Tenant.query.all():
        try:
            _as_tenant(tenant.id)
            result = workflow_services.escalate_overdue_instances(tenant.id)
            escalated += result["escalated"]
            skipped_no_target += result["skipped_no_target"]
            errors.extend({"tenant_id": str(tenant.id), **e} for e in result["errors"])
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 -- one tenant's failure must not abort the rest
            db.session.rollback()
            errors.append({"tenant_id": str(tenant.id), "error": str(exc)})

    return {"escalated": escalated, "skipped_no_target": skipped_no_target, "errors": errors}
