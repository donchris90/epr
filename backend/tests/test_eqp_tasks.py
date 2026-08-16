"""
Tests for app/modules/eqp/tasks.py -- the Celery task implementing
the cost-allocation cutover that approve_transfer's own comment left
as "intentionally left for a scheduler... this module has no Celery
task wired up yet" for any future-dated equipment transfer.

Calls the task directly as a plain function, matching the established
pattern in test_inv_tasks.py -- celery.Task's ContextTask override
(app/celery_app.py) wraps every call in a real Flask app context
already, so this runs the real task body synchronously, no running
worker required.

Assertions after the task runs use raw SQL rather than ORM queries --
the task does its own per-tenant SET LOCAL + commit cycles internally
(the same requirement documented in app/modules/inv/tasks.py's
_as_tenant), and re-querying via the ORM afterward hit an identity-map
subtlety unrelated to the feature under test. Raw SQL with an explicit
tenant_id filter in the WHERE clause is simpler and more direct for
what these assertions actually need to check.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import text

from app.modules.eqp.tasks import apply_due_transfer_cutovers


def _as_tenant(db, tenant_id):
    db.session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})


def _seed_transfer(db, tenant_id, *, cutover_date, status="approved", cutover_applied_at=None):
    from app.modules.eqp.models import Equipment, EquipmentTransfer

    _as_tenant(db, tenant_id)
    from_project = uuid.uuid4()
    to_project = uuid.uuid4()
    equip = Equipment(tenant_id=tenant_id, name="Test Excavator", current_project_id=from_project)
    db.session.add(equip)
    db.session.flush()

    transfer = EquipmentTransfer(
        tenant_id=tenant_id, equipment_id=equip.id, from_project_id=from_project, to_project_id=to_project,
        status=status, cutover_date=cutover_date, cutover_applied_at=cutover_applied_at,
    )
    db.session.add(transfer)
    db.session.flush()
    equip_id, transfer_id = equip.id, transfer.id
    db.session.commit()
    return equip_id, transfer_id, to_project


def _current_project_id(db, tenant_id, equip_id):
    _as_tenant(db, tenant_id)
    row = db.session.execute(
        text("SELECT current_project_id FROM eqp_equipment WHERE id = :id"), {"id": str(equip_id)}
    ).first()
    return row[0]


def _cutover_applied_at(db, tenant_id, transfer_id):
    _as_tenant(db, tenant_id)
    row = db.session.execute(
        text("SELECT cutover_applied_at FROM eqp_equipment_transfers WHERE id = :id"), {"id": str(transfer_id)}
    ).first()
    return row[0]


class TestApplyDueTransferCutovers:
    def test_applies_a_due_unapplied_cutover(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        equip_id, transfer_id, to_project = _seed_transfer(db, tenant, cutover_date=date.today())

        result = apply_due_transfer_cutovers()
        assert result["cutovers_applied"] == 1
        assert result["errors"] == []

        assert str(_current_project_id(db, tenant, equip_id)) == str(to_project)
        assert _cutover_applied_at(db, tenant, transfer_id) is not None

    def test_does_not_apply_a_future_dated_cutover(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        equip_id, transfer_id, to_project = _seed_transfer(db, tenant, cutover_date=date.today() + timedelta(days=5))

        result = apply_due_transfer_cutovers()
        assert result["cutovers_applied"] == 0
        assert str(_current_project_id(db, tenant, equip_id)) != str(to_project)

    def test_does_not_reapply_an_already_applied_cutover(self, app, db, seed_tenants):
        """The real idempotency guarantee: cutover_applied_at being
        set is what stops a second run from acting on the same
        transfer again."""
        tenant = seed_tenants["a"]
        _seed_transfer(db, tenant, cutover_date=date.today(), cutover_applied_at=date.today())

        result = apply_due_transfer_cutovers()
        assert result["cutovers_applied"] == 0

    def test_running_twice_is_safe_and_idempotent(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        _seed_transfer(db, tenant, cutover_date=date.today())

        first = apply_due_transfer_cutovers()
        second = apply_due_transfer_cutovers()

        assert first["cutovers_applied"] == 1
        assert second["cutovers_applied"] == 0

    def test_does_not_apply_a_pending_not_yet_approved_transfer(self, app, db, seed_tenants):
        tenant = seed_tenants["a"]
        equip_id, transfer_id, to_project = _seed_transfer(db, tenant, cutover_date=date.today(), status="pending")

        result = apply_due_transfer_cutovers()
        assert result["cutovers_applied"] == 0
        assert str(_current_project_id(db, tenant, equip_id)) != str(to_project)

    def test_cross_tenant_isolation(self, app, db, seed_tenants):
        _seed_transfer(db, seed_tenants["a"], cutover_date=date.today())
        _seed_transfer(db, seed_tenants["b"], cutover_date=date.today())

        result = apply_due_transfer_cutovers()
        assert result["cutovers_applied"] == 2  # one per tenant, correctly isolated
        assert result["errors"] == []
