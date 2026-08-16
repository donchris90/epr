"""
Module 17 — Financial Management (Code: FIN)
Service layer — business logic other modules must call through rather
than querying fin_* tables directly (SRS Section 3.3).

Business rules encoded here (SRS 4.17):
  - No transaction may post directly to the General Ledger bypassing
    its originating module. `_post_journal_entry` is intentionally
    private (leading underscore, not imported by routes.py) --
    every public entry point is tied to a real originating module or
    the explicitly-gated manual exception path.
  - Budget Control (FIN-04): hard block vs. warning, configurable per
    tenant per cost category.
  - Every journal entry must balance (sum of debits == sum of credits)
    before anything is committed -- the fundamental invariant of
    double-entry accounting, checked here, not trusted to callers.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.utils.errors import APIError
from app.modules.fin.models import (
    JournalEntry,
    GeneralLedgerLine,
    AccountsPayableInvoice,
    AccountsReceivableInvoice,
    BudgetControlPolicy,
    BankStatementLine,
    CashFlowForecastEntry,
    FinancialStatement,
    ChartOfAccounts,
    Company,
)


def _require_tenant_company(tenant_id, company_id):
    """
    A bare FK column is NOT sufficient to stop a cross-tenant reference:
    Postgres foreign-key constraint checks run with elevated internal
    privileges to enforce referential integrity and BYPASS row-level
    security, so a caller could otherwise create a journal entry
    pointing at another tenant's company_id and the FK check alone
    would happily accept it. Every posting path validates company/
    account ownership explicitly before touching the ledger.
    """
    company = Company.query.filter_by(id=company_id, tenant_id=tenant_id).first()
    if not company:
        raise APIError("Company not found", status=404)
    return company


def _require_tenant_account(tenant_id, account_id):
    account = ChartOfAccounts.query.filter_by(id=account_id, tenant_id=tenant_id).first()
    if not account:
        raise APIError("Account not found", status=404)
    return account


# --- Core double-entry posting (private -- business rule) ---------------------

def _post_journal_entry(tenant_id, *, company_id, source_module, lines, source_reference=None, description=None, entry_date=None, currency="NGN", exchange_rate=Decimal("1"), posted_by=None):
    """
    `lines` is a list of dicts: {account_id, debit_amount=0, credit_amount=0, project_id=None, cost_code=None}.
    Raises if the entry does not balance -- this is checked BEFORE any
    row is added to the session, so an unbalanced entry never touches
    the database at all, not even transiently.
    """
    if not lines:
        raise APIError("A journal entry requires at least one line", status=400)

    _require_tenant_company(tenant_id, company_id)
    for line in lines:
        _require_tenant_account(tenant_id, line["account_id"])

    total_debits = sum((Decimal(str(l.get("debit_amount", 0))) for l in lines), Decimal("0"))
    total_credits = sum((Decimal(str(l.get("credit_amount", 0))) for l in lines), Decimal("0"))

    if total_debits != total_credits:
        raise APIError(
            "Journal entry does not balance",
            status=400,
            detail=f"Total debits {total_debits} != total credits {total_credits}.",
        )
    if total_debits == 0:
        raise APIError("Journal entry has zero total value", status=400)

    entry = JournalEntry(
        tenant_id=tenant_id,
        company_id=company_id,
        entry_date=entry_date or date.today(),
        source_module=source_module,
        source_reference=source_reference,
        description=description,
        status="posted",
        posted_by=posted_by,
        posted_at=datetime.now(timezone.utc),
        currency=currency,
        exchange_rate=exchange_rate,
    )
    db.session.add(entry)
    db.session.flush()

    for line in lines:
        db.session.add(
            GeneralLedgerLine(
                tenant_id=tenant_id,
                journal_entry_id=entry.id,
                account_id=line["account_id"],
                project_id=line.get("project_id"),
                cost_code=line.get("cost_code"),
                debit_amount=Decimal(str(line.get("debit_amount", 0))),
                credit_amount=Decimal(str(line.get("credit_amount", 0))),
            )
        )

    db.session.commit()
    return entry


# --- Budget control (FIN-04, business rule) ------------------------------------

def check_budget_control(tenant_id, *, cost_code, posting_amount, cbs_budget_amount, cost_category=None):
    """
    `cost_code` (a specific CBS line item, UUID) is what the spend
    check is actually against. `cost_category` (a broader string
    classification, e.g. "materials", "labor") is what the tenant's
    enforcement-mode POLICY is keyed on, per FIN-04's own wording --
    these are deliberately not the same thing: the SRS enforces budget
    at the cost-code level but configures policy at the cost-category
    level. `cbs_budget_amount` is the total approved CBS budget for
    this cost code, supplied by the caller (Module 3 owns that figure).
    Already-spent is computed from THIS module's own ledger, which it
    does own.
    """
    already_spent = (
        db.session.query(db.func.coalesce(db.func.sum(GeneralLedgerLine.debit_amount), 0))
        .join(ChartOfAccounts, GeneralLedgerLine.account_id == ChartOfAccounts.id)
        .filter(
            GeneralLedgerLine.tenant_id == tenant_id,
            GeneralLedgerLine.cost_code == cost_code,
            ChartOfAccounts.account_type == "expense",
        )
        .scalar()
    )
    already_spent = Decimal(already_spent)
    remaining = Decimal(str(cbs_budget_amount)) - already_spent
    posting_amount = Decimal(str(posting_amount))
    would_exceed = posting_amount > remaining

    if not would_exceed:
        return {"allowed": True, "warning": False, "remaining_before": remaining}

    policy = (
        BudgetControlPolicy.query.filter_by(tenant_id=tenant_id, cost_category=cost_category).first()
        if cost_category
        else None
    ) or BudgetControlPolicy.query.filter_by(tenant_id=tenant_id, cost_category=None).first()
    enforcement_mode = policy.enforcement_mode if policy else "warning"

    if enforcement_mode == "hard_block":
        raise APIError(
            "Posting exceeds CBS budget for this cost code",
            status=409,
            detail=f"Remaining budget {remaining}, posting amount {posting_amount}.",
        )

    return {"allowed": True, "warning": True, "remaining_before": remaining}


# --- Accounts Payable (FIN-02) ---------------------------------------------------

def post_accounts_payable_invoice(
    tenant_id,
    *,
    company_id,
    source_module,
    source_reference,
    invoice_number,
    amount,
    expense_account_id,
    payable_account_id,
    counterparty_reference=None,
    currency="NGN",
    due_date=None,
    project_id=None,
    cost_code=None,
    cost_category=None,
    cbs_budget_amount=None,
    posted_by=None,
):
    """
    Dr Expense, Cr Accounts Payable. `source_module` must be a real
    originating module (e.g. "PRC" for a matched procurement invoice,
    "SUB" for a subcontract payment certificate) -- this function is
    the sanctioned entry point Module 7/12 route handlers would call,
    not something a generic route exposes for arbitrary use.
    """
    amount = Decimal(str(amount))

    if cost_code is not None and cbs_budget_amount is not None:
        check_budget_control(
            tenant_id, cost_code=cost_code, posting_amount=amount, cbs_budget_amount=cbs_budget_amount, cost_category=cost_category
        )

    entry = _post_journal_entry(
        tenant_id,
        company_id=company_id,
        source_module=source_module,
        source_reference=source_reference,
        description=f"AP invoice {invoice_number}",
        currency=currency,
        posted_by=posted_by,
        lines=[
            {"account_id": expense_account_id, "debit_amount": amount, "project_id": project_id, "cost_code": cost_code},
            {"account_id": payable_account_id, "credit_amount": amount},
        ],
    )

    invoice = AccountsPayableInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        journal_entry_id=entry.id,
        counterparty_reference=counterparty_reference,
        source_reference=source_reference,
        invoice_number=invoice_number,
        amount=amount,
        currency=currency,
        due_date=due_date,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


# --- Accounts Receivable (FIN-03) -------------------------------------------------

def post_accounts_receivable_invoice(
    tenant_id,
    *,
    company_id,
    source_module,
    source_reference,
    invoice_number,
    amount,
    receivable_account_id,
    revenue_account_id,
    client_reference=None,
    currency="NGN",
    due_date=None,
    project_id=None,
    posted_by=None,
):
    """Dr Accounts Receivable, Cr Revenue. `source_module` should be
    "BIL" (Module 18) once that module exists to call this."""
    amount = Decimal(str(amount))

    entry = _post_journal_entry(
        tenant_id,
        company_id=company_id,
        source_module=source_module,
        source_reference=source_reference,
        description=f"AR invoice {invoice_number}",
        currency=currency,
        posted_by=posted_by,
        lines=[
            {"account_id": receivable_account_id, "debit_amount": amount, "project_id": project_id},
            {"account_id": revenue_account_id, "credit_amount": amount, "project_id": project_id},
        ],
    )

    invoice = AccountsReceivableInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        journal_entry_id=entry.id,
        client_reference=client_reference,
        source_reference=source_reference,
        invoice_number=invoice_number,
        amount=amount,
        currency=currency,
        due_date=due_date,
    )
    db.session.add(invoice)
    db.session.commit()
    return invoice


# --- Manual exception (business rule -- the ONE other sanctioned path) -----------

def post_manual_exception(tenant_id, *, company_id, lines, description, approved_by, entry_date=None):
    """
    The documented exception process for postings with no real
    originating module -- gated behind the `fin:manual_exception`
    permission at the route level (elevated approval, per the business
    rule's own wording), never exposed as a general-purpose posting API.
    """
    if not description:
        raise APIError("A description is required for a manual exception posting", status=400)

    return _post_journal_entry(
        tenant_id,
        company_id=company_id,
        source_module="manual_exception",
        description=description,
        entry_date=entry_date,
        posted_by=approved_by,
        lines=lines,
    )


# --- Project costing (FIN-10) ----------------------------------------------------

def get_project_cost_summary(tenant_id, *, project_id, period_start=None, period_end=None):
    """Computed from posted ledger lines -- no separate stored table,
    same reasoning as WFM's labor cost allocation."""
    query = (
        db.session.query(GeneralLedgerLine.cost_code, db.func.sum(GeneralLedgerLine.debit_amount - GeneralLedgerLine.credit_amount))
        .join(JournalEntry, GeneralLedgerLine.journal_entry_id == JournalEntry.id)
        .filter(GeneralLedgerLine.tenant_id == tenant_id, GeneralLedgerLine.project_id == project_id)
    )
    if period_start:
        query = query.filter(JournalEntry.entry_date >= period_start)
    if period_end:
        query = query.filter(JournalEntry.entry_date <= period_end)

    rows = query.group_by(GeneralLedgerLine.cost_code).all()
    return [{"cost_code": str(cost_code) if cost_code else None, "net_amount": net} for cost_code, net in rows]


# --- Bank reconciliation (FIN-07) -----------------------------------------------

def attempt_auto_match(line: BankStatementLine):
    """
    Simple exact-amount, same-day matching against unmatched journal
    entries for the same company -- a real but intentionally modest
    auto-match strategy; anything not matched this way is left for
    manual reconciliation, which is exactly the "flagging exceptions"
    behavior FIN-07 asks for.
    """
    if line.status != "unmatched":
        raise APIError("Bank statement line is not unmatched", status=409)

    already_matched_ids = db.session.query(BankStatementLine.matched_journal_entry_id).filter(
        BankStatementLine.tenant_id == line.tenant_id, BankStatementLine.matched_journal_entry_id.isnot(None)
    )

    candidates = JournalEntry.query.filter(
        JournalEntry.tenant_id == line.tenant_id,
        JournalEntry.company_id == line.company_id,
        JournalEntry.entry_date == line.transaction_date,
        JournalEntry.id.notin_(already_matched_ids),
    ).all()

    target_amount = abs(line.amount)
    for entry in candidates:
        entry_total = sum((l.debit_amount for l in entry.lines), Decimal("0"))
        if entry_total == target_amount:
            line.matched_journal_entry_id = entry.id
            line.status = "matched"
            db.session.commit()
            return line

    line.status = "exception"
    db.session.commit()
    return line


# --- Cash flow (FIN-05) -----------------------------------------------------------

def generate_cash_flow_forecast(
    tenant_id, *, company_id, period_start, period_end, forecast_inflow=None, forecast_outflow=None, project_id=None
):
    """Actual figures computed from this module's own posted ledger
    (revenue-account credits = inflow, expense-account debits =
    outflow); forecast figures are caller-supplied estimation input."""
    inflow_query = (
        db.session.query(db.func.coalesce(db.func.sum(GeneralLedgerLine.credit_amount), 0))
        .join(ChartOfAccounts, GeneralLedgerLine.account_id == ChartOfAccounts.id)
        .join(JournalEntry, GeneralLedgerLine.journal_entry_id == JournalEntry.id)
        .filter(
            GeneralLedgerLine.tenant_id == tenant_id,
            JournalEntry.company_id == company_id,
            ChartOfAccounts.account_type == "revenue",
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
        )
    )
    outflow_query = (
        db.session.query(db.func.coalesce(db.func.sum(GeneralLedgerLine.debit_amount), 0))
        .join(ChartOfAccounts, GeneralLedgerLine.account_id == ChartOfAccounts.id)
        .join(JournalEntry, GeneralLedgerLine.journal_entry_id == JournalEntry.id)
        .filter(
            GeneralLedgerLine.tenant_id == tenant_id,
            JournalEntry.company_id == company_id,
            ChartOfAccounts.account_type == "expense",
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
        )
    )
    if project_id:
        inflow_query = inflow_query.filter(GeneralLedgerLine.project_id == project_id)
        outflow_query = outflow_query.filter(GeneralLedgerLine.project_id == project_id)

    entry = CashFlowForecastEntry(
        tenant_id=tenant_id,
        company_id=company_id,
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
        forecast_inflow=Decimal(str(forecast_inflow)) if forecast_inflow is not None else None,
        forecast_outflow=Decimal(str(forecast_outflow)) if forecast_outflow is not None else None,
        actual_inflow=Decimal(inflow_query.scalar()),
        actual_outflow=Decimal(outflow_query.scalar()),
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


# --- Financial statements (FIN-09) ------------------------------------------------

def generate_income_statement(tenant_id, *, company_id, period_start, period_end):
    """Net income = total revenue (credits - debits on revenue
    accounts) - total expense (debits - credits on expense accounts).
    `company_id=None` means consolidated across all companies (FIN-12)."""
    query = (
        db.session.query(ChartOfAccounts.account_type, db.func.sum(GeneralLedgerLine.debit_amount), db.func.sum(GeneralLedgerLine.credit_amount))
        .join(GeneralLedgerLine, GeneralLedgerLine.account_id == ChartOfAccounts.id)
        .join(JournalEntry, GeneralLedgerLine.journal_entry_id == JournalEntry.id)
        .filter(
            GeneralLedgerLine.tenant_id == tenant_id,
            ChartOfAccounts.account_type.in_(("revenue", "expense")),
            JournalEntry.entry_date >= period_start,
            JournalEntry.entry_date <= period_end,
        )
    )
    if company_id:
        query = query.filter(JournalEntry.company_id == company_id)

    totals = {"revenue": Decimal("0"), "expense": Decimal("0")}
    for account_type, debit_sum, credit_sum in query.group_by(ChartOfAccounts.account_type).all():
        debit_sum = Decimal(debit_sum or 0)
        credit_sum = Decimal(credit_sum or 0)
        totals[account_type] = (credit_sum - debit_sum) if account_type == "revenue" else (debit_sum - credit_sum)

    net_income = totals["revenue"] - totals["expense"]

    statement = FinancialStatement(
        tenant_id=tenant_id,
        company_id=company_id,
        statement_type="income_statement",
        period_start=period_start,
        period_end=period_end,
        data={"revenue": str(totals["revenue"]), "expense": str(totals["expense"]), "net_income": str(net_income)},
        generated_at=datetime.now(timezone.utc),
    )
    db.session.add(statement)
    db.session.commit()
    return statement
