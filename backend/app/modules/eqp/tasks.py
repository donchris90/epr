"""
Celery tasks for Equipment & Fleet (Module 9).

Closes a real, previously-documented gap: approve_transfer's own
comment said a future-dated cost-allocation cutover was "intentionally
left for a scheduler to apply on that date... this module has no
Celery task wired up yet." A same-day approval always applied its
cutover immediately; anything future-dated just sat there, approved,
forever, until a human noticed and did something about it manually --
nothing ever came back to actually move the equipment's cost
allocation on the date everyone had agreed it should move.
"""
from app.extensions import db, celery
from app.models.core import Tenant
from app.modules.eqp import services as eqp_services
from sqlalchemy import text


def _as_tenant(tenant_id):
    """Same requirement as every other piece of code in this project
    that writes outside a real HTTP request -- see
    app/modules/inv/tasks.py's identical helper for the full
    explanation."""
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


@celery.task(name="eqp.apply_due_transfer_cutovers")
def apply_due_transfer_cutovers():
    """
    EQP-12: for every tenant, find approved equipment transfers whose
    cutover_date has arrived but whose cost-allocation effect hasn't
    been applied yet, and apply it.

    Idempotent by construction, not just by convention: applying a
    cutover sets cutover_applied_at, and due_unapplied_transfer_cutovers
    only ever returns transfers where that's still null -- running this
    task twice in the same day, or accidentally overlapping with
    itself, can't double-apply the same transfer.

    Returns a summary dict rather than raising on a single tenant's
    failure, matching app/modules/inv/tasks.py's established pattern:
    one tenant's bad data shouldn't take down the run for every other
    tenant in the same pass.
    """
    applied = 0
    errors = []

    for tenant in Tenant.query.all():
        try:
            _as_tenant(tenant.id)
            due = eqp_services.due_unapplied_transfer_cutovers(tenant.id)

            for transfer in due:
                eqp_services.apply_transfer_cutover(transfer)
                applied += 1

            db.session.commit()
        except Exception as exc:  # noqa: BLE001 -- one tenant's failure must not abort the rest
            db.session.rollback()
            errors.append({"tenant_id": str(tenant.id), "error": str(exc)})

    return {"cutovers_applied": applied, "errors": errors}
