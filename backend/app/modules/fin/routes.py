"""
Module 17 — Financial Management (Code: FIN)
SRS Section 4.17 — Flask Blueprint. Base path: /v1/fin
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.fin import services
from app.modules.fin.models import (
    Company,
    ChartOfAccounts,
    BudgetControlPolicy,
    JournalEntry,
    AccountsPayableInvoice,
    AccountsReceivableInvoice,
    BankStatementLine,
)
from app.modules.fin.schemas import (
    CompanySchema,
    ChartOfAccountsSchema,
    BudgetControlPolicyInputSchema,
    BudgetControlPolicySchema,
    CheckBudgetControlSchema,
    PostAPInvoiceSchema,
    PostARInvoiceSchema,
    InvoiceSchema,
    PostManualExceptionSchema,
    JournalEntrySchema,
    BankStatementLineInputSchema,
    BankStatementLineSchema,
    CashFlowForecastInputSchema,
    CashFlowForecastSchema,
    IncomeStatementInputSchema,
    FinancialStatementSchema,
)

bp = Blueprint("fin", __name__, url_prefix="/v1/fin")

company_schema = CompanySchema()
account_schema = ChartOfAccountsSchema()
policy_schema = BudgetControlPolicySchema()
invoice_schema = InvoiceSchema()
journal_schema = JournalEntrySchema()
bank_line_schema = BankStatementLineSchema()
cash_flow_schema = CashFlowForecastSchema()
statement_schema = FinancialStatementSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_bank_line_or_404(line_id) -> BankStatementLine:
    line = BankStatementLine.query.filter_by(id=line_id, tenant_id=g.tenant_id).first()
    if not line:
        raise APIError("Bank statement line not found", status=404)
    return line


@bp.get("/health")
def health():
    return jsonify({"module": "fin", "name": "Financial Management", "status": "ok"})


# --- Companies (FIN-12) ------------------------------------------------------------

@bp.post("/companies")
@require_permission("fin:approve")
def create_company():
    data = _load(company_schema)
    company = Company(tenant_id=g.tenant_id, **data)
    db.session.add(company)
    db.session.commit()
    return jsonify(company_schema.dump(company)), 201


@bp.get("/companies")
@require_permission("fin:read")
def list_companies():
    companies = Company.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(company_schema.dump(companies, many=True)))


# --- Chart of accounts (FIN-01) -----------------------------------------------------

@bp.post("/chart-of-accounts")
@require_permission("fin:approve")
def create_account():
    data = _load(account_schema)
    account = ChartOfAccounts(tenant_id=g.tenant_id, **data)
    db.session.add(account)
    db.session.commit()
    return jsonify(account_schema.dump(account)), 201


@bp.get("/chart-of-accounts")
@require_permission("fin:read")
def list_accounts():
    accounts = ChartOfAccounts.query.filter_by(tenant_id=g.tenant_id).all()
    return jsonify(envelope(account_schema.dump(accounts, many=True)))


# --- Budget control (FIN-04, business rule) -----------------------------------------

@bp.post("/budget-control-policies")
@require_permission("fin:approve")
def create_budget_policy():
    data = _load(BudgetControlPolicyInputSchema())
    policy = BudgetControlPolicy(tenant_id=g.tenant_id, **data)
    db.session.add(policy)
    db.session.commit()
    return jsonify(policy_schema.dump(policy)), 201


@bp.post("/budget-control/check")
@require_permission("fin:read")
def check_budget_control():
    data = _load(CheckBudgetControlSchema())
    result = services.check_budget_control(g.tenant_id, **data)
    return jsonify({k: (str(v) if k != "allowed" and k != "warning" else v) for k, v in result.items()})


# --- Accounts Payable (FIN-02) ------------------------------------------------------

@bp.post("/ap-invoices")
@require_permission("fin:write")
def post_ap_invoice():
    data = _load(PostAPInvoiceSchema())
    invoice = services.post_accounts_payable_invoice(g.tenant_id, posted_by=g.user_id, **data)
    return jsonify(invoice_schema.dump(invoice)), 201


@bp.get("/ap-invoices")
@require_permission("fin:read")
def list_ap_invoices():
    status = request.args.get("status")
    query = AccountsPayableInvoice.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    invoices = query.all()
    return jsonify(envelope(invoice_schema.dump(invoices, many=True)))


# --- Accounts Receivable (FIN-03) -----------------------------------------------------

@bp.post("/ar-invoices")
@require_permission("fin:write")
def post_ar_invoice():
    data = _load(PostARInvoiceSchema())
    invoice = services.post_accounts_receivable_invoice(g.tenant_id, posted_by=g.user_id, **data)
    return jsonify(invoice_schema.dump(invoice)), 201


@bp.get("/ar-invoices")
@require_permission("fin:read")
def list_ar_invoices():
    status = request.args.get("status")
    query = AccountsReceivableInvoice.query.filter_by(tenant_id=g.tenant_id)
    if status:
        query = query.filter_by(status=status)
    invoices = query.all()
    return jsonify(envelope(invoice_schema.dump(invoices, many=True)))


# --- Manual exception posting (business rule -- elevated permission gate) -------------
# NOTE: this is the ONLY posting route not tied to a real originating
# module, and it is gated behind `fin:manual_exception` specifically,
# a distinct grant from ordinary `fin:write` -- the same field-level
# gate pattern used for WFM's medical records and HSE's incident closure.

@bp.post("/journal-entries/manual-exception")
@require_permission("fin:manual_exception")
def post_manual_exception():
    data = _load(PostManualExceptionSchema())
    entry = services.post_manual_exception(g.tenant_id, approved_by=g.user_id, **data)
    return jsonify(journal_schema.dump(entry)), 201


@bp.get("/journal-entries")
@require_permission("fin:read")
def list_journal_entries():
    source_module = request.args.get("source_module")
    query = JournalEntry.query.filter_by(tenant_id=g.tenant_id)
    if source_module:
        query = query.filter_by(source_module=source_module)
    entries = query.all()
    return jsonify(envelope(journal_schema.dump(entries, many=True)))


# --- Project costing (FIN-10) -----------------------------------------------------------

@bp.get("/project-cost-summary")
@require_permission("fin:read")
def get_project_cost_summary():
    project_id = request.args.get("project_id")
    if not project_id:
        raise APIError("project_id query parameter is required", status=400)
    period_start = request.args.get("period_start")
    period_end = request.args.get("period_end")

    result = services.get_project_cost_summary(g.tenant_id, project_id=project_id, period_start=period_start, period_end=period_end)
    return jsonify(envelope([{"cost_code": r["cost_code"], "net_amount": str(r["net_amount"])} for r in result]))


# --- Bank reconciliation (FIN-07) ------------------------------------------------------

@bp.post("/bank-statement-lines")
@require_permission("fin:write")
def create_bank_statement_line():
    data = _load(BankStatementLineInputSchema())
    line = BankStatementLine(tenant_id=g.tenant_id, **data)
    db.session.add(line)
    db.session.commit()
    return jsonify(bank_line_schema.dump(line)), 201


@bp.post("/bank-statement-lines/<uuid:line_id>/auto-match")
@require_permission("fin:write")
def auto_match_bank_line(line_id):
    line = _get_bank_line_or_404(line_id)
    line = services.attempt_auto_match(line)
    return jsonify(bank_line_schema.dump(line))


# --- Cash flow (FIN-05) -----------------------------------------------------------------

@bp.post("/cash-flow-forecast")
@require_permission("fin:write")
def generate_cash_flow_forecast():
    data = _load(CashFlowForecastInputSchema())
    entry = services.generate_cash_flow_forecast(g.tenant_id, **data)
    return jsonify(cash_flow_schema.dump(entry)), 201


# --- Financial statements (FIN-09) -----------------------------------------------------

@bp.post("/financial-statements/income-statement")
@require_permission("fin:read")
def generate_income_statement():
    data = _load(IncomeStatementInputSchema())
    statement = services.generate_income_statement(g.tenant_id, **data)
    return jsonify(statement_schema.dump(statement)), 201
