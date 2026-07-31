"""
Module 25 — AI Construction Assistant (Code: AI)
SRS Section 4.25.

A long-term differentiator layered across the entire platform:
natural-language query and document-automation capability grounded in
the tenant's own project data.

Key Data Entities (SRS 4.25): AIQueryLog, AIGeneratedReport,
AIDocumentExtractionJob -- otherwise operates as a read/generate layer
over all other modules' data, scoped strictly per tenant.

IMPORTANT SCOPE NOTE: this environment has no LLM/AI service
configured, so natural-language query PARSING (turning "why is Project
A delayed?" into a structured request) and free-text narrative
generation are genuinely out of scope for this pass -- building either
without a real model behind it would mean faking the capability with
hardcoded string matching, which would be dishonest about what the
system actually does. What IS implemented for real, and is what
AI-12's own wording describes as the mechanism underneath any future
natural-language layer ("tool-calling to retrieve structured data
rather than generating answers from unstructured guesswork"):
  - The TOOLS themselves: real functions in services.py that answer
    specific, well-defined questions by querying actual module data
    (e.g. "which projects are at risk," "which equipment is idle").
    A natural-language layer, when one exists, would call these same
    functions rather than duplicate their logic.
  - AIQueryLog: the audit trail AI-13 requires, logging every tool
    invocation and the exact context it retrieved -- built and real,
    independent of whether the query text itself came from a person
    typing a question or a future NLP layer.
  - AIDocumentExtractionJob: the full human-review-gate WORKFLOW
    (business rule: extraction never auto-commits) is real and
    enforced; the actual OCR/document-understanding step that would
    populate `extracted_data` is treated as an external input this
    module receives, not something this module performs itself.
  - AIGeneratedReport: the citation-enforcement business rule is real
    and enforced; the narrative TEXT of a report is caller-supplied
    (this module doesn't synthesize prose without an LLM), but the
    citation requirement applies regardless of who or what wrote the
    prose.

Design notes:
  - Business rule (SRS 4.25): any AI-generated figure feeding a
    financial or contractual document must cite its source
    module/transaction -- services.generate_report validates that
    every referenced figure has a corresponding citation before the
    report can be created at all.
  - Business rule (SRS 4.25): document extraction never auto-commits;
    services.commit_extraction is the only path from a job's
    extracted_data into a real target-module record, and it requires
    the job to already be in "reviewed" status (a distinct, prior,
    explicit human action) before it will run at all.
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin


EXTRACTION_TYPES = ("boq", "invoice")
EXTRACTION_STATUSES = ("pending", "extracted", "reviewed", "committed", "rejected")
REPORT_TYPES = ("cash_flow_forecast", "executive_summary", "diary_summary")


class AIQueryLog(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AI-13: every query and the exact context retrieved to answer
    it -- logged by services._log_tool_call regardless of which tool
    function was invoked, for auditability."""

    __tablename__ = "ai_query_logs"

    user_id = db.Column(UUID(as_uuid=True), nullable=True)
    tool_name = db.Column(db.String(64), nullable=False)  # e.g. "list_at_risk_projects", "list_idle_equipment"
    query_params = db.Column(JSONB, nullable=True)
    context_retrieved = db.Column(JSONB, nullable=True)  # the exact structured data returned, for audit
    queried_at = db.Column(db.DateTime(timezone=True), nullable=True)


class AIGeneratedReport(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AI-04, AI-05: business rule -- every figure cited requires a
    source. `source_citations` is validated non-empty and
    cross-checked against `content` before a report can be created at
    all (services.generate_report)."""

    __tablename__ = "ai_generated_reports"

    report_type = db.Column(db.String(32), nullable=False)
    content = db.Column(JSONB, nullable=False)  # {figure_key: value, ...} plus narrative text if supplied
    source_citations = db.Column(JSONB, nullable=False)  # {figure_key: {module, record_id}, ...}
    generated_by = db.Column(UUID(as_uuid=True), nullable=True)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.CheckConstraint(f"report_type IN {REPORT_TYPES}", name="ck_ai_report_type"),)


class AIDocumentExtractionJob(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """AI-06, AI-07: business rule -- never auto-commits. Status
    progression is strictly linear and one-way: pending -> extracted ->
    reviewed -> committed (or -> rejected from extracted/reviewed).
    `committed_record_id` is only ever set by services.commit_extraction,
    which refuses to run unless status == "reviewed"."""

    __tablename__ = "ai_document_extraction_jobs"

    source_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    extraction_type = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)

    extracted_data = db.Column(JSONB, nullable=True)  # {field: value, ...}
    confidence_scores = db.Column(JSONB, nullable=True)  # {field: 0.0-1.0, ...}
    low_confidence_fields = db.Column(JSONB, nullable=True)  # list of field names flagged for review

    reviewed_by = db.Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    corrected_data = db.Column(JSONB, nullable=True)  # reviewer's corrections, if any, layered over extracted_data

    committed_record_id = db.Column(UUID(as_uuid=True), nullable=True)
    committed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint(f"extraction_type IN {EXTRACTION_TYPES}", name="ck_ai_extraction_type"),
        db.CheckConstraint(f"status IN {EXTRACTION_STATUSES}", name="ck_ai_extraction_status"),
    )
