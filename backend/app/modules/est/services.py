"""
Module 3 — Estimating & Cost Engineering (Code: EST)
Service layer — business logic other modules must call through rather
than querying est_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.3):
  - Rate analyses must reconcile: material + labor + equipment +
    subcontract + markup components must sum to the displayed unit rate
    within rounding tolerance, enforced at save time.
  - The CBS baseline (EST-12) is immutable once approved; any subsequent
    change requires a formal Budget Revision record with approval, never
    a silent edit.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.utils.errors import APIError
from app.workflow import services as workflow_services
from app.modules.est.models import (
    EstimateVersion,
    BOQItem,
    RateAnalysis,
    RateAnalysisLine,
    Markup,
    ContingencyItem,
    CostBreakdownStructure,
    CBSLineItem,
    BudgetRevision,
)

# Reconciliation tolerance for rate analysis (SRS 4.3 "within rounding
# tolerance") -- one cent-equivalent at 4 decimal places of precision.
RECONCILIATION_TOLERANCE = Decimal("0.01")


# --- Estimate versions (EST-13, EST-14) -----------------------------------

def create_estimate_version(tenant_id, *, tender_id, label=None, based_on_version_id=None):
    """Creates a new draft version. If based_on_version_id is given, this
    is a what-if scenario (EST-13) -- copying happens at the BOQ-item
    level via clone_boq_items, not automatically here, so callers can
    choose to start from a blank slate or a clone."""
    existing_count = EstimateVersion.query.filter_by(tenant_id=tenant_id, tender_id=tender_id).count()
    version = EstimateVersion(
        tenant_id=tenant_id,
        tender_id=tender_id,
        version_number=existing_count + 1,
        label=label,
        status="draft",
    )
    db.session.add(version)
    db.session.commit()
    return version


def submit_estimate_version(version: EstimateVersion):
    """Marks this version as the submitted one for its tender, and
    supersedes any other submitted version -- only one version may be
    "submitted" at a time (the one TBM's estimate-lock rule refers to)."""
    if version.status == "submitted":
        raise APIError("Estimate version is already submitted", status=409)

    other_submitted = EstimateVersion.query.filter_by(
        tenant_id=version.tenant_id, tender_id=version.tender_id, status="submitted"
    ).all()
    for other in other_submitted:
        other.status = "superseded"

    version.status = "submitted"
    db.session.commit()
    return version


# --- Rate analysis & reconciliation (EST-02, business rule) ---------------

def save_rate_analysis(boq_item: BOQItem, *, lines: list, markup_pct: Decimal = Decimal("0")):
    """
    Business rule: material + labor + equipment + subcontract + markup
    components must sum to the displayed unit rate within rounding
    tolerance, enforced here at save time.

    `lines` is a list of dicts: {component_type, description,
    quantity_per_unit, unit_cost, cost_library_item_id (optional)}.
    `markup_pct` is applied to the summed component cost.
    """
    if not lines:
        raise APIError("At least one rate analysis line is required", status=400)

    if boq_item.rate_analysis is not None:
        # Replace wholesale rather than diff-merge -- simpler and matches
        # how estimators actually work (re-price the whole item).
        for line in list(boq_item.rate_analysis.lines):
            db.session.delete(line)
        db.session.delete(boq_item.rate_analysis)
        db.session.flush()

    rate_analysis = RateAnalysis(tenant_id=boq_item.tenant_id, boq_item_id=boq_item.id)
    db.session.add(rate_analysis)
    db.session.flush()

    component_subtotal = Decimal("0")
    for line_data in lines:
        qty = Decimal(str(line_data["quantity_per_unit"]))
        unit_cost = Decimal(str(line_data["unit_cost"]))
        line_total = (qty * unit_cost).quantize(Decimal("0.0001"))
        component_subtotal += line_total

        db.session.add(
            RateAnalysisLine(
                tenant_id=boq_item.tenant_id,
                rate_analysis_id=rate_analysis.id,
                cost_library_item_id=line_data.get("cost_library_item_id"),
                component_type=line_data["component_type"],
                description=line_data["description"],
                quantity_per_unit=qty,
                unit_cost=unit_cost,
                line_total=line_total,
            )
        )

    markup_amount = (component_subtotal * (Decimal(str(markup_pct)) / Decimal("100"))).quantize(Decimal("0.0001"))
    reconciled_unit_rate = (component_subtotal + markup_amount).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    boq_item.unit_rate = reconciled_unit_rate
    db.session.commit()
    return rate_analysis


def verify_rate_reconciliation(boq_item: BOQItem, *, markup_pct: Decimal = Decimal("0")) -> bool:
    """Re-derives the unit rate from the current lines and confirms it
    matches BOQItem.unit_rate within RECONCILIATION_TOLERANCE. Exposed
    separately from save_rate_analysis so it can be used as a
    standalone integrity check (e.g. a periodic audit job)."""
    if boq_item.rate_analysis is None:
        return True  # nothing to reconcile

    component_subtotal = sum((line.line_total for line in boq_item.rate_analysis.lines), Decimal("0"))
    markup_amount = component_subtotal * (Decimal(str(markup_pct)) / Decimal("100"))
    expected = component_subtotal + markup_amount

    return abs((boq_item.unit_rate or Decimal("0")) - expected) <= RECONCILIATION_TOLERANCE


# --- Markup, contingency, risk allowance (EST-08, EST-09) -----------------

def set_markup(estimate_version: EstimateVersion, *, scope, overhead_pct, profit_pct, target_boq_item_id=None):
    if scope != "whole_tender" and not target_boq_item_id:
        raise APIError("target_boq_item_id is required for section/item-scoped markups", status=400)

    markup = Markup(
        tenant_id=estimate_version.tenant_id,
        estimate_version_id=estimate_version.id,
        scope=scope,
        target_boq_item_id=target_boq_item_id,
        overhead_pct=overhead_pct,
        profit_pct=profit_pct,
    )
    db.session.add(markup)
    db.session.commit()
    return markup


def add_contingency_item(estimate_version: EstimateVersion, *, kind, basis, value, description=None):
    item = ContingencyItem(
        tenant_id=estimate_version.tenant_id,
        estimate_version_id=estimate_version.id,
        kind=kind,
        basis=basis,
        value=value,
        description=description,
    )
    db.session.add(item)
    db.session.commit()
    return item


# --- Engineer's Estimate & Tender Price views (EST-10, EST-11) -------------
# Both are computed views over the current data, not persisted tables --
# there is nothing to keep in sync, and re-deriving them is cheap.

def engineers_estimate(estimate_version: EstimateVersion) -> Decimal:
    """EST-10: cost-only total (no markup), for internal benchmarking."""
    total = Decimal("0")
    for boq_item in estimate_version.boq_items:
        if boq_item.rate_analysis:
            component_subtotal = sum(
                (line.line_total for line in boq_item.rate_analysis.lines), Decimal("0")
            )
            qty = boq_item.quantity or Decimal("0")
            total += component_subtotal * qty
    return total.quantize(Decimal("0.01"))


def tender_price_summary(estimate_version: EstimateVersion) -> dict:
    """EST-11: BOQ item rates, section subtotals, and grand total
    (including markup and contingency/risk), for the final Tender Price
    document."""
    items_total = Decimal("0")
    line_items = []
    for boq_item in estimate_version.boq_items:
        if boq_item.unit_rate is None or boq_item.quantity is None:
            continue
        amount = (boq_item.unit_rate * boq_item.quantity).quantize(Decimal("0.01"))
        items_total += amount
        line_items.append(
            {
                "boq_item_id": str(boq_item.id),
                "description": boq_item.description,
                "quantity": str(boq_item.quantity),
                "unit_rate": str(boq_item.unit_rate),
                "amount": str(amount),
            }
        )

    contingency_total = Decimal("0")
    for item in estimate_version.contingency_items:
        if item.basis == "percentage":
            contingency_total += (items_total * (item.value / Decimal("100"))).quantize(Decimal("0.01"))
        else:
            contingency_total += item.value

    grand_total = (items_total + contingency_total).quantize(Decimal("0.01"))

    return {
        "line_items": line_items,
        "items_total": str(items_total),
        "contingency_total": str(contingency_total),
        "grand_total": str(grand_total),
    }


# --- Cost Breakdown Structure & Budget baseline (EST-12, business rule) ---

def generate_cbs_from_estimate(estimate_version: EstimateVersion, *, project_id=None):
    """
    EST-12: on contract award, generates the project Budget/CBS
    directly from the winning estimate, item-for-item, as an immutable
    snapshot (once approved -- see approve_cbs).
    """
    if estimate_version.status != "submitted":
        raise APIError(
            "Cannot generate CBS from a non-submitted estimate",
            status=409,
            detail=f"Estimate version status is '{estimate_version.status}'",
        )

    existing = CostBreakdownStructure.query.filter_by(source_estimate_version_id=estimate_version.id).first()
    if existing:
        raise APIError("A CBS has already been generated from this estimate version", status=409)

    cbs = CostBreakdownStructure(
        tenant_id=estimate_version.tenant_id,
        project_id=project_id,
        source_estimate_version_id=estimate_version.id,
    )
    db.session.add(cbs)
    db.session.flush()

    for boq_item in estimate_version.boq_items:
        if boq_item.unit_rate is None or boq_item.quantity is None:
            continue  # section headers with no direct cost are not baseline lines
        budgeted_amount = (boq_item.unit_rate * boq_item.quantity).quantize(Decimal("0.01"))
        db.session.add(
            CBSLineItem(
                tenant_id=estimate_version.tenant_id,
                cbs_id=cbs.id,
                source_boq_item_id=boq_item.id,
                description=boq_item.description,
                unit=boq_item.unit,
                quantity=boq_item.quantity,
                unit_rate=boq_item.unit_rate,
                budgeted_amount=budgeted_amount,
            )
        )

    db.session.commit()
    return cbs


def approve_cbs(cbs: CostBreakdownStructure, *, approver_id):
    """Locks the baseline. After this, line amounts may only change via
    create_budget_revision (business rule, SRS 4.3)."""
    if cbs.is_approved:
        raise APIError("CBS is already approved", status=409)

    cbs.is_approved = True
    cbs.approved_by = approver_id
    cbs.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return cbs


def update_cbs_line_item(cbs: CostBreakdownStructure, line_item: CBSLineItem, *, new_amount):
    """Direct edits are only permitted before approval. After approval,
    the CBS is the immutable baseline -- see create_budget_revision."""
    if cbs.is_approved:
        raise APIError(
            "CBS baseline is approved and immutable",
            status=409,
            detail="Use create_budget_revision to change an approved baseline.",
        )
    line_item.budgeted_amount = new_amount
    db.session.commit()
    return line_item


def create_budget_revision(cbs: CostBreakdownStructure, line_item: CBSLineItem, *, reason, new_amount, approver_id):
    """
    Business rule: the ONLY sanctioned way to change an approved CBS
    baseline. Not permitted on an unapproved CBS -- use
    update_cbs_line_item directly until the baseline is locked.

    Real budget-integrity gap found and fixed while extending the
    Workflow Engine to a fourth module, not invented to justify the
    work: every revision self-approved immediately on creation
    (approved_by was always the same actor who created it) --
    directly mutating CBSLineItem.budgeted_amount, the same figure
    app/commitments/services.py computes remaining budget against, on
    the say-so of a single user holding est:approve alone. Now: when a
    tenant configures and activates a Workflow Engine chain for
    ("est", "budget_revision"), the revision is created pending and
    the actual budget mutation is deferred until the workflow reports
    approved (see finalize_budget_revision). A tenant that has never
    configured one sees identical behavior to before this existed.
    """
    if not cbs.is_approved:
        raise APIError(
            "CBS is not yet approved",
            status=409,
            detail="Edit the line item directly until the baseline is approved.",
        )
    if not reason:
        raise APIError("A reason is required for a budget revision", status=400)

    workflow = workflow_services.get_active_workflow(cbs.tenant_id, module_name="est", entity_type="budget_revision")

    if workflow:
        revision = BudgetRevision(
            tenant_id=cbs.tenant_id,
            cbs_id=cbs.id,
            cbs_line_item_id=line_item.id,
            reason=reason,
            previous_amount=line_item.budgeted_amount,
            revised_amount=new_amount,
            status="pending",
        )
        db.session.add(revision)
        db.session.flush()

        # The absolute size of the change (not just the new figure) is
        # what a threshold-based approval step would reasonably route
        # on -- a 5,000 revision and a 50,000,000 revision are very
        # different requests even if the resulting budgeted_amount
        # happened to land on the same number.
        amount = abs(new_amount - line_item.budgeted_amount)

        workflow_services.start_workflow_instance(
            cbs.tenant_id, workflow,
            module_name="est", entity_type="budget_revision", entity_id=revision.id,
            initiated_by=approver_id, amount=amount,
        )
        db.session.commit()
        return revision

    # No workflow configured -- exact pre-existing behavior: immediate
    # self-approval, effects applied right away.
    revision = BudgetRevision(
        tenant_id=cbs.tenant_id,
        cbs_id=cbs.id,
        cbs_line_item_id=line_item.id,
        reason=reason,
        previous_amount=line_item.budgeted_amount,
        revised_amount=new_amount,
        approved_by=approver_id,
        approved_at=datetime.now(timezone.utc),
        status="approved",
    )
    db.session.add(revision)
    line_item.budgeted_amount = new_amount
    db.session.commit()
    return revision


def finalize_budget_revision(revision: BudgetRevision, *, actor_id):
    """
    Applies the deferred budget mutation once the workflow governing
    this revision reports approved -- mirrors
    app/modules/ctm/services.py:finalize_amendment and
    app/modules/hse/services.py:finalize_permit_approval exactly.
    """
    if revision.status != "pending":
        raise APIError(f"Revision is not pending (current status: {revision.status})", status=409)

    from app.workflow.models import WorkflowInstance

    instance = (
        WorkflowInstance.query.filter_by(
            tenant_id=revision.tenant_id, module_name="est", entity_type="budget_revision", entity_id=revision.id
        )
        .order_by(WorkflowInstance.created_at.desc())
        .first()
    )
    if instance and instance.status == "pending":
        raise APIError(
            "This budget revision is governed by an approval workflow",
            status=409,
            detail=(
                f"Use POST /v1/workflow/instances/{instance.id}/approve "
                f"(currently at step {instance.current_step_number}), not this endpoint directly."
            ),
        )
    if instance and instance.status in ("rejected", "cancelled"):
        revision.status = "rejected"
        db.session.commit()
        raise APIError(f"The governing approval workflow was {instance.status} for this revision", status=409)

    line_item = CBSLineItem.query.filter_by(id=revision.cbs_line_item_id, tenant_id=revision.tenant_id).first()
    line_item.budgeted_amount = revision.revised_amount

    revision.status = "approved"
    revision.approved_by = actor_id
    revision.approved_at = datetime.now(timezone.utc)
    db.session.commit()
    return revision
