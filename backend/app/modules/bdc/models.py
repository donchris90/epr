"""
Module 1 — Business Development & CRM (Code: BDC)
SRS Section 4.1.

Manages the company's pipeline before a project exists as a contract:
leads, client relationships, opportunities, and the tender calendar that
feeds Module 2 (Tender & Bid Management).

Key Data Entities (SRS 4.1): Lead, Client, Contact, Opportunity,
Competitor, Consultant, GovernmentAgency, Proposal, Document (Document
is defined centrally in app/models/core.py since it's shared platform-wide).
"""
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TenantMixin, AuditMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin


# --- Enumerated / configurable value sets -----------------------------
# Stored as plain strings (not Postgres ENUMs) so tenants can configure
# pipeline stages per BDC-03 without a schema migration.

LEAD_STATUSES = ("open", "converted", "archived")
OPPORTUNITY_STAGES = ("identified", "qualified", "bid_no_bid", "submitted", "won", "lost")
BID_NO_BID_DECISIONS = ("bid", "no_bid")


class Client(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """BDC-02: Client database with company details, contact persons,
    billing information, and historical project relationship."""

    __tablename__ = "bdc_clients"

    name = db.Column(db.String(255), nullable=False)
    billing_address = db.Column(db.Text, nullable=True)
    billing_email = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    contacts = relationship("Contact", back_populates="client", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="client")

    __table_args__ = (db.Index("ix_bdc_clients_tenant_name", "tenant_id", "name"),)


class Contact(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """A contact person at a Client, Consultant, or Government Agency."""

    __tablename__ = "bdc_contacts"

    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_clients.id"), nullable=True, index=True)
    consultant_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_consultants.id"), nullable=True, index=True)
    government_agency_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("bdc_government_agencies.id"), nullable=True, index=True
    )

    name = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(128), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(64), nullable=True)

    client = relationship("Client", back_populates="contacts")


class Lead(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """BDC-01: Lead records with source, estimated value, and probability."""

    __tablename__ = "bdc_leads"

    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_clients.id"), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(128), nullable=True)
    estimated_value = db.Column(db.Numeric(18, 4), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    probability_pct = db.Column(db.Numeric(5, 2), nullable=True)  # 0.00-100.00
    status = db.Column(db.String(32), nullable=False, default="open")

    __table_args__ = (
        db.CheckConstraint(f"status IN {LEAD_STATUSES}", name="ck_bdc_leads_status"),
        db.CheckConstraint(
            "probability_pct IS NULL OR (probability_pct >= 0 AND probability_pct <= 100)",
            name="ck_bdc_leads_probability_range",
        ),
    )


class Opportunity(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """BDC-03: Opportunities tracked through configurable pipeline stages
    (Identified -> Qualified -> Bid/No-Bid -> Submitted -> Won/Lost).

    Business rule (SRS 4.1): cannot transition to "won" without a linked
    Contract record (Module 4) -- enforced in services.py, not here, since
    the DB layer can't see Module 4's tables directly (bounded-context
    discipline, SRS 3.3).
    """

    __tablename__ = "bdc_opportunities"

    lead_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_leads.id"), nullable=True, index=True)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_clients.id"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    stage = db.Column(db.String(32), nullable=False, default="identified", index=True)
    estimated_value = db.Column(db.Numeric(18, 4), nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="NGN")

    # BDC-05: Bid/No-Bid decision workflow
    bid_no_bid_decision = db.Column(db.String(16), nullable=True)
    bid_no_bid_scorecard = db.Column(JSONB, nullable=True)  # {criterion: score, ...}
    bid_no_bid_rationale = db.Column(db.Text, nullable=True)
    bid_no_bid_approver_id = db.Column(UUID(as_uuid=True), nullable=True)
    bid_no_bid_decided_at = db.Column(db.DateTime(timezone=True), nullable=True)
    no_bid_reason_code = db.Column(db.String(64), nullable=True)  # required when decision == "no_bid"

    # Set once BDC-03 stage reaches "won" and a Module 4 Contract exists.
    contract_id = db.Column(UUID(as_uuid=True), nullable=True)

    # BDC-04: tender calendar deadline (mirrors the linked Module 2 Tender
    # once one exists; nullable pre-tender)
    submission_deadline = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    client = relationship("Client", back_populates="opportunities")

    __table_args__ = (
        db.CheckConstraint(f"stage IN {OPPORTUNITY_STAGES}", name="ck_bdc_opportunities_stage"),
        db.CheckConstraint(
            f"bid_no_bid_decision IS NULL OR bid_no_bid_decision IN {BID_NO_BID_DECISIONS}",
            name="ck_bdc_opportunities_decision",
        ),
        db.Index("ix_bdc_opportunities_tenant_deadline", "tenant_id", "submission_deadline"),
    )


class Competitor(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BDC-06: Competitor organizations and historical win rates on
    tracked tenders, where data is available."""

    __tablename__ = "bdc_competitors"

    name = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    # Denormalized rollup, recalculated by services.py from win/loss records
    # rather than edited directly (traceability principle, SRS 9.1).
    known_win_count = db.Column(db.Integer, nullable=False, default=0)
    known_loss_count = db.Column(db.Integer, nullable=False, default=0)


class Consultant(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BDC-07: Consultants (engineers, architects, project managers
    acting for clients) with historical relationship notes."""

    __tablename__ = "bdc_consultants"

    name = db.Column(db.String(255), nullable=False)
    discipline = db.Column(db.String(128), nullable=True)  # e.g. "structural", "PM"
    relationship_notes = db.Column(db.Text, nullable=True)

    contacts = relationship("Contact", backref="consultant")


class GovernmentAgency(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """BDC-08: Government agencies including procurement contacts and
    historical tender patterns."""

    __tablename__ = "bdc_government_agencies"

    name = db.Column(db.String(255), nullable=False)
    jurisdiction = db.Column(db.String(128), nullable=True)
    tender_pattern_notes = db.Column(db.Text, nullable=True)

    contacts = relationship("Contact", backref="government_agency")


class Proposal(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, SoftDeleteMixin):
    """BDC-09: Proposal creation with template-based document generation,
    merging company credentials, past project references, and CVs of
    proposed key staff."""

    __tablename__ = "bdc_proposals"

    opportunity_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_opportunities.id"), nullable=False, index=True)
    template_key = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="draft")
    generated_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey("documents.id"), nullable=True)

    opportunity = relationship("Opportunity")


class WinLossRecord(db.Model, UUIDPrimaryKeyMixin, TenantMixin, AuditMixin):
    """Backs BDC-11 (Win/Loss reports) and BDC-06 (competitor win-rate
    tracking). One row per resolved (won/lost) Opportunity."""

    __tablename__ = "bdc_win_loss_records"

    opportunity_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("bdc_opportunities.id"), nullable=False, unique=True, index=True
    )
    outcome = db.Column(db.String(8), nullable=False)  # "won" | "lost"
    winning_price = db.Column(db.Numeric(18, 4), nullable=True)  # if disclosed
    competitor_id = db.Column(UUID(as_uuid=True), db.ForeignKey("bdc_competitors.id"), nullable=True)
    reason_code = db.Column(db.String(64), nullable=True)  # required on loss
    sector = db.Column(db.String(128), nullable=True)
    value_band = db.Column(db.String(32), nullable=True)  # for BDC-11 reporting buckets

    __table_args__ = (db.CheckConstraint("outcome IN ('won','lost')", name="ck_bdc_winloss_outcome"),)
