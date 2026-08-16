"""
Module 4 — Contract Management (Code: CTM)
Service layer — business logic other modules must call through rather
than querying ctm_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.4):
  - Retention withheld must always equal the sum of retention amounts
    deducted across all certified payment certificates for that
    contract; reconciled at every certificate approval.
  - A bond/guarantee/insurance record nearing expiry (default: 30 days)
    generates an alert; it does not block operations but is auditable
    if left unresolved.
  - Retention release follows a fixed sequence: end-of-DLP release
    cannot happen before substantial-completion release.
  - Contract amendments of type "time" and "price" update the
    Contract's completion_date / contract_value respectively, since
    CTM-10 requires completion_date to reflect approved EOTs.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.workflow import services as workflow_services
from app.modules.ctm.models import (
    Contract,
    Retention,
    AdvancePayment,
    PerformanceBond,
    Insurance,
    Guarantee,
    ContractAmendment,
)

DEFAULT_EXPIRY_ALERT_DAYS = 30


# --- Contract creation on award (CTM-01) -----------------------------------

def create_contract_on_award(tenant_id, *, tender_id, contract_number, contract_value, cbs_id=None, **kwargs):
    """
    CTM-01: creates the Contract record on award, linked to the winning
    Tender and its baseline Budget/CBS.

    This is the call that closes the loop Module 1/2 leave open: after
    calling this, the caller (typically a route orchestrating the
    "award" action) is responsible for setting
    Opportunity.contract_id via app.modules.bdc.services, since CTM does
    not reach into bdc_* tables directly (bounded-context discipline).
    """
    existing = Contract.query.filter_by(tenant_id=tenant_id, tender_id=tender_id).first()
    if existing:
        raise APIError("A contract already exists for this tender", status=409)

    contract = Contract(
        tenant_id=tenant_id,
        tender_id=tender_id,
        cbs_id=cbs_id,
        contract_number=contract_number,
        contract_value=contract_value,
        original_completion_date=kwargs.get("completion_date"),
        **kwargs,
    )
    db.session.add(contract)
    db.session.commit()
    return contract


# --- Retention (CTM-06, business rule) -------------------------------------

def apply_retention_to_certificate(retention: Retention, *, certificate_amount) -> Decimal:
    """
    Called once per certified payment (from Module 18, once it exists).
    Returns the amount withheld for this certificate and updates the
    running total, which by construction is always the reconciled sum
    of every certificate's deduction -- this is the single write path,
    so there is nothing else that could cause it to drift.
    """
    certificate_amount = Decimal(str(certificate_amount))
    withheld = (certificate_amount * retention.percentage / Decimal("100"))

    if retention.cap_amount is not None:
        remaining_capacity = retention.cap_amount - retention.amount_withheld
        withheld = min(withheld, max(remaining_capacity, Decimal("0")))

    retention.amount_withheld += withheld
    db.session.commit()
    return withheld


def release_retention(retention: Retention, *, stage: str, actor_id=None):
    """Business rule: substantial-completion release must happen before
    end-of-DLP release -- retention is released in a fixed sequence,
    mirroring how the underlying contractual mechanism actually works."""
    if stage == "substantial_completion":
        if retention.released_substantial_completion:
            raise APIError("Substantial completion retention already released", status=409)
        retention.released_substantial_completion = True
    elif stage == "end_of_dlp":
        if not retention.released_substantial_completion:
            raise APIError(
                "Cannot release end-of-DLP retention before substantial completion retention",
                status=409,
            )
        if retention.released_end_of_dlp:
            raise APIError("End-of-DLP retention already released", status=409)
        retention.released_end_of_dlp = True
    else:
        raise APIError("Invalid release stage", status=400)

    db.session.commit()
    return retention


# --- Advance payment recoupment (CTM-05) ------------------------------------

def apply_advance_recoupment_to_certificate(advance: AdvancePayment, *, certificate_amount) -> Decimal:
    """Calculates and applies the recoupment against a certified
    payment (feeds Module 18), capped at the outstanding balance so the
    contractor is never recouped more than was actually advanced."""
    certificate_amount = Decimal(str(certificate_amount))
    recoupment = certificate_amount * advance.recoupment_pct_per_certificate / Decimal("100")
    recoupment = min(recoupment, advance.outstanding_balance)

    advance.amount_recouped += recoupment
    db.session.commit()
    return recoupment


# --- Contract amendments (CTM-09, CTM-10) -----------------------------------

def _validate_amendment_fields(amendment_type, type_specific_fields):
    if amendment_type == "time":
        if not type_specific_fields.get("time_extension_days"):
            raise APIError("time_extension_days is required for a time amendment", status=400)
    elif amendment_type == "price":
        if type_specific_fields.get("price_delta") is None:
            raise APIError("price_delta is required for a price amendment", status=400)
    elif amendment_type == "scope":
        if not type_specific_fields.get("scope_change_description"):
            raise APIError("scope_change_description is required for a scope amendment", status=400)
    else:
        raise APIError("Invalid amendment type", status=400)


def _apply_amendment_effects(contract, amendment_type, type_specific_fields):
    """The actual contract mutation -- factored out so it can run
    either immediately (record_amendment, when no workflow governs
    this entity type) or deferred until a workflow reports approved
    (finalize_amendment)."""
    if amendment_type == "time":
        days = type_specific_fields.get("time_extension_days")
        base_date = contract.completion_date or contract.original_completion_date
        if base_date:
            contract.completion_date = base_date + timedelta(days=days)
    elif amendment_type == "price":
        delta = type_specific_fields.get("price_delta")
        contract.contract_value += Decimal(str(delta))
    # "scope" amendments have no direct contract-field mutation --
    # scope_change_description is the record of the change itself.


def record_amendment(contract: Contract, *, amendment_type, description, actor_id, **type_specific_fields):
    """
    Real fraud/error control found genuinely missing while wiring this
    up, not by inspection: before this, EVERY amendment self-approved
    immediately on creation (approved_by was always the same actor who
    created it, despite the field name suggesting a real second-approval
    control) -- any single user with ctm:write could change a
    contract's value or completion date alone. Now: when a tenant has
    configured and activated a Workflow Engine chain for
    ("ctm", "contract_amendment"), the amendment is created pending and
    the actual contract mutation is deferred until the workflow
    reports approved (see finalize_amendment). A tenant that has never
    configured one sees identical behavior to before this existed --
    purely additive, matching the same pattern used for PRC Purchase
    Requests.
    """
    _validate_amendment_fields(amendment_type, type_specific_fields)

    workflow = workflow_services.get_active_workflow(
        contract.tenant_id, module_name="ctm", entity_type="contract_amendment"
    )

    if workflow:
        amendment = ContractAmendment(
            tenant_id=contract.tenant_id,
            contract_id=contract.id,
            amendment_type=amendment_type,
            description=description,
            status="pending",
            **type_specific_fields,
        )
        db.session.add(amendment)
        db.session.flush()

        amount = None
        if amendment_type == "price":
            amount = abs(Decimal(str(type_specific_fields.get("price_delta") or 0)))

        workflow_services.start_workflow_instance(
            contract.tenant_id, workflow,
            module_name="ctm", entity_type="contract_amendment", entity_id=amendment.id,
            initiated_by=actor_id, amount=amount,
        )
        db.session.commit()
        return amendment

    # No workflow configured for this entity type -- exact pre-existing
    # behavior, unchanged: immediate self-approval, effects applied now.
    _apply_amendment_effects(contract, amendment_type, type_specific_fields)

    amendment = ContractAmendment(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        amendment_type=amendment_type,
        description=description,
        approved_by=actor_id,
        approved_at=datetime.now(timezone.utc),
        status="approved",
        **type_specific_fields,
    )
    db.session.add(amendment)
    db.session.commit()
    return amendment


def finalize_amendment(amendment: ContractAmendment, *, actor_id):
    """
    Applies the deferred contract mutation once the workflow governing
    this amendment reports approved -- the second half of what
    record_amendment used to do in one atomic step before a workflow
    could gate it. Mirrors the pattern PRC's approve_purchase_request
    uses: defer to the workflow while it's pending, finalize once it
    says done.
    """
    if amendment.status != "pending":
        raise APIError(f"Amendment is not pending (current status: {amendment.status})", status=409)

    from app.workflow.models import WorkflowInstance

    instance = (
        WorkflowInstance.query.filter_by(
            tenant_id=amendment.tenant_id, module_name="ctm", entity_type="contract_amendment", entity_id=amendment.id
        )
        .order_by(WorkflowInstance.created_at.desc())
        .first()
    )
    if instance and instance.status == "pending":
        raise APIError(
            "This amendment is governed by an approval workflow",
            status=409,
            detail=(
                f"Use POST /v1/workflow/instances/{instance.id}/approve "
                f"(currently at step {instance.current_step_number}), not this endpoint directly."
            ),
        )
    if instance and instance.status in ("rejected", "cancelled"):
        amendment.status = "rejected"
        db.session.commit()
        raise APIError(f"The governing approval workflow was {instance.status} for this amendment", status=409)

    contract = Contract.query.filter_by(id=amendment.contract_id, tenant_id=amendment.tenant_id).first()
    type_specific_fields = {}
    if amendment.amendment_type == "time":
        type_specific_fields["time_extension_days"] = amendment.time_extension_days
    elif amendment.amendment_type == "price":
        type_specific_fields["price_delta"] = amendment.price_delta

    _apply_amendment_effects(contract, amendment.amendment_type, type_specific_fields)

    amendment.status = "approved"
    amendment.approved_by = actor_id
    amendment.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return amendment


# --- Expiry alerts (CTM-04, CTM-07, CTM-08, business rule) ------------------

def expiring_instruments(tenant_id, *, within_days: int = DEFAULT_EXPIRY_ALERT_DAYS):
    """
    Business rule: a bond/guarantee/insurance nearing expiry (default 30
    days) generates a mandatory alert; it does not block operations but
    is auditable if left unresolved. This returns the current set for a
    scheduler (Celery beat) to turn into actual notifications and for
    the Executive Dashboard (CTM-10) to surface directly.
    """
    today = date.today()
    horizon = today + timedelta(days=within_days)

    def _due(model):
        return model.query.filter(
            model.tenant_id == tenant_id,
            model.status == "active",
            model.valid_until.isnot(None),
            model.valid_until <= horizon,
            model.valid_until >= today,
        ).all()

    return {
        "performance_bonds": _due(PerformanceBond),
        "insurances": _due(Insurance),
        "guarantees": _due(Guarantee),
    }
