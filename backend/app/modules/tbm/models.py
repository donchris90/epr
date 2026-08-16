"""
Module 2 — Tender & Bid Management (Code: TBM)
SRS Section 4.2.

Manages the full tendering process for opportunities that pass the
Bid/No-Bid gate (Module 1): registering the tender, ingesting the
client's BOQ, managing clarifications/RFIs, and tracking submission.

Key Data Entities (SRS 4.2): Tender, TenderBOQItem, ScopeItem,
BidDocument, RFI, Clarification, ApprovalStep (implements
ApprovalWorkflow), TenderChecklistItem, Submission, JVPartner (for
TBM-11 Joint Venture apportionment).

Win/Loss analysis (TBM-10) deliberately does NOT duplicate BDC's
WinLossRecord table — a Tender always has a linked Opportunity, and
TBM's win/loss service delegates to app.modules.bdc.services rather than
querying or writing bdc_* tables directly (bounded-context discipline,
SRS Section 3.3).
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


TENDER_STATUSES = ("draft", "in_estimate", "in_approval", "submitted", "awarded", "lost")
BID_DOCUMENT_TYPES = (
    "technical_proposal",
    "financial_proposal",
    "bid_bond",
    "power_of_attorney",
    "certification",
    "other",
)
RFI_STATUSES = ("open", "answered", "overdue")
APPROVAL_STEP_STATUSES = ("pending", "approved", "rejected")
SUBMISSION_METHODS = ("portal", "email", "hand_delivery", "courier")
SCOPE_ANNOTATION_TYPES = ("clarifying_note", "assumption", "exclusion")


class Tender(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """TBM-01: Tender registration."""

    __tablename__ = "tbm_tenders"

    opportunity_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)  # bdc_opportunities.id
    reference_number = db.Column(db.String(128), nullable=False)
    client_id = db.Column(UUID(as_uuid=True), nullable=True)  # bdc_clients.id
    consultant_id = db.Column(UUID(as_uuid=True), nullable=True)  # bdc_consultants.id

    submission_deadline = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    bid_bond_required = db.Column(db.Boolean, nullable=False, default=False)
    bid_bond_amount = db.Column(db.Numeric(18, 4), nullable=True)
    tender_fee = db.Column(db.Numeric(18, 4), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="NGN")

    status = db.Column(db.String(32), nullable=False, default="draft", index=True)
    is_joint_venture = db.Column(db.Boolean, nullable=False, default=False)

    # Business rule: estimate (Module 3) is locked once the Bid Approval
    # Workflow is initiated (TBM-07 / business rule in SRS 4.2).
    estimate_locked = db.Column(db.Boolean, nullable=False, default=False)
    estimate_locked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reopen_count = db.Column(db.Integer, nullable=False, default=0)
    last_reopen_reason = db.Column(db.Text, nullable=True)

    boq_items = relationship("TenderBOQItem", back_populates="tender", cascade="all, delete-orphan")
    bid_documents = relationship("BidDocument", back_populates="tender", cascade="all, delete-orphan")
    rfis = relationship("RFI", back_populates="tender", cascade="all, delete-orphan")
    clarifications = relationship("Clarification", back_populates="tender", cascade="all, delete-orphan")
    approval_steps = relationship(
        "ApprovalStep", back_populates="tender", order_by="ApprovalStep.step_order", cascade="all, delete-orphan"
    )
    checklist_items = relationship("TenderChecklistItem", back_populates="tender", cascade="all, delete-orphan")
    jv_partners = relationship("JVPartner", back_populates="tender", cascade="all, delete-orphan")
    submission = relationship("Submission", back_populates="tender", uselist=False)

    __table_args__ = (
        db.CheckConstraint(f"status IN {TENDER_STATUSES}", name="ck_tbm_tenders_status"),
        db.UniqueConstraint("tenant_id", "reference_number", name="uq_tbm_tenders_tenant_reference"),
        db.Index("ix_tbm_tenders_tenant_deadline", "tenant_id", "submission_deadline"),
    )


class TenderBOQItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-02: client-issued BOQ, imported from Excel/CSV/PDF. Hierarchical
    via self-referencing parent_id (section / sub-section / item), per the
    same structuring convention used by Module 3's BOQItem (EST-01)."""

    __tablename__ = "tbm_tender_boq_items"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tender_boq_items.id"), nullable=True, index=True)

    item_code = db.Column(db.String(64), nullable=True)
    description = db.Column(db.Text, nullable=False)
    unit = db.Column(db.String(32), nullable=True)
    quantity = db.Column(db.Numeric(18, 4), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    tender = relationship("Tender", back_populates="boq_items")
    scope_annotations = relationship("ScopeItem", back_populates="boq_item", cascade="all, delete-orphan")


class ScopeItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-03: Scope Analysis annotations (clarifying notes, assumptions,
    exclusions) on a BOQ item, made before pricing."""

    __tablename__ = "tbm_scope_items"

    tender_boq_item_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("tbm_tender_boq_items.id"), nullable=False, index=True
    )
    annotation_type = db.Column(db.String(32), nullable=False)
    text = db.Column(db.Text, nullable=False)

    boq_item = relationship("TenderBOQItem", back_populates="scope_annotations")

    __table_args__ = (
        db.CheckConstraint(f"annotation_type IN {SCOPE_ANNOTATION_TYPES}", name="ck_tbm_scope_items_type"),
    )


class BidDocument(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-04: Bid document repository with a completeness checklist
    (paired with TenderChecklistItem for the sign-off gate)."""

    __tablename__ = "tbm_bid_documents"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    doc_type = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="pending")  # pending|uploaded|verified

    tender = relationship("Tender", back_populates="bid_documents")

    __table_args__ = (db.CheckConstraint(f"doc_type IN {BID_DOCUMENT_TYPES}", name="ck_tbm_bid_documents_type"),)


class RFI(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-05: Requests for Information to the client/consultant."""

    __tablename__ = "tbm_rfis"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    related_boq_item_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tender_boq_items.id"), nullable=True)

    question = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime(timezone=True), nullable=True)
    response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="open")

    tender = relationship("Tender", back_populates="rfis")

    __table_args__ = (db.CheckConstraint(f"status IN {RFI_STATUSES}", name="ck_tbm_rfis_status"),)


class Clarification(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-06: Client-issued addenda. Business rule: every addendum must
    be acknowledged before submission sign-off (enforced in services.py)."""

    __tablename__ = "tbm_clarifications"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    addendum_number = db.Column(db.String(32), nullable=False)
    description = db.Column(db.Text, nullable=False)
    issued_at = db.Column(db.DateTime(timezone=True), nullable=True)

    acknowledged = db.Column(db.Boolean, nullable=False, default=False)
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)
    acknowledged_by = db.Column(UUID(as_uuid=True), nullable=True)

    affected_boq_item_ids = db.Column(JSONB, nullable=True)  # list of TenderBOQItem UUIDs, as strings
    requires_reestimate = db.Column(db.Boolean, nullable=False, default=False)

    tender = relationship("Tender", back_populates="clarifications")


class ApprovalStep(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-07: one step of the configurable Bid Approval Workflow
    (e.g. Estimator -> Commercial Manager -> Managing Director)."""

    __tablename__ = "tbm_approval_steps"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    role_required = db.Column(db.String(128), nullable=False)  # e.g. "commercial_manager"
    approver_id = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    comments = db.Column(db.Text, nullable=True)

    tender = relationship("Tender", back_populates="approval_steps")

    __table_args__ = (
        db.CheckConstraint(f"status IN {APPROVAL_STEP_STATUSES}", name="ck_tbm_approval_steps_status"),
        db.UniqueConstraint("tender_id", "step_order", name="uq_tbm_approval_steps_tender_order"),
    )


class TenderChecklistItem(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-08: configurable completeness checklist gating submission."""

    __tablename__ = "tbm_tender_checklist_items"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    label = db.Column(db.String(255), nullable=False)
    is_mandatory = db.Column(db.Boolean, nullable=False, default=True)
    is_complete = db.Column(db.Boolean, nullable=False, default=False)
    completed_by = db.Column(UUID(as_uuid=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    tender = relationship("Tender", back_populates="checklist_items")


class Submission(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-09: submission record. One-to-one with Tender — a tender is
    submitted at most once (a resubmission after a query is modeled as a
    new Clarification + re-opened checklist, not a second Submission)."""

    __tablename__ = "tbm_submissions"

    tender_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, unique=True, index=True
    )
    method = db.Column(db.String(16), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False)
    receipt_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)
    acknowledgment_reference = db.Column(db.String(255), nullable=True)

    tender = relationship("Tender", back_populates="submission")

    __table_args__ = (db.CheckConstraint(f"method IN {SUBMISSION_METHODS}", name="ck_tbm_submissions_method"),)


class JVPartner(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """TBM-11: Joint Venture / Consortium partner apportionment."""

    __tablename__ = "tbm_jv_partners"

    tender_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tbm_tenders.id"), nullable=False, index=True)
    partner_name = db.Column(db.String(255), nullable=False)
    scope_share_pct = db.Column(db.Numeric(5, 2), nullable=False)
    financial_share_pct = db.Column(db.Numeric(5, 2), nullable=False)

    tender = relationship("Tender", back_populates="jv_partners")

    __table_args__ = (
        db.CheckConstraint(
            "scope_share_pct >= 0 AND scope_share_pct <= 100", name="ck_tbm_jv_partners_scope_share_range"
        ),
        db.CheckConstraint(
            "financial_share_pct >= 0 AND financial_share_pct <= 100",
            name="ck_tbm_jv_partners_financial_share_range",
        ),
    )
