"""
Celery tasks for Inventory & Warehouse (Module 8).

The first actual @celery.task definitions anywhere in this codebase --
Celery has been configured (broker, result backend, ContextTask
wrapping every task in a real Flask app context) since early in this
build, but nothing was ever scheduled to run on it. This closes that
gap for the one cross-module capability that was explicitly left as
"a Celery task" in the code itself: see the docstring on
app/modules/inv/services.py:check_reorder_levels.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.extensions import db, celery
from app.models.core import Tenant
from app.modules.inv import services as inv_services
from app.modules.inv.models import MaterialItem
from app.modules.prc.models import PurchaseRequest


# How long to wait before auto-creating another draft PR for the same
# reorder level while the shortage persists. Without this, a daily (or
# more frequent) periodic run would create a new duplicate PR every
# single time it ran for as long as stock stayed below the reorder
# point -- flooding Procurement with copies of the same request rather
# than one they can act on. 7 days is a reasonable default for a
# construction-materials reorder cycle; not tuned against any
# real-world data, since none exists yet for this platform.
REORDER_PR_COOLDOWN = timedelta(days=7)


def _as_tenant(tenant_id):
    """Celery tasks run entirely outside any HTTP request, so nothing
    has set app.tenant_id the way the tenant-context middleware does
    for a real request -- this task has to do it itself, once per
    tenant, for every write it makes. Same requirement, same reason,
    as every other piece of code in this project that writes outside
    a real request (see tests/conftest.py's _as_tenant, or
    app/onboarding/services.py)."""
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


@celery.task(name="inv.check_and_create_reorder_purchase_requests")
def check_and_create_reorder_purchase_requests():
    """
    INV-05 / cross-module: for every tenant, find material items at or
    below their configured reorder point where auto_create_pr is set,
    and raise a draft Purchase Request in Procurement for each one not
    already covered by a still-fresh auto-created PR.

    Deliberately creates a DRAFT PR, never auto-submits it -- PRC-11's
    budget validation happens at submission
    (app/modules/prc/routes.py's /purchase-requests/<id>/submit), and
    this task has no basis to decide that check should be skipped just
    because the trigger was automatic. A human still has to look at
    and submit what this task raises.

    Returns a summary dict rather than raising on a single tenant's
    failure -- one tenant's bad data (e.g. a reorder level pointing at
    a material item that's since been deleted) shouldn't take down the
    check for every other tenant in the same run.
    """
    created = 0
    skipped_cooldown = 0
    errors = []

    for tenant in Tenant.query.all():
        try:
            _as_tenant(tenant.id)
            below_reorder = inv_services.check_reorder_levels(tenant.id)

            for entry in below_reorder:
                level = entry["reorder_level"]
                if not level.auto_create_pr:
                    continue

                if level.last_auto_pr_at is not None:
                    age = datetime.now(timezone.utc) - level.last_auto_pr_at
                    if age < REORDER_PR_COOLDOWN:
                        skipped_cooldown += 1
                        continue

                material_item = MaterialItem.query.filter_by(
                    tenant_id=tenant.id, id=level.material_item_id
                ).first()
                if not material_item:
                    continue

                pr = PurchaseRequest(
                    tenant_id=tenant.id,
                    description=(
                        f"Auto-generated: {material_item.code} — {material_item.description} "
                        f"below reorder point (available: {entry['available_quantity']}, "
                        f"reorder point: {level.reorder_point})"
                    ),
                    quantity=level.reorder_quantity,
                    unit=material_item.unit,
                )
                db.session.add(pr)
                level.last_auto_pr_at = datetime.now(timezone.utc)
                created += 1

            db.session.commit()
        except Exception as exc:  # noqa: BLE001 -- one tenant's failure must not abort the rest
            db.session.rollback()
            errors.append({"tenant_id": str(tenant.id), "error": str(exc)})

    return {"purchase_requests_created": created, "skipped_cooldown": skipped_cooldown, "errors": errors}
