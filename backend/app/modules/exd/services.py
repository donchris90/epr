"""
Module 21 — Executive Dashboard (Code: EXD)
Service layer.

Business rule (SRS 4.21): dashboard figures are always traceable to
source-module transactions via drill-down; nothing here is an
independently-editable stored number -- every function queries other
modules' real tables fresh and returns a `drill_down` list of the
specific source record IDs the figure was built from, so a caller can
always answer "where did this number come from."

Every function takes `tenant_id` and queries are always filtered by it
explicitly, even though the underlying tables are also RLS-protected --
this module reads across many other modules' tables directly (the one
place in this codebase where that's the correct design, see the module
docstring in models.py), so being explicit about tenant scoping here
matters even more than usual.
"""
from decimal import Decimal

from app.extensions import db


# --- Company Revenue vs Budget (EXD-01) -----------------------------------------

def get_company_revenue(tenant_id, *, company_id=None, period_start, period_end, budget_amount=None):
    """
    Actual revenue computed fresh from Module 17's posted ledger
    (credits to revenue-type accounts, net of any debits/reversals) --
    the same query shape as FIN's own generate_income_statement,
    because this IS that same fact, just displayed on a dashboard
    rather than saved as a formal statement. `budget_amount` is
    caller-supplied (a budget/target figure isn't itself a FIN ledger
    fact).
    """
    from app.modules.fin.models import JournalEntry, GeneralLedgerLine, ChartOfAccounts

    query = (
        db.session.query(GeneralLedgerLine.journal_entry_id, GeneralLedgerLine.credit_amount, GeneralLedgerLine.debit_amount)
        .join(ChartOfAccounts, GeneralLedgerLine.account_id == ChartOfAccounts.id)
        .join(JournalEntry, GeneralLedgerLine.journal_entry_id == JournalEntry.id)
        .filter(
            GeneralLedgerLine.tenant_id == tenant_id,
            ChartOfAccounts.account_type == "revenue",
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
        )
    )
    if company_id:
        query = query.filter(JournalEntry.company_id == company_id)

    rows = query.all()
    actual_revenue = sum((Decimal(credit) - Decimal(debit) for _, credit, debit in rows), Decimal("0"))
    drill_down = sorted({str(entry_id) for entry_id, _, _ in rows})

    result = {"actual_revenue": actual_revenue, "drill_down_journal_entries": drill_down}
    if budget_amount is not None:
        budget_amount = Decimal(str(budget_amount))
        result["budget_amount"] = budget_amount
        result["variance"] = actual_revenue - budget_amount
        result["variance_pct"] = (
            ((actual_revenue - budget_amount) / budget_amount * 100) if budget_amount != 0 else None
        )
    return result


# --- Active Projects: CPI/SPI (EXD-06) --------------------------------------------

def get_active_projects_performance(tenant_id):
    """Each project's MOST RECENT EVM snapshot (Module 19), the same
    latest-per-project aggregation shape as PC's own
    list_at_risk_projects, just without the threshold filter -- every
    project, not only the at-risk ones."""
    from app.modules.pc.models import EVMSnapshot

    latest_per_project = (
        db.session.query(EVMSnapshot.project_id, db.func.max(EVMSnapshot.period_end).label("latest_period"))
        .filter(EVMSnapshot.tenant_id == tenant_id)
        .group_by(EVMSnapshot.project_id)
        .subquery()
    )

    snapshots = (
        EVMSnapshot.query.join(
            latest_per_project,
            db.and_(
                EVMSnapshot.project_id == latest_per_project.c.project_id,
                EVMSnapshot.period_end == latest_per_project.c.latest_period,
            ),
        )
        .filter(EVMSnapshot.tenant_id == tenant_id)
        .all()
    )

    return [
        {
            "project_id": str(s.project_id),
            "period_end": s.period_end.isoformat(),
            "cpi": s.cpi,
            "spi": s.spi,
            "drill_down_evm_snapshot_id": str(s.id),
        }
        for s in snapshots
    ]


# --- Consolidated Project Risks (EXD-11) ------------------------------------------

def get_consolidated_project_risks(tenant_id, *, status="open"):
    """Module 19's Risk Register, ranked by exposure value -- the
    highest-exposure open risks across every project, in one list."""
    from app.modules.pc.models import RiskRegisterEntry

    risks = (
        RiskRegisterEntry.query.filter_by(tenant_id=tenant_id, status=status)
        .order_by(RiskRegisterEntry.exposure_value.desc())
        .all()
    )
    return [
        {
            "project_id": str(r.project_id),
            "description": r.description,
            "exposure_value": r.exposure_value,
            "drill_down_risk_entry_id": str(r.id),
        }
        for r in risks
    ]


# --- AR / AP Aging (EXD-08) -------------------------------------------------------

def get_ar_ap_aging_summary(tenant_id, *, as_of=None):
    """
    AR side reuses Module 18's own outstanding-invoices report (a
    cross-module SERVICE call, not a table read -- BIL already owns
    and exposes exactly this aggregation). AP side is computed here
    directly from Module 17's unpaid AccountsPayableInvoice rows, using
    the same age-band convention as BIL's report for a consistent
    dashboard.
    """
    from datetime import date
    from app.modules.bil import services as bil_services
    from app.modules.fin.models import AccountsPayableInvoice

    as_of = as_of or date.today()
    ar_bands = bil_services.get_outstanding_invoices_report(tenant_id, as_of=as_of)

    ap_bands = {"current": [], "1_30_days": [], "31_60_days": [], "61_90_days": [], "over_90_days": []}
    unpaid = AccountsPayableInvoice.query.filter_by(tenant_id=tenant_id, status="unpaid").all()
    for invoice in unpaid:
        age_days = (as_of - invoice.due_date).days if invoice.due_date else 0
        if age_days <= 0:
            band = "current"
        elif age_days <= 30:
            band = "1_30_days"
        elif age_days <= 60:
            band = "31_60_days"
        elif age_days <= 90:
            band = "61_90_days"
        else:
            band = "over_90_days"
        ap_bands[band].append(
            {
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "amount": str(invoice.amount),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            }
        )

    return {"accounts_receivable": ar_bands, "accounts_payable": ap_bands}


# --- Equipment Utilization by category (EXD-04) -----------------------------------

def get_equipment_utilization_by_category(tenant_id, *, period_start, period_end):
    """
    Module 9's Equipment doesn't have a "category" field of its own
    (it has make/model), so this groups by `ownership_type` as the
    nearest real, queryable grouping dimension -- a documented
    simplification rather than inventing a category taxonomy Module 9
    doesn't define.
    """
    from app.modules.eqp.models import Equipment, UtilizationRecord

    rows = (
        db.session.query(
            Equipment.ownership_type,
            db.func.coalesce(db.func.sum(UtilizationRecord.hours_operated), 0),
            db.func.coalesce(db.func.sum(UtilizationRecord.hours_scheduled), 0),
        )
        .join(UtilizationRecord, UtilizationRecord.equipment_id == Equipment.id)
        .filter(
            Equipment.tenant_id == tenant_id,
            UtilizationRecord.record_date >= period_start,
            UtilizationRecord.record_date <= period_end,
        )
        .group_by(Equipment.ownership_type)
        .all()
    )

    return [
        {
            "ownership_type": ownership_type,
            "hours_operated": Decimal(operated),
            "hours_scheduled": Decimal(scheduled),
            "utilization_pct": (Decimal(operated) / Decimal(scheduled) * 100) if Decimal(scheduled) > 0 else None,
        }
        for ownership_type, operated, scheduled in rows
    ]
