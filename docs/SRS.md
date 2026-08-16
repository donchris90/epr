# Table of Contents {#table-of-contents .TOC-Heading}

# Document Control

  -----------------------------------------------------------------------
  Field                               Value
  ----------------------------------- -----------------------------------
  Document Title                      SiteForge Construction Management
                                      Platform --- Software Requirements
                                      Specification

  Version                             1.0

  Status                              Draft for Development

  Prepared For                        Engineering, Product, and QA Teams

  Document Type                       Software Requirements Specification
                                      (SRS), IEEE 830 / ISO 29148
                                      informed

  Classification                      Internal --- Product Blueprint
  -----------------------------------------------------------------------

## Revision History

  -----------------------------------------------------------------------
  Version           Date              Description       Author
  ----------------- ----------------- ----------------- -----------------
  0.1               Draft             Initial concept   Product Team
                                      and module        
                                      outline           

  1.0               Current           Full functional,  Engineering &
                                      data, API, UX,    Product
                                      and delivery      
                                      specification     
  -----------------------------------------------------------------------

## Purpose of This Document

This Software Requirements Specification (SRS) defines the complete
functional and non-functional requirements for **SiteForge**, a
multi-tenant, cloud-based Construction Management Platform purpose-built
for civil engineering and building contractors, consultants, and asset
owners operating primarily in African markets. It is written to a level
of detail sufficient for a development team to design, build, test, and
deploy the system without requiring further product discovery for the
scope defined herein.

This document supersedes informal notes, pitch decks, or verbal
descriptions of the product. Where a conflict exists between this SRS
and any other artifact, this document governs unless formally revised.

# 1. Introduction

## 1.1 Purpose

SiteForge exists to replace the fragmented toolset that construction
companies typically operate with --- spreadsheets for costing, a generic
accounting package for finance, WhatsApp for site communication, paper
diaries for daily records, and a patchwork of point solutions for
equipment, fuel, and workforce tracking. Instead of building "another
ERP," SiteForge organizes the product around the **lifecycle of a
construction project** --- from the moment a tender is identified
through to asset handover and long-term maintenance --- with a full ERP
(finance, procurement, inventory, HR/payroll) embedded as the
operational backbone rather than as the product's organizing principle.

## 1.2 Scope

SiteForge is a Software-as-a-Service (SaaS) platform, deployable as a
multi-tenant cloud service or as a single-tenant private deployment for
large clients. The platform covers:

-   Business development and CRM for pre-tender activity
-   Tender and bid management
-   Estimating and cost engineering
-   Contract management
-   Project planning and scheduling
-   Field execution (daily site diaries, inspections, pour records)
-   Procurement and vendor management
-   Inventory and warehouse management across yards, sites, and quarries
-   Equipment and fleet management, including fuel management
-   Workforce management, including casual labor and subcontractor labor
-   Subcontractor management
-   Quality management (QMS)
-   Health, Safety & Environment (HSE)
-   Survey and engineering data
-   Plant and quarry production (crushers, asphalt plants, concrete
    batching)
-   Financial management (full general ledger and project costing)
-   Client billing (progress certificates, variations, retention)
-   Project controls (earned value management, forecasting)
-   Asset management post-handover
-   Executive reporting
-   Client and vendor self-service portals
-   An offline-first mobile field application
-   An AI Construction Assistant layered across all of the above

Out of scope for this version: payroll tax compliance for jurisdictions
outside the initial target markets (configurable but not pre-loaded),
BIM/3D model authoring (SiteForge consumes BIM outputs but does not
author them), and hardware/IoT firmware for equipment sensors (SiteForge
integrates via standard telemetry protocols but does not manufacture
devices).

## 1.3 Intended Audience

-   **Engineering teams** --- as the primary blueprint for backend,
    frontend, and mobile implementation.
-   **QA and test engineering** --- to derive test plans and acceptance
    criteria.
-   **Product management** --- as the reference for scope control and
    roadmap sequencing.
-   **DevOps/Infrastructure** --- for deployment topology and
    environment planning.
-   **Prospective enterprise clients and implementation partners** ---
    as a statement of platform capability during evaluation.

## 1.4 Definitions, Acronyms, and Abbreviations

  -----------------------------------------------------------------------
  Term                                Definition
  ----------------------------------- -----------------------------------
  BOQ                                 Bill of Quantities

  WBS                                 Work Breakdown Structure

  CBS                                 Cost Breakdown Structure

  EVM                                 Earned Value Management

  PV / EV / AC                        Planned Value / Earned Value /
                                      Actual Cost

  CPI / SPI                           Cost Performance Index / Schedule
                                      Performance Index

  RFI                                 Request for Information

  RFQ                                 Request for Quotation

  GRN                                 Goods Receipt Note

  NCR                                 Non-Conformance Report

  ITP                                 Inspection and Test Plan

  PTW                                 Permit to Work

  DLP                                 Defects Liability Period

  SLA                                 Service Level Agreement

  RBAC                                Role-Based Access Control

  RLS                                 Row-Level Security

  MVP                                 Minimum Viable Product

  Tenant                              A single contracting company (and
                                      its projects/users) operating
                                      within the multi-tenant platform
  -----------------------------------------------------------------------

## 1.5 References

-   IEEE 830-1998 Recommended Practice for Software Requirements
    Specifications (structural reference only)
-   ISO/IEC/IEEE 29148:2018 Systems and software engineering --- Life
    cycle processes --- Requirements engineering
-   PMI Practice Standard for Earned Value Management
-   FIDIC Conditions of Contract (as a general reference model for
    contract data structures; SiteForge does not enforce any single
    contract form)

## 1.6 Document Overview

Section 2 describes the product at a high level. Section 3 defines the
technical architecture. Section 4 contains the detailed functional
requirements for all 25 platform modules. Section 5 defines the database
schema and entity relationships. Section 6 defines API contracts.
Section 7 defines UI/UX specifications and page-level flows. Section 8
defines the permission matrix. Section 9 defines cross-cutting business
rules. Section 10 defines non-functional requirements. Section 11
defines the development roadmap. Section 12 defines testing
requirements. Section 13 defines deployment architecture. Appendices
follow.

# 2. Overall Description

## 2.1 Product Perspective

SiteForge is a new, independent product. It is not an add-on to an
existing accounting package, and it is not organized around departmental
silos (finance, HR, procurement) as most ERPs are. Instead, its
information architecture mirrors the actual sequence of events in a
construction business:

    Tender → Estimate → Win Contract → Planning → Execution → Procurement →
    Materials → Equipment → Labor → Quality → Safety → Finance →
    Progress Monitoring → Client Billing → Project Closeout → Asset Management

Every module writes into a shared project data model, so that a single
BOQ line item, for example, is traceable from the original estimate
through procurement, site consumption, and client billing without
re-entry. This traceability is the platform's central design principle
and the primary justification for building a unified platform rather
than integrating point solutions.

## 2.2 Product Functions (Summary)

At a high level, SiteForge allows a contracting company to:

1.  Identify, evaluate, and bid on tenders.
2.  Build detailed, defensible cost estimates and convert winning bids
    into contracts.
3.  Plan projects using WBS-based schedules with critical path analysis.
4.  Run daily field operations --- diaries, inspections, pours, photos
    --- from mobile devices, online or offline.
5.  Procure materials and services against approved budgets, with full
    vendor lifecycle management.
6.  Track materials and equipment across multiple yards, sites, and
    quarries, including fuel.
7.  Manage a mixed workforce of permanent employees, casual labor, and
    subcontractors.
8.  Enforce quality and safety processes with auditable records.
9.  Run a full project-costed general ledger and produce client billing
    (progress certificates, variations).
10. Monitor project performance using earned value management and
    forecast outcomes.
11. Hand over completed assets and manage them through their operational
    life.
12. Give executives, clients, and vendors self-service visibility
    appropriate to their role.
13. Use an AI assistant to query project data in natural language and to
    automate document-heavy tasks (BOQ extraction, invoice capture,
    report generation).

## 2.3 User Classes and Characteristics

  -----------------------------------------------------------------------
  User Class              Description             Primary Interface
  ----------------------- ----------------------- -----------------------
  Executive / Director    Owns company-wide       Web --- Executive
                          visibility into         Dashboard
                          revenue, cash, risk,    
                          and project             
                          profitability           

  Project Manager         Owns a project's        Web
                          schedule, budget, and   
                          delivery                

  Site Engineer / Foreman Records daily site      Mobile Field App
                          activity, quality, and  (offline-first)
                          safety data             

  Quantity Surveyor /     Builds BOQs, rate       Web
  Estimator               analyses, and cost      
                          estimates; measures     
                          work for billing        

  Procurement Officer     Manages RFQs, purchase  Web
                          orders, and vendor      
                          relationships           

  Store/Warehouse Keeper  Manages material        Web + Mobile
                          receipt, issue, and     (barcode/QR scanning)
                          stock levels at yards   
                          and sites               

  Fleet/Plant Manager     Manages equipment       Web
                          allocation,             
                          maintenance, and fuel   

  HR/Payroll Officer      Manages employee and    Web
                          casual worker records,  
                          attendance, and payroll 

  Finance/Accounts        Manages the general     Web
  Officer                 ledger, AP/AR, and      
                          financial reporting     

  QA/QC Engineer          Manages inspection test Web + Mobile
                          plans, NCRs, and punch  
                          lists                   

  HSE Officer             Manages permits,        Web + Mobile
                          incidents, and safety   
                          audits                  

  Subcontractor           Submits progress,       Vendor/Subcontractor
  (external)              receives payment        Portal
                          certificates            

  Client (external)       Reviews progress,       Client Portal
                          approves variations and 
                          invoices                

  Vendor/Supplier         Receives orders,        Vendor Portal
  (external)              submits quotes and      
                          invoices                

  System Administrator    Configures tenant       Web --- Admin Console
                          settings, users, roles, 
                          and permissions         
  -----------------------------------------------------------------------

## 2.4 Operating Environment

-   **Server-side:** Linux containers orchestrated for horizontal
    scaling, deployed to a cloud provider with an African or European
    region for latency, with disaster-recovery replication to a
    secondary region.
-   **Client-side (web):** Modern evergreen browsers (Chrome, Edge,
    Safari, Firefox), responsive down to tablet width for site-office
    use.
-   **Client-side (mobile):** Android (primary, given regional device
    distribution) and iOS, offline-first with local storage and
    background sync.
-   **Connectivity assumption:** Intermittent and low-bandwidth
    connectivity at remote site locations is the default assumption, not
    the exception. All field-facing features must function offline and
    reconcile on reconnect.

## 2.5 Design and Implementation Constraints

-   Multi-tenant data isolation is mandatory; no tenant may access
    another tenant's data under any circumstance, including via
    misconfiguration (enforced at the database layer, not only the
    application layer).
-   The platform must support multi-currency and multi-company
    consolidation from day one, given that contractors in the target
    market frequently operate several legal entities and bid in more
    than one currency.
-   Local regulatory realities (e.g., VAT/withholding tax regimes,
    statutory payroll deductions) must be configurable per
    tenant/jurisdiction rather than hard-coded.
-   The mobile app must degrade gracefully to a fully functional offline
    mode; this is a hard constraint, not a stretch goal.
-   All monetary calculations must use fixed-point/decimal arithmetic;
    floating-point currency values are prohibited.

## 2.6 Assumptions and Dependencies

-   Tenants will provide their own chart of accounts or accept a
    configurable default construction-industry chart of accounts.
-   GPS/telemetry integration for equipment assumes third-party hardware
    already installed or being installed by the tenant; SiteForge
    consumes standard telemetry feeds (e.g., via MQTT/REST) rather than
    manufacturing trackers.
-   Biometric attendance assumes tenant-provided biometric devices with
    a documented integration API (e.g., ZKTeco-class devices); SiteForge
    does not supply biometric hardware.
-   Banking integration for reconciliation depends on the availability
    of a statement feed (file-based or API) from the tenant's bank(s).

## 2.7 Multi-Tenancy Model

SiteForge uses a **shared database, tenant-isolated-schema** approach as
the default (each tenant's rows are scoped by `tenant_id` and enforced
via PostgreSQL Row-Level Security policies on every tenant-scoped
table), with an option to promote a large tenant to a dedicated
database/schema without any application-level code change, since the ORM
layer is tenant-context-aware regardless of physical isolation strategy.
See Section 3 and Section 5 for implementation detail.

# 3. System Architecture Overview

## 3.1 Technology Stack

  ------------------------------------------------------------------------
  Layer                   Technology              Rationale
  ----------------------- ----------------------- ------------------------
  Backend framework       Python 3.13+, Flask     Team expertise; Flask's
                                                  minimalism suits a
                                                  modular monolith that
                                                  can be split into
                                                  services later

  ORM / Migrations        SQLAlchemy, Alembic     Mature, explicit control
                                                  over query generation
                                                  and RLS-aware session
                                                  scoping

  Database                PostgreSQL 16+          Row-Level Security,
                                                  JSONB for
                                                  semi-structured data
                                                  (e.g., custom fields),
                                                  strong transactional
                                                  integrity for financial
                                                  data

  Caching & Queues        Redis, Celery           Background jobs (report
                                                  generation, AI calls,
                                                  notification fan-out),
                                                  rate limiting, session
                                                  caching

  Auth                    JWT (short-lived        Stateless auth suited to
                          access + refresh        mobile offline-first
                          tokens), RBAC           clients; refresh
                                                  rotation for security

  API                     REST (OpenAPI 3.1       REST is simpler to
                          documented); GraphQL    secure and cache
                          considered for v2       per-tenant; GraphQL
                          reporting layer         reserved for flexible
                                                  executive-dashboard
                                                  queries later

  Web frontend            React + TypeScript      Component reuse across
                                                  the 25 modules; strong
                                                  ecosystem for
                                                  data-grid-heavy UI
                                                  (Gantt, BOQ tables)

  Mobile                  Flutter                 Single codebase for
                                                  Android/iOS; mature
                                                  offline/local-database
                                                  story (sqlite via drift)

  Object storage          S3-compatible (MinIO in Site photos, documents,
                          development, managed    drawings, exports
                          S3/equivalent in        
                          production)             

  Deployment              Docker, Gunicorn        Reproducible builds,
                          (WSGI), Nginx, CI/CD    blue-green deploys
                          pipeline (GitHub        
                          Actions)                

  Observability           Structured logging,     Multi-tenant systems
                          OpenTelemetry tracing,  require per-tenant
                          Prometheus/Grafana      visibility into
                          metrics, Sentry for     performance and errors
                          error tracking          
  ------------------------------------------------------------------------

## 3.2 High-Level Architecture

                        ┌─────────────────────────────────────┐
                        │        Client Applications           │
                        │  Web (React)  Mobile (Flutter)        │
                        │  Client Portal   Vendor Portal        │
                        └───────────────┬───────────────────────┘
                                        │ HTTPS / JWT
                        ┌───────────────▼───────────────────────┐
                        │            API Gateway / Nginx         │
                        │   Rate limiting, TLS termination       │
                        └───────────────┬───────────────────────┘
                                        │
                        ┌───────────────▼───────────────────────┐
                        │        Flask Application (Gunicorn)    │
                        │  ┌─────────┐ ┌─────────┐ ┌──────────┐ │
                        │  │ Tender/ │ │ Finance/ │ │ Field Ops│ │
                        │  │ Estimate│ │ Billing  │ │ / Mobile │ │
                        │  │ Module  │ │ Module   │ │ Sync API │ │
                        │  └─────────┘ └─────────┘ └──────────┘ │
                        │   Tenant-context middleware (RLS)      │
                        └───────┬───────────────┬────────────────┘
                                │               │
                    ┌───────────▼───┐   ┌───────▼────────┐
                    │  PostgreSQL    │   │  Redis + Celery │
                    │  (RLS enforced)│   │  (jobs, cache)  │
                    └───────────────┘   └────────┬────────┘
                                                  │
                                        ┌─────────▼─────────┐
                                        │  Anthropic API      │
                                        │  (AI Assistant)     │
                                        └────────────────────┘
                        ┌─────────────────────────────────────┐
                        │  S3-Compatible Object Storage         │
                        │  (photos, documents, exports)         │
                        └─────────────────────────────────────┘

## 3.3 Modular Monolith with Bounded Contexts

Rather than starting with microservices (which adds distributed-systems
complexity the team does not yet need), SiteForge is built as a
**modular monolith**: a single deployable Flask application internally
organized into bounded contexts that map 1:1 to the 25 platform modules
in Section 4. Each bounded context owns its own database tables and
exposes a Python service interface; other modules call that interface
rather than reaching into another module's tables directly. This
discipline is what allows specific modules (e.g., Plant & Quarry
Management, or the AI Assistant) to be extracted into standalone
services later without a rewrite.

## 3.4 Tenant Isolation

Every tenant-scoped table carries a `tenant_id` column. A PostgreSQL
Row-Level Security policy
(`USING (tenant_id = current_setting('app.tenant_id')::uuid)`) is
applied to every such table, and the application sets `app.tenant_id` at
the start of every request via a database session variable, derived from
the authenticated JWT. This means a bug in application-layer filtering
cannot leak cross-tenant data --- the database itself refuses to return
rows outside the current tenant, which is the reason RLS is mandated
over purely application-level `WHERE tenant_id = ?` filtering.

## 3.5 Offline-First Mobile Architecture

The Flutter mobile app maintains a local SQLite database mirroring the
subset of server data relevant to the logged-in user's assigned
projects. Writes (diary entries, photos, attendance, inspections) are
queued locally with a client-generated UUID and a monotonic local
timestamp, then synced to the server via a batched `/sync` endpoint when
connectivity is available. Conflict resolution follows a
**last-writer-wins per field, with a full audit trail of prior values**
--- the server never silently discards a conflicting write; it stores
both and flags the record for review if the conflict touches a
financially or safety-significant field (e.g., quantities on a
measurement sheet).

## 3.6 AI Construction Assistant Architecture

The AI Assistant is implemented as a Celery-backed service that:

1.  Receives a natural-language query or scheduled trigger.
2.  Retrieves scoped, tenant-isolated context (relevant project,
    financial, schedule, or document data) via internal service calls
    --- never a raw database dump.
3.  Sends the assembled context and query to the underlying language
    model via the Anthropic API, with tool-calling enabled for
    structured lookups (e.g., "get idle equipment") and document parsing
    (BOQ/invoice extraction).
4.  Returns a structured response (text, chart data, or a generated
    document) to the requesting interface (chat panel, scheduled report,
    or mobile query).

All AI Assistant calls are logged with the exact context sent, for
auditability, and never include data from a tenant other than the
requester's.

## 3.7 Integration Points

  -----------------------------------------------------------------------
  External System         Purpose                 Integration Method
  ----------------------- ----------------------- -----------------------
  Banks                   Statement               File import (MT940/CSV)
                          reconciliation          or API where available

  GPS/Telematics          Equipment location,     REST/MQTT feed
  providers               fuel, hours             ingestion

  Biometric devices       Attendance              Vendor SDK/API polling
                                                  or push webhook

  Payment gateways        Client online payment   Hosted checkout / API
                          (portal)                

  Government tender       Tender discovery (where Scheduled scraping/feed
  portals                 an API/feed exists)     ingestion where
                                                  permitted, manual entry
                                                  otherwise

  Email/SMS providers     Notifications           Transactional email/SMS
                                                  API

  Accounting export       Statutory filing /      CSV/Excel/PDF export,
                          external auditor        and optional direct
                          handoff                 export to common
                                                  regional accounting
                                                  formats
  -----------------------------------------------------------------------

# 4. Functional Requirements

This section defines detailed functional requirements for all 25
SiteForge modules. Each module is presented with: an overview, its key
data entities, numbered functional requirements (prefixed with a module
code), and module-specific business rules. Cross-cutting business rules
that span multiple modules are consolidated in Section 9.

## 4.1 Module 1 --- Business Development & CRM (Code: BDC)

### Overview

Manages the company's pipeline before a project exists as a contract:
leads, client relationships, opportunities, and the tender calendar that
feeds Module 2.

### Key Data Entities

`Lead`, `Client`, `Contact`, `Opportunity`, `Competitor`, `Consultant`,
`GovernmentAgency`, `Proposal`, `Document`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  BDC-01                              The system shall allow users to
                                      create, update, and archive Lead
                                      records with source, estimated
                                      value, and probability.

  BDC-02                              The system shall maintain a Client
                                      database with company details,
                                      contact persons, billing
                                      information, and historical project
                                      relationship.

  BDC-03                              The system shall track
                                      Opportunities through configurable
                                      pipeline stages (e.g., Identified →
                                      Qualified → Bid/No-Bid → Submitted
                                      → Won/Lost).

  BDC-04                              The system shall provide a Tender
                                      Calendar view showing upcoming
                                      submission deadlines across all
                                      tracked opportunities.

  BDC-05                              The system shall support a
                                      structured Bid/No-Bid decision
                                      workflow with configurable scoring
                                      criteria (e.g., strategic fit,
                                      capacity, risk, margin) and a
                                      recorded decision with rationale
                                      and approver.

  BDC-06                              The system shall allow tracking of
                                      Competitor organizations and their
                                      historical win rates on tracked
                                      tenders, where data is available.

  BDC-07                              The system shall maintain a
                                      Consultant database (engineers,
                                      architects, project managers acting
                                      for clients) with historical
                                      relationship notes.

  BDC-08                              The system shall maintain a
                                      Government Agency database
                                      including procurement contacts and
                                      historical tender patterns.

  BDC-09                              The system shall support Proposal
                                      creation with template-based
                                      document generation, merging
                                      company credentials, past project
                                      references, and CVs of proposed key
                                      staff.

  BDC-10                              The system shall provide a
                                      centralized Document Repository for
                                      pre-tender documents (company
                                      profile, certifications, tax
                                      clearance, past performance)
                                      reusable across proposals.

  BDC-11                              The system shall generate Win/Loss
                                      reports summarizing conversion rate
                                      by client, sector, and value band,
                                      feeding into Module 2's win/loss
                                      analysis.

  BDC-12                              The system shall notify assigned
                                      business development staff of
                                      approaching tender calendar
                                      deadlines on a configurable
                                      schedule (e.g., 14, 7, 2 days
                                      prior).
  -----------------------------------------------------------------------

### Business Rules

-   An Opportunity cannot transition to "Won" without a linked Contract
    record (Module 4).
-   A Bid/No-Bid decision of "No-Bid" closes the opportunity and
    requires a reason code.
-   Only users with the Business Development or Executive role may edit
    scoring criteria weights.

## 4.2 Module 2 --- Tender & Bid Management (Code: TBM)

### Overview

Manages the full tendering process for opportunities that pass the
Bid/No-Bid gate: registering the tender, ingesting the client's Bill of
Quantities, managing clarifications, and tracking submission.

### Key Data Entities

`Tender`, `TenderBOQItem`, `ScopeItem`, `BidDocument`, `RFI`,
`Clarification`, `ApprovalWorkflow`, `TenderChecklistItem`,
`Submission`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  TBM-01                              The system shall allow registration
                                      of a Tender with reference number,
                                      client, consultant, submission
                                      deadline, bid bond requirements,
                                      and tender fee.

  TBM-02                              The system shall support import of
                                      a client-issued BOQ from
                                      Excel/CSV/PDF, mapping columns to
                                      item code, description, unit, and
                                      quantity.

  TBM-03                              The system shall support Scope
                                      Analysis, allowing users to
                                      annotate BOQ items with clarifying
                                      notes, assumptions, and exclusions
                                      before pricing.

  TBM-04                              The system shall maintain a
                                      repository of Bid Documents
                                      (technical proposal, financial
                                      proposal, bid bond, power of
                                      attorney, certifications) with a
                                      completeness checklist.

  TBM-05                              The system shall support creation
                                      and tracking of RFIs to the
                                      client/consultant, with due dates
                                      and received responses logged
                                      against the relevant BOQ item(s).

  TBM-06                              The system shall log Bid
                                      Clarifications issued by the client
                                      (addenda) and flag affected BOQ
                                      items and previously entered
                                      estimates for re-review.

  TBM-07                              The system shall enforce a
                                      configurable Bid Approval Workflow
                                      (e.g., Estimator → Commercial
                                      Manager → Managing Director) before
                                      a bid may be marked "Submitted."

  TBM-08                              The system shall provide a
                                      configurable Tender Checklist (bid
                                      bond obtained, JV agreement signed,
                                      documents certified, etc.) that
                                      must be 100% complete before
                                      submission sign-off.

  TBM-09                              The system shall record Submission
                                      details (method, date/time, receipt
                                      acknowledgment) and support upload
                                      of the submission receipt.

  TBM-10                              The system shall support Win/Loss
                                      Analysis capturing the winning
                                      price (if disclosed), competitor
                                      identities (if known), and a
                                      structured reason code on loss.

  TBM-11                              The system shall support Joint
                                      Venture / Consortium tenders,
                                      apportioning scope and financial
                                      share between JV partners.

  TBM-12                              The system shall prevent submission
                                      sign-off if any mandatory checklist
                                      item, RFI response, or approval
                                      step is outstanding.
  -----------------------------------------------------------------------

### Business Rules

-   A Tender's estimate (Module 3) is locked from further edits once the
    Bid Approval Workflow is initiated; changes thereafter require an
    explicit "reopen for revision" action logged with reason.
-   Every addendum received (TBM-06) must be acknowledged before
    submission; the system blocks submission sign-off otherwise.

## 4.3 Module 3 --- Estimating & Cost Engineering (Code: EST)

### Overview

The foundation of every project's financial life: converts a scoped BOQ
into a priced, risk-adjusted tender price, and produces the baseline
budget and Cost Breakdown Structure that all downstream cost tracking is
measured against.

### Key Data Entities

`BOQItem`, `RateAnalysis`, `CostLibraryItem`, `MaterialPrice`,
`EquipmentRate`, `LaborRate`, `VendorQuotation`, `Markup`,
`Contingency`, `RiskAllowance`, `Budget`, `CostBreakdownStructure`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  EST-01                              The system shall provide a BOQ
                                      Builder supporting hierarchical
                                      (section/sub-section/item)
                                      structuring with unit, quantity,
                                      and rate per item.

  EST-02                              The system shall support Rate
                                      Analysis per BOQ item, decomposing
                                      a unit rate into material, labor,
                                      equipment, and subcontract
                                      components with quantities-per-unit
                                      and unit costs.

  EST-03                              The system shall maintain reusable
                                      Cost Libraries (standard rate
                                      analyses) that can be applied to
                                      new tenders and adjusted for
                                      project-specific factors.

  EST-04                              The system shall maintain a
                                      Material Price database with
                                      location-based and time-based price
                                      history, supporting escalation
                                      assumptions.

  EST-05                              The system shall maintain Equipment
                                      Costing rates (owned equipment
                                      cost-per-hour derived from Module
                                      9/10 data, and rental rates)
                                      selectable per rate analysis line.

  EST-06                              The system shall maintain Labor
                                      Costing rates by trade/grade,
                                      including statutory on-costs,
                                      selectable per rate analysis line.

  EST-07                              The system shall support capturing
                                      and comparing Vendor Quotations
                                      against estimated
                                      material/subcontract costs, feeding
                                      forward into Module 7
                                      (Procurement).

  EST-08                              The system shall support
                                      configurable Markups (overhead %,
                                      profit %) applicable at BOQ-item,
                                      section, or whole-of-tender level.

  EST-09                              The system shall support
                                      Contingency allowances (percentage
                                      or fixed) distinguished from Risk
                                      Allowance (quantified risk
                                      register-based provisioning), both
                                      visible separately in the final
                                      price build-up.

  EST-10                              The system shall generate an
                                      Engineer's Estimate view
                                      (cost-only, no markup) usable for
                                      internal benchmarking and
                                      negotiation preparation.

  EST-11                              The system shall generate the final
                                      Tender Price document, showing BOQ
                                      item rates, section subtotals, and
                                      grand total, exportable to the
                                      client's required BOQ format.

  EST-12                              On contract award, the system shall
                                      generate the project Budget and
                                      Cost Breakdown Structure (CBS)
                                      directly from the winning estimate,
                                      item-for-item, forming the
                                      immutable baseline against which
                                      Module 19 (Project Controls)
                                      measures performance.

  EST-13                              The system shall support what-if
                                      scenario comparison (e.g.,
                                      alternate markup or productivity
                                      assumptions) prior to final
                                      submission, without overwriting the
                                      submitted version.

  EST-14                              The system shall version every
                                      estimate revision with a full audit
                                      trail of rate and quantity changes
                                      between versions.
  -----------------------------------------------------------------------

### Business Rules

-   The CBS baseline (EST-12) is immutable once approved; any subsequent
    change requires a formal Budget Revision record with approval, never
    a silent edit.
-   Rate analyses must reconcile: material + labor + equipment +
    subcontract + markup components must sum to the displayed unit rate
    within rounding tolerance, enforced at save time.

## 4.4 Module 4 --- Contract Management (Code: CTM)

### Overview

Governs the contract that comes into force once a bid is won, including
the commercial instruments (bonds, guarantees, retention) that
construction contracts depend on.

### Key Data Entities

`Contract`, `ContractDocument`, `PaymentTerm`, `PerformanceBond`,
`AdvancePayment`, `Retention`, `Insurance`, `Guarantee`,
`ContractAmendment`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  CTM-01                              The system shall create a Contract
                                      record on award, linked to the
                                      winning Tender and its baseline
                                      Budget/CBS.

  CTM-02                              The system shall store Contract
                                      Value, currency, and payment terms
                                      (e.g., monthly certification,
                                      30-day payment cycle).

  CTM-03                              The system shall maintain a
                                      repository of executed Contract
                                      Documents (signed agreement,
                                      general/particular conditions,
                                      drawings register).

  CTM-04                              The system shall track Performance
                                      Bond details (amount, issuing bank,
                                      validity period) with automated
                                      expiry alerts.

  CTM-05                              The system shall track Advance
                                      Payment terms (percentage,
                                      recoupment schedule) and
                                      automatically calculate recoupment
                                      against each certified payment
                                      (feeding Module 18).

  CTM-06                              The system shall track Retention
                                      percentage and cap, automatically
                                      withholding retention on each
                                      certified payment and tracking the
                                      retention release schedule (e.g.,
                                      50% at substantial completion, 50%
                                      at end of DLP).

  CTM-07                              The system shall track required
                                      Insurance policies (CAR,
                                      third-party liability, workmen's
                                      compensation) with validity and
                                      automated expiry alerts.

  CTM-08                              The system shall track Guarantees
                                      (advance payment guarantee,
                                      retention guarantee) with the same
                                      lifecycle controls as performance
                                      bonds.

  CTM-09                              The system shall support Contract
                                      Amendments (variations to time,
                                      price, or scope at the
                                      whole-contract level) with a full
                                      history distinct from item-level
                                      Variation Orders (Module 18).

  CTM-10                              The system shall track Contract
                                      Expiry / Completion Date, including
                                      extensions of time (EOTs), and
                                      surface upcoming expiries on the
                                      Executive Dashboard.

  CTM-11                              The system shall support
                                      multi-currency contracts with a
                                      defined base currency for
                                      consolidated reporting and
                                      configurable exchange-rate
                                      sourcing.
  -----------------------------------------------------------------------

### Business Rules

-   Retention withheld (CTM-06) must always equal the sum of retention
    amounts deducted across all certified payment certificates for that
    contract; this reconciliation is checked at every certificate
    approval.
-   A bond/guarantee/insurance record nearing expiry (default: 30 days)
    generates a mandatory alert to the assigned Contract Administrator
    and Executive Dashboard; it does not block operations but is
    auditable if left unresolved.

## 4.5 Module 5 --- Project Planning (Code: PLN)

### Overview

Moves beyond simple milestone tracking into full schedule engineering:
WBS, Gantt charts, critical path, resource loading, and look-ahead
planning used daily on-site.

### Key Data Entities

`WBSNode`, `Activity`, `ActivityDependency`, `ResourceAssignment`,
`Baseline`, `LookAheadPlan`, `DelayEvent`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  PLN-01                              The system shall support a
                                      hierarchical Work Breakdown
                                      Structure (WBS) linked to the CBS
                                      so schedule and cost share the same
                                      structural backbone.

  PLN-02                              The system shall render an
                                      interactive Gantt Chart with
                                      drag-to-adjust dates, and shall
                                      recalculate dependent activities
                                      automatically.

  PLN-03                              The system shall calculate the
                                      Critical Path automatically and
                                      visually distinguish critical
                                      activities.

  PLN-04                              The system shall support
                                      Finish-to-Start, Start-to-Start,
                                      Finish-to-Finish, and
                                      Start-to-Finish Activity
                                      Dependencies with lag/lead.

  PLN-05                              The system shall support Resource
                                      Loading, assigning labor crews,
                                      equipment, and materials to
                                      activities and flagging
                                      over-allocation.

  PLN-06                              The system shall allow a Schedule
                                      to be Baselined (snapshot) and
                                      shall retain all prior baselines
                                      for comparison.

  PLN-07                              The system shall generate rolling
                                      Look-Ahead Plans (e.g., 2-week,
                                      6-week) derived from the master
                                      schedule, editable at site level
                                      without altering the master
                                      schedule directly.

  PLN-08                              The system shall support Delay
                                      Analysis, logging Delay Events with
                                      cause classification (client,
                                      contractor, weather, force majeure)
                                      and calculated schedule impact
                                      using a configurable method (e.g.,
                                      time impact analysis).

  PLN-09                              The system shall import/export
                                      schedules in common interchange
                                      formats (e.g., MPX/XML) for
                                      interoperability with external
                                      scheduling tools where required by
                                      a client or consultant.

  PLN-10                              The system shall compute Schedule
                                      Variance against the current
                                      baseline and surface it to Module
                                      19 (Project Controls).

  PLN-11                              The system shall support multiple
                                      concurrent baselines per project
                                      (e.g., original, revised, current)
                                      with clear labeling of which is
                                      used for contractual EOT claims.
  -----------------------------------------------------------------------

### Business Rules

-   Changing an activity's dates after baselining does not alter the
    baseline; variance is always computed as current-minus-baseline,
    never by overwriting history.
-   A Delay Event affecting the critical path automatically flags the
    project's forecast completion date for review on the Executive
    Dashboard.

## 4.6 Module 6 --- Project Execution (Code: EXE)

### Overview

The daily operating record of the project --- what actually happened on
site --- captured primarily through the offline-first Mobile Field App
(Module 24) but fully manageable from the web.

### Key Data Entities

`DailySiteDiary`, `DailyReport`, `SitePhoto`, `SiteVideo`,
`WeatherRecord`, `ProgressEntry`, `WorkCompletedRecord`, `SiteIssue`,
`VisitorLog`, `EquipmentUsageRecord`, `LaborUsageRecord`,
`ConcretePourRecord`, `InspectionLog`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  EXE-01                              The system shall provide a Daily
                                      Site Diary per project per day,
                                      capturing weather, workforce
                                      present, equipment on site, and a
                                      narrative summary.

  EXE-02                              The system shall support Daily
                                      Report generation compiling diary
                                      data, photos, progress, and issues
                                      into a shareable PDF.

  EXE-03                              The system shall allow attaching
                                      Photos and Videos to diary entries,
                                      activities, or inspection records,
                                      with automatic geotagging and
                                      timestamping where device
                                      permissions allow.

  EXE-04                              The system shall capture Weather
                                      conditions (manually or via
                                      integrated weather API) for
                                      contractual delay-claim
                                      substantiation.

  EXE-05                              The system shall capture Progress
                                      against WBS activities as a
                                      percentage or quantity, feeding
                                      Module 19's earned value
                                      calculation.

  EXE-06                              The system shall log Work Completed
                                      against BOQ items with quantities,
                                      cross-referenced to measurement
                                      sheets (Module 12) and billing
                                      (Module 18).

  EXE-07                              The system shall log Site Issues
                                      with category, severity, assigned
                                      owner, and resolution status, and
                                      shall support escalation rules for
                                      overdue issues.

  EXE-08                              The system shall maintain a Visitor
                                      Log for site access records,
                                      supporting HSE induction
                                      verification.

  EXE-09                              The system shall log Equipment Used
                                      and Labor Used per day per
                                      activity, feeding Modules 9 and 11
                                      for utilization and cost
                                      allocation.

  EXE-10                              The system shall support structured
                                      Concrete Pour Records (mix design,
                                      volume, slump test, cube
                                      references, weather at time of
                                      pour) linked to QMS inspection
                                      records.

  EXE-11                              The system shall maintain
                                      Inspection Logs referencing the
                                      applicable Inspection and Test Plan
                                      (Module 13) and recording
                                      pass/fail/conditional outcomes.

  EXE-12                              The system shall allow the Daily
                                      Site Diary to be digitally
                                      signed/approved by the responsible
                                      Site Engineer and countersigned by
                                      the Project Manager or client
                                      representative where required.

  EXE-13                              The system shall support offline
                                      creation and editing of all
                                      Execution-module records, syncing
                                      automatically per the offline
                                      architecture defined in Section
                                      3.5.
  -----------------------------------------------------------------------

### Business Rules

-   A Daily Site Diary, once signed off, becomes read-only; corrections
    require a linked Amendment record, never an edit to signed content.
-   Work Completed quantities recorded in EXE-06 cannot exceed the BOQ
    item's contracted quantity without a linked Variation Order (Module
    18), triggering a warning if exceeded.

## 4.7 Module 7 --- Procurement (Code: PRC)

### Overview

Extends beyond simple purchase orders into full vendor lifecycle
management, tightly integrated with Estimating (for budget checks) and
Inventory (for receipt).

### Key Data Entities

`Vendor`, `RFQ`, `QuotationComparison`, `PurchaseRequest`,
`PurchaseOrder`, `Approval`, `GoodsReceiptNote`, `InvoiceMatch`,
`VendorPerformanceRecord`, `SupplierRating`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  PRC-01                              The system shall maintain a Vendor
                                      Registration record including tax
                                      registration, banking details,
                                      categories supplied, and compliance
                                      document expiry (e.g., trade
                                      license).

  PRC-02                              The system shall support raising
                                      RFQs to multiple vendors for a
                                      given material/service requirement,
                                      with a defined response deadline.

  PRC-03                              The system shall generate a
                                      side-by-side Quotation Comparison
                                      across responding vendors on price,
                                      lead time, and payment terms.

  PRC-04                              The system shall support Purchase
                                      Requests raised by site or project
                                      staff, validated in real time
                                      against remaining budget (from the
                                      CBS) before submission.

  PRC-05                              The system shall generate Purchase
                                      Orders from an approved Purchase
                                      Request or accepted quotation, with
                                      line-item reference back to the
                                      originating BOQ/CBS item.

  PRC-06                              The system shall enforce a
                                      configurable multi-level Approval
                                      workflow for Purchase Orders based
                                      on value thresholds.

  PRC-07                              The system shall support Goods
                                      Receipt Notes recording quantity
                                      received, condition, and
                                      discrepancies against the Purchase
                                      Order, updating Inventory (Module
                                      8) automatically on confirmation.

  PRC-08                              The system shall support three-way
                                      Invoice Matching (Purchase Order,
                                      Goods Receipt Note, Vendor Invoice)
                                      before an invoice is released for
                                      payment in Module 17.

  PRC-09                              The system shall maintain Vendor
                                      Performance Records tracking
                                      on-time delivery rate, quality
                                      rejection rate, and price
                                      competitiveness over time.

  PRC-10                              The system shall support a
                                      structured Supplier Rating
                                      (scorecard) reviewable at contract
                                      renewal or annual vendor review.

  PRC-11                              The system shall flag Purchase
                                      Requests/Orders that would breach
                                      the remaining CBS budget for the
                                      relevant cost code, requiring an
                                      override with recorded
                                      justification and approver.

  PRC-12                              The system shall support
                                      blanket/framework Purchase Orders
                                      for recurring materials, drawn down
                                      incrementally by multiple Goods
                                      Receipt Notes.
  -----------------------------------------------------------------------

### Business Rules

-   A Purchase Order cannot be issued to a Vendor whose compliance
    documents (PRC-01) have expired, without an explicit
    compliance-waiver override recorded with reason and approver.
-   Invoice payment (Module 17) is blocked until three-way matching
    (PRC-08) is complete or an exception is explicitly approved.

## 4.8 Module 8 --- Inventory & Warehouse (Code: INV)

### Overview

Tracks every material movement across the company's central yard,
individual site stores, and quarries, with the granularity (batch,
serial, barcode) that civil works and materials-heavy contracting
requires.

### Key Data Entities

`Warehouse` (Yard/Site Store/Quarry), `StockItem`, `StockTransfer`,
`StockReservation`, `ReorderLevel`, `Barcode`, `QRCode`, `BatchNumber`,
`SerialNumber`, `WasteRecord`, `MaterialReturn`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  INV-01                              The system shall support multiple
                                      Warehouse types (Central Yard, Site
                                      Store, Quarry) each with
                                      independent stock balances rolled
                                      up to a company-wide view.

  INV-02                              The system shall support Stock
                                      Transfers between warehouses with
                                      in-transit tracking and receipt
                                      confirmation at the destination.

  INV-03                              The system shall support Stock
                                      Reservations against a specific
                                      project/activity, reducing
                                      available (but not physical)
                                      quantity shown to other projects.

  INV-04                              The system shall support
                                      configurable Reorder Levels per
                                      item per warehouse, triggering
                                      automatic reorder alerts or draft
                                      Purchase Requests.

  INV-05                              The system shall support Barcode
                                      and QR Code generation and scanning
                                      for stock issue, receipt, and
                                      count, usable from the Mobile Field
                                      App.

  INV-06                              The system shall support Batch
                                      Number tracking for materials with
                                      shelf life or quality-certificate
                                      dependency (e.g., cement,
                                      admixtures).

  INV-07                              The system shall support Serial
                                      Number tracking for high-value
                                      trackable items (e.g., generators,
                                      specific tools).

  INV-08                              The system shall support Waste
                                      Tracking, recording material loss
                                      with cause classification
                                      (breakage, theft, spoilage,
                                      over-order) for cost analysis.

  INV-09                              The system shall support Material
                                      Returns from site back to yard or
                                      to vendor, with condition recording
                                      and, where applicable, credit note
                                      linkage to Module 7/17.

  INV-10                              The system shall support Cycle
                                      Counting and full Stock Takes with
                                      variance reporting against
                                      system-recorded balances.

  INV-11                              The system shall value stock using
                                      a configurable method (weighted
                                      average or FIFO) per tenant,
                                      consistent across all warehouses
                                      for that tenant.

  INV-12                              The system shall provide real-time
                                      stock visibility per project,
                                      distinguishing on-hand, reserved,
                                      and in-transit quantities.
  -----------------------------------------------------------------------

### Business Rules

-   A Stock Transfer is not considered complete, and does not update
    destination balances, until receipt is confirmed at the destination
    warehouse.
-   Waste and shrinkage recorded in INV-08 rolls up into project cost
    variance in Module 19 as a distinct cost category, never hidden
    inside standard consumption.

## 4.9 Module 9 --- Equipment & Fleet Management (Code: EQP)

### Overview

A complete fleet management system covering the full lifecycle of owned
and rented plant and vehicles, from acquisition through utilization
tracking to disposal.

### Key Data Entities

`Equipment`, `GPSPosition`, `FuelConsumptionRecord` (see Module 10 for
detail), `OperatorAssignment`, `MaintenanceRecord`, `SparePart`,
`RepairHistory`, `DowntimeEvent`, `UtilizationRecord`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  EQP-01                              The system shall maintain an
                                      Equipment Register with make,
                                      model, serial/chassis number,
                                      ownership type (owned/rented),
                                      acquisition cost, and depreciation
                                      schedule.

  EQP-02                              The system shall ingest GPS
                                      Integration feeds where available,
                                      showing current location and
                                      location history on a map view.

  EQP-03                              The system shall track Fuel
                                      Consumption per equipment unit,
                                      cross-referenced with Module 10.

  EQP-04                              The system shall support Operator
                                      Assignment, linking a qualified
                                      operator (Module 11 competency
                                      check) to a piece of equipment for
                                      a shift or period.

  EQP-05                              The system shall support scheduled
                                      and unscheduled Maintenance records
                                      with due-date alerts based on
                                      hours, mileage, or calendar
                                      interval.

  EQP-06                              The system shall maintain a Spare
                                      Parts inventory linked to Module 8,
                                      tracking parts consumed per
                                      maintenance/repair event.

  EQP-07                              The system shall maintain Repair
                                      History per equipment unit,
                                      including cost, downtime duration,
                                      and root cause.

  EQP-08                              The system shall track Downtime
                                      Events with reason classification
                                      (breakdown, scheduled maintenance,
                                      awaiting parts, idle/no work)
                                      distinct from productive hours.

  EQP-09                              The system shall calculate
                                      Availability (uptime ÷ total
                                      scheduled time) and Utilization
                                      (productive hours ÷ available
                                      hours) per equipment unit and per
                                      fleet category.

  EQP-10                              The system shall calculate Cost per
                                      Hour (fuel + maintenance +
                                      depreciation + operator ÷ hours
                                      operated) and Cost per Project,
                                      allocating shared equipment costs
                                      across projects by usage.

  EQP-11                              The system shall flag equipment
                                      that is Idle (no logged usage)
                                      beyond a configurable threshold for
                                      reallocation review --- directly
                                      answering the "show me all idle
                                      excavators" AI Assistant use case.

  EQP-12                              The system shall support equipment
                                      Transfer between projects/sites
                                      with an approval step and automatic
                                      cost-allocation cutover date.
  -----------------------------------------------------------------------

### Business Rules

-   An Operator Assignment (EQP-04) is blocked if the operator's
    relevant certification (Module 11) has expired.
-   Cost per Hour (EQP-10) recalculates automatically whenever a
    contributing maintenance, fuel, or depreciation record changes,
    keeping the figure always current rather than static.

## 4.10 Module 10 --- Fuel Management (Code: FUEL)

### Overview

A dedicated module given how materially fuel cost and fuel-related fraud
affect contractor margins in the target market.

### Key Data Entities

`FuelPurchase`, `FuelTank`, `FuelIssue`, `FuelVarianceRecord`,
`TheftFlag`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FUEL-01                             The system shall record Fuel
                                      Purchases with vendor, quantity,
                                      price, and delivery confirmation,
                                      updating Fuel Tank balances.

  FUEL-02                             The system shall track Fuel Tank
                                      levels (bulk storage tanks and,
                                      where telemetry exists, equipment
                                      onboard tanks) with dip-reading or
                                      sensor-based reconciliation.

  FUEL-03                             The system shall record Fuel Issues
                                      to specific equipment or
                                      generators, requiring
                                      operator/equipment selection and
                                      odometer/hour-meter reading at time
                                      of issue.

  FUEL-04                             The system shall calculate expected
                                      consumption per equipment unit
                                      based on historical/manufacturer
                                      burn rate and compare it against
                                      actual issued fuel to compute a
                                      Fuel Variance.

  FUEL-05                             The system shall flag Fuel Theft
                                      Detection alerts where variance
                                      exceeds a configurable threshold,
                                      where a fuel issue occurs with no
                                      corresponding equipment usage log,
                                      or where tank-level drops do not
                                      match recorded issues.

  FUEL-06                             The system shall calculate Fuel
                                      Efficiency (consumption per hour or
                                      per unit of output, e.g., per m³
                                      excavated) per equipment unit.

  FUEL-07                             The system shall generate Fuel Cost
                                      Reports by project, equipment, and
                                      time period, distinguishing normal
                                      consumption from variance/loss.

  FUEL-08                             The system shall support
                                      integration with GPS/telematics
                                      fuel-level sensors where installed,
                                      reducing reliance on manual dip
                                      readings.

  FUEL-09                             The system shall require a
                                      countersigned fuel issue slip
                                      (digital signature captured via
                                      mobile) for any manual
                                      (non-telemetry) fuel issue above a
                                      configurable quantity threshold.
  -----------------------------------------------------------------------

### Business Rules

-   A Fuel Theft Detection flag (FUEL-05) does not auto-block operations
    but generates a mandatory review task assigned to the Fleet/Plant
    Manager, escalating to Executive Dashboard visibility if unresolved
    beyond a configurable period.
-   Fuel Variance (FUEL-04) is calculated per equipment unit per period
    and rolls into Cost per Hour (EQP-10) as a distinct line, not
    blended into a generic fuel cost figure.

## 4.11 Module 11 --- Workforce Management (Code: WFM)

### Overview

Extends beyond payroll to cover the full mixed workforce reality of
construction: permanent employees, daily casual labor, and their
competency, attendance, and pay.

### Key Data Entities

`Employee`, `CasualWorker`, `AttendanceRecord`, `Timesheet`,
`LeaveRequest`, `TrainingRecord`, `MedicalRecord`, `Competency`,
`Certification`, `PayrollRun`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  WFM-01                              The system shall maintain Employee
                                      records (permanent/contract staff)
                                      with role, trade, pay grade, and
                                      assigned project(s).

  WFM-02                              The system shall maintain Casual
                                      Worker records supporting rapid
                                      daily onboarding at site level,
                                      with minimal required fields for
                                      same-day engagement.

  WFM-03                              The system shall capture Attendance
                                      via manual entry, QR code, or
                                      Biometric device integration, per
                                      project per day.

  WFM-04                              The system shall generate
                                      Timesheets from attendance and
                                      activity assignment (Module 5/6),
                                      supporting both time-based and
                                      piece-rate/task-based pay.

  WFM-05                              The system shall support Leave
                                      requests and approvals,
                                      distinguishing leave types per
                                      tenant policy (annual, sick,
                                      compassionate).

  WFM-06                              The system shall maintain Training
                                      Records including course, provider,
                                      completion date, and expiry (where
                                      applicable, e.g., first aid
                                      refreshers).

  WFM-07                              The system shall maintain Medical
                                      Records including fitness-to-work
                                      certification, with confidentiality
                                      access restricted to HR and HSE
                                      roles only.

  WFM-08                              The system shall maintain a
                                      Competency matrix per employee
                                      (skills, equipment authorizations)
                                      referenced by Module 9's
                                      operator-assignment check and
                                      Module 13/14 role qualifications.

  WFM-09                              The system shall track
                                      Certifications with expiry dates
                                      and automated renewal alerts (e.g.,
                                      crane operator license, scaffold
                                      certificate).

  WFM-10                              The system shall run Payroll,
                                      calculating gross pay from
                                      timesheets/attendance, applying
                                      statutory deductions (configurable
                                      per jurisdiction), and generating
                                      payslips and a bank payment file.

  WFM-11                              The system shall support
                                      Subcontract Labor engaged directly
                                      by the main contractor (as distinct
                                      from full Subcontractor Management
                                      in Module 12) with simplified
                                      attendance-based payment.

  WFM-12                              The system shall allocate labor
                                      cost to project/activity/cost-code
                                      for project costing purposes
                                      (feeding Module 17 and Module 19).
  -----------------------------------------------------------------------

### Business Rules

-   Medical Records (WFM-07) access is restricted at the field level
    regardless of general role permissions --- even a Project Manager
    with broad access cannot view medical detail without an explicit
    HR/HSE role grant.
-   Payroll (WFM-10) cannot be finalized while any linked timesheet
    remains in "pending approval" status.

## 4.12 Module 12 --- Subcontractor Management (Code: SUB)

### Overview

Critical for civil engineering projects where a significant share of
scope is routinely subcontracted; manages the subcontractor as a
quasi-client-and-vendor hybrid.

### Key Data Entities

`SubcontractAgreement`, `SubcontractScopeItem`,
`SubcontractProgressEntry`, `MeasurementSheet`, `PaymentCertificate`
(subcontract), `SubcontractRetention`, `SubcontractClaim`,
`PerformanceRating`, `ComplianceDocument`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  SUB-01                              The system shall maintain
                                      Subcontract Agreements with value,
                                      scope reference, payment terms, and
                                      retention terms, mirroring the
                                      structure of Module 4's Contract
                                      but scoped to a subcontract
                                      package.

  SUB-02                              The system shall define Scope of
                                      Work at BOQ-item or lump-sum level,
                                      linked to the main contract's CBS
                                      for cost-code alignment.

  SUB-03                              The system shall support
                                      subcontractor Progress submissions
                                      (self-measured), routed for
                                      main-contractor verification before
                                      certification.

  SUB-04                              The system shall support
                                      Measurement Sheets recording
                                      verified quantities of work
                                      executed, jointly referenced by
                                      both parties.

  SUB-05                              The system shall generate
                                      subcontract Payment Certificates
                                      from verified measurement, applying
                                      retention and any recoverable
                                      deductions (e.g., materials
                                      supplied by main contractor).

  SUB-06                              The system shall track Subcontract
                                      Retention withheld and its release
                                      schedule, independent of but
                                      reconcilable against the main
                                      contract's retention (Module 4).

  SUB-07                              The system shall support
                                      Subcontractor Claims (e.g., for
                                      delay, additional scope) with a
                                      structured review and response
                                      workflow.

  SUB-08                              The system shall maintain a
                                      Performance Rating per
                                      subcontractor per project (quality,
                                      schedule adherence, safety
                                      compliance, responsiveness).

  SUB-09                              The system shall track Compliance
                                      Documents (insurance, safety
                                      certification, tax clearance, labor
                                      law compliance) with expiry alerts,
                                      blocking new payment certification
                                      if expired absent an explicit
                                      waiver.

  SUB-10                              The system shall support
                                      back-charges to a subcontractor
                                      (e.g., for rework, materials
                                      supplied) deducted directly on the
                                      next Payment Certificate with full
                                      itemization.
  -----------------------------------------------------------------------

### Business Rules

-   A subcontract Payment Certificate (SUB-05) cannot be issued without
    a corresponding verified Measurement Sheet (SUB-04) for the
    certified quantities.
-   Subcontract Retention (SUB-06) release is a distinct approval step
    from main-contract retention release and does not occur
    automatically from a main-contract event.

## 4.13 Module 13 --- Quality Management (QMS) (Code: QMS)

### Overview

Provides the auditable quality trail construction contracts and client
consultants require, from planned inspections through to formal
close-out.

### Key Data Entities

`InspectionTestPlan`, `MaterialApproval`, `LabResult`, `NCR`,
`PunchListItem`, `CorrectiveAction`, `SnagListItem`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  QMS-01                              The system shall define Inspection
                                      and Test Plans (ITPs) per work
                                      activity type, specifying required
                                      hold points, checks, and acceptance
                                      criteria.

  QMS-02                              The system shall support Material
                                      Approval submittals (technical
                                      data, samples) with a
                                      client/consultant approval workflow
                                      before the material may be used,
                                      cross-referenced to Module 8 stock.

  QMS-03                              The system shall record Laboratory
                                      Results (e.g., concrete cube
                                      strength, compaction density,
                                      asphalt extraction) linked to the
                                      relevant pour/lot record.

  QMS-04                              The system shall raise
                                      Non-Conformance Reports (NCRs) with
                                      description, photographic evidence,
                                      root cause, and disposition
                                      (rework/accept-as-is/reject).

  QMS-05                              The system shall maintain Punch
                                      Lists per area/building/section,
                                      tracked to closure before handover
                                      sign-off.

  QMS-06                              The system shall track Corrective
                                      Actions arising from NCRs or
                                      audits, with owner, due date, and
                                      verification-of-closure step.

  QMS-07                              The system shall maintain Snag
                                      Lists distinct from punch lists
                                      where the tenant's contractual
                                      terminology requires the
                                      distinction (configurable per
                                      tenant/contract).

  QMS-08                              The system shall support Close-out
                                      Tracking, requiring all NCRs, punch
                                      list items, and snag list items in
                                      a given scope to be closed before
                                      that scope can be marked complete
                                      in Module 6/19.

  QMS-09                              The system shall link every ITP
                                      hold point to the corresponding
                                      Inspection Log entry (Module 6) so
                                      that inspection completion is
                                      provable against the plan, not
                                      merely recorded ad hoc.

  QMS-10                              The system shall generate a Quality
                                      Dashboard showing open NCR count
                                      and age, punch list closure rate,
                                      and material approval turnaround
                                      time.
  -----------------------------------------------------------------------

### Business Rules

-   Work may not proceed past a defined ITP hold point (QMS-01) without
    a recorded pass or an approved concession, enforced as a workflow
    gate rather than a passive reminder.
-   An NCR (QMS-04) cannot be closed without a linked Corrective Action
    verified as complete.

## 4.14 Module 14 --- Health, Safety & Environment (HSE) (Code: HSE)

### Overview

Manages the permit, incident, and audit trail that keeps a contracting
business insurable, certifiable, and --- most importantly --- its
workforce safe.

### Key Data Entities

`PermitToWork`, `Incident`, `NearMiss`, `ToolboxTalk`, `PPERecord`,
`SafetyAudit`, `RiskAssessment`, `EnvironmentalMonitoringRecord`,
`WasteDisposalRecord`, `EmergencyResponsePlan`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  HSE-01                              The system shall support Permit to
                                      Work issuance for high-risk
                                      activities (hot work, confined
                                      space, excavation, working at
                                      height) with a defined approval and
                                      closure workflow.

  HSE-02                              The system shall record Incidents
                                      with classification (first aid,
                                      medical treatment, lost time,
                                      fatality), investigation findings,
                                      and regulatory-reportable flag.

  HSE-03                              The system shall record Near Misses
                                      with the same structured
                                      classification as incidents,
                                      distinguished by outcome severity,
                                      feeding leading-indicator safety
                                      metrics.

  HSE-04                              The system shall log Toolbox Talks
                                      with topic, attendee list (linked
                                      to Module 11 employee/casual worker
                                      records), and facilitator
                                      signature.

  HSE-05                              The system shall track PPE issuance
                                      per worker, with reorder alerts
                                      linked to Module 8 stock levels.

  HSE-06                              The system shall support scheduled
                                      and ad hoc Safety Audits with a
                                      configurable checklist, scoring,
                                      and corrective-action linkage to
                                      Module 13's Corrective Action
                                      entity.

  HSE-07                              The system shall maintain Risk
                                      Assessments per activity/area,
                                      requiring review and re-approval on
                                      a configurable interval or upon a
                                      significant scope change.

  HSE-08                              The system shall record
                                      Environmental Monitoring data
                                      (dust, noise, water discharge
                                      quality) where required by project
                                      environmental permits.

  HSE-09                              The system shall track Waste
                                      Disposal (construction waste,
                                      hazardous materials) with
                                      manifest/certificate of disposal
                                      attachment for regulatory
                                      compliance.

  HSE-10                              The system shall maintain an
                                      Emergency Response Plan per
                                      project/site with designated roles,
                                      muster points, and emergency
                                      contacts accessible offline from
                                      the Mobile Field App.

  HSE-11                              The system shall calculate leading
                                      and lagging safety indicators
                                      (TRIR, LTIFR, near-miss reporting
                                      rate) per project and company-wide
                                      for the Executive Dashboard.

  HSE-12                              The system shall block Permit to
                                      Work issuance (HSE-01) if the
                                      relevant Risk Assessment (HSE-07)
                                      is expired or the involved workers'
                                      safety training (Module 11) is not
                                      current.
  -----------------------------------------------------------------------

### Business Rules

-   A Permit to Work (HSE-01) must be formally closed (not merely
    time-expired) before the associated work is marked complete in
    Module 6.
-   Every recordable Incident (HSE-02) automatically generates a
    Corrective Action requirement, and closure of that action requires
    sign-off by the HSE Officer role specifically, regardless of who
    raised it.

## 4.15 Module 15 --- Survey & Engineering (Code: SVY)

### Overview

Captures the geospatial and earthworks data unique to civil
construction, bridging field survey work and downstream billing/QMS.

### Key Data Entities

`SurveyControlPoint`, `GPSCoordinate`, `LevelReading`, `CrossSection`,
`EarthworksVolumeCalculation`, `RoadAlignment`, `AsBuiltRecord`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  SVY-01                              The system shall maintain a
                                      register of Survey Control Points
                                      with coordinate system, datum, and
                                      benchmark elevation.

  SVY-02                              The system shall support capture
                                      and storage of GPS Coordinates for
                                      setting-out and as-built
                                      verification, importable from
                                      common survey instrument export
                                      formats.

  SVY-03                              The system shall support Level
                                      Readings for grading and
                                      formation-level verification
                                      against design levels, flagging
                                      out-of-tolerance readings.

  SVY-04                              The system shall support Cross
                                      Section capture and comparison
                                      against design cross-sections for
                                      earthworks measurement.

  SVY-05                              The system shall calculate
                                      Earthworks Volumes (cut/fill) from
                                      cross-section or surface-model
                                      data, feeding Module 6 progress and
                                      Module 18 billing quantities.

  SVY-06                              The system shall maintain Road
                                      Alignment data (horizontal and
                                      vertical alignment, chainage) for
                                      linear infrastructure projects.

  SVY-07                              The system shall maintain As-Built
                                      Records capturing final constructed
                                      position/level versus design,
                                      forming part of the handover
                                      package to Module 20 (Asset
                                      Management).

  SVY-08                              The system shall support import of
                                      design surfaces/alignments from
                                      common civil design software export
                                      formats (e.g., LandXML) for
                                      comparison against field survey
                                      data.

  SVY-09                              The system shall allow survey data
                                      capture from the Mobile Field App
                                      with GPS-tagged photos correlated
                                      to control points.
  -----------------------------------------------------------------------

### Business Rules

-   Earthworks Volume calculations (SVY-05) used for billing must
    reference an approved design surface; ad hoc volume estimates are
    clearly flagged as "unofficial/preliminary" and cannot be submitted
    as a billing quantity.
-   As-Built Records (SVY-07) are locked once the associated scope is
    marked complete and become part of the immutable handover package.

## 4.16 Module 16 --- Plant & Quarry Management (Code: PQ)

### Overview

Identified as a potential major differentiator: manages the production
side of the business for contractors who operate their own crushers,
asphalt plants, concrete batching plants, and quarries --- a common
vertical-integration pattern in the target market.

### Key Data Entities

`CrusherProductionRecord`, `AsphaltPlantBatch`, `ConcretePlantBatch`,
`QuarryProductionRecord`, `Stockpile`, `ExplosivesRegister`,
`DrillingRecord`, `BlastingRecord`, `HaulageRecord`, `ProductionReport`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  PQ-01                               The system shall record Crusher
                                      Production by shift, tracking input
                                      material, output gradation split,
                                      and downtime.

  PQ-02                               The system shall record Asphalt
                                      Plant Batches with mix design
                                      reference, temperature, and
                                      quantity produced, linked to QMS
                                      lab results.

  PQ-03                               The system shall record Concrete
                                      Plant Batches with mix design,
                                      batch weights, water/cement ratio,
                                      and destination pour reference
                                      (Module 6).

  PQ-04                               The system shall record Quarry
                                      Production by face/bench, material
                                      type, and volume extracted.

  PQ-05                               The system shall track Stockpile
                                      quantities and locations by
                                      material type, reconciling
                                      production output against Inventory
                                      (Module 8) receipts.

  PQ-06                               The system shall maintain an
                                      Explosives Register recording
                                      procurement, storage, issuance, and
                                      consumption in compliance with
                                      regulatory record-keeping
                                      requirements.

  PQ-07                               The system shall record Drilling
                                      Records (pattern, depth, hole
                                      count) preceding a blast event.

  PQ-08                               The system shall record Blasting
                                      Records (explosives used, blast
                                      design, vibration/fly-rock
                                      monitoring results) linked to the
                                      relevant drilling record and
                                      regulatory notification where
                                      required.

  PQ-09                               The system shall track Haulage
                                      Records (loads, tonnage, cycle
                                      time) between quarry/plant and site
                                      or stockpile.

  PQ-10                               The system shall generate
                                      consolidated Production Reports by
                                      plant/quarry/period, including
                                      yield efficiency and cost per
                                      ton/m³ produced.

  PQ-11                               The system shall allocate
                                      plant/quarry production cost to
                                      consuming projects based on actual
                                      off-take, feeding project costing
                                      in Module 17/19.
  -----------------------------------------------------------------------

### Business Rules

-   Explosives Register entries (PQ-06) cannot be deleted, only
    appended/corrected with an audit trail, given the regulatory
    sensitivity of explosives record-keeping.
-   Blasting Records (PQ-08) require a linked Drilling Record and, where
    the tenant's jurisdiction requires it, a recorded regulatory
    notification reference before the blast event can be marked
    complete.

## 4.17 Module 17 --- Financial Management (Code: FIN)

### Overview

A complete accounting system built for project-costed, multi-company,
multi-currency construction accounting --- the ERP core referenced in
this document's opening statement, expressed through the platform's
project lifecycle rather than as an isolated department.

### Key Data Entities

`GeneralLedgerEntry`, `ChartOfAccounts`, `AccountsPayableInvoice`,
`AccountsReceivableInvoice`, `BudgetControl`, `CashFlowRecord`,
`FixedAsset`, `BankStatement`, `BankReconciliation`, `TaxRecord`,
`FinancialStatement`, `ProjectCostRecord`, `Company` (multi-company).

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  FIN-01                              The system shall maintain a
                                      double-entry General Ledger with a
                                      configurable Chart of Accounts,
                                      defaulting to a
                                      construction-industry template.

  FIN-02                              The system shall support Accounts
                                      Payable, generating payable
                                      invoices from matched procurement
                                      invoices (Module 7) and subcontract
                                      certificates (Module 12).

  FIN-03                              The system shall support Accounts
                                      Receivable, generating receivable
                                      invoices from client billing
                                      (Module 18).

  FIN-04                              The system shall enforce Budget
                                      Control, preventing (or warning,
                                      per configurable policy) postings
                                      that exceed the CBS budget for a
                                      cost code without an approved
                                      budget revision.

  FIN-05                              The system shall generate Cash Flow
                                      reports (actual and forecast) at
                                      company and project level, feeding
                                      Module 19's cash flow forecast.

  FIN-06                              The system shall maintain a Fixed
                                      Assets register with depreciation
                                      schedules, integrated with Module
                                      9's equipment register where an
                                      asset is also operational plant.

  FIN-07                              The system shall support Bank
                                      Reconciliation against imported
                                      bank statements (file or API),
                                      matching transactions automatically
                                      where possible and flagging
                                      exceptions.

  FIN-08                              The system shall calculate and
                                      track Taxes (VAT/withholding/other,
                                      configurable per jurisdiction) on
                                      both sales and purchase
                                      transactions.

  FIN-09                              The system shall generate standard
                                      Financial Statements (Income
                                      Statement, Balance Sheet, Cash Flow
                                      Statement) at company and
                                      consolidated-group level.

  FIN-10                              The system shall support Project
                                      Costing, allocating every revenue
                                      and cost transaction to a project
                                      and, within it, to a cost code
                                      aligned with the CBS.

  FIN-11                              The system shall support
                                      Multi-currency accounting with
                                      configurable functional and
                                      presentation currencies and
                                      automated exchange-rate
                                      application/revaluation.

  FIN-12                              The system shall support
                                      Multi-company consolidation for
                                      tenants operating more than one
                                      legal entity, including
                                      intercompany transaction
                                      elimination.

  FIN-13                              The system shall use fixed-point
                                      decimal arithmetic for all monetary
                                      values and shall never represent
                                      currency amounts as floating-point
                                      numbers, per the constraint in
                                      Section 2.5.

  FIN-14                              The system shall maintain a full,
                                      immutable audit trail of every
                                      General Ledger posting, including
                                      the originating module and user.
  -----------------------------------------------------------------------

### Business Rules

-   No transaction may post directly to the General Ledger bypassing its
    originating module (e.g., a payable invoice must originate from
    Module 7/12, never a manual AP entry outside of a documented
    exception process with elevated approval).
-   Budget Control (FIN-04) policy (hard block vs. warning) is
    configurable per tenant per cost category, since some tenants
    require certainty of budget compliance and others require
    flexibility for urgent site needs.

## 4.18 Module 18 --- Client Billing (Code: BIL)

### Overview

The revenue-recognition engine of the platform: converts verified
progress into certified, client-facing billing documents.

### Key Data Entities

`ProgressCertificate`, `MilestoneBillingSchedule`, `RetentionLedger`,
`VariationOrder`, `Claim`, `PaymentTracking`, `OutstandingInvoice`,
`RevenueRecognitionRecord`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  BIL-01                              The system shall generate Progress
                                      Certificates from verified Work
                                      Completed quantities (Module 6)
                                      and/or measurement sheets, applying
                                      contract rates from the CBS.

  BIL-02                              The system shall support Milestone
                                      Billing schedules for contracts
                                      billed against defined milestones
                                      rather than measured quantities.

  BIL-03                              The system shall maintain the
                                      Retention Ledger, calculating
                                      retention withheld per certificate
                                      and tracking scheduled release per
                                      Module 4's contract terms.

  BIL-04                              The system shall support Variation
                                      Orders at BOQ-item level, requiring
                                      client/consultant approval before
                                      the varied quantity or rate is
                                      billable.

  BIL-05                              The system shall support formal
                                      Claims (e.g., for delay costs,
                                      disruption, unforeseen conditions)
                                      with supporting documentation
                                      package assembly.

  BIL-06                              The system shall track Payment
                                      status per certificate/invoice
                                      (submitted, certified, paid,
                                      overdue) with automated aging.

  BIL-07                              The system shall generate an
                                      Outstanding Invoices report by
                                      client/project/age band, surfaced
                                      on the Executive Dashboard.

  BIL-08                              The system shall support
                                      configurable Revenue Recognition
                                      methods (percentage-of-completion
                                      as the default for long-term
                                      construction contracts,
                                      completed-contract where required)
                                      feeding Module 17's financial
                                      statements.

  BIL-09                              The system shall route Progress
                                      Certificates through a
                                      client-approval step (in-app via
                                      the Client Portal, Module 22, or
                                      manual upload of a countersigned
                                      certificate) before recognizing the
                                      associated receivable.

  BIL-10                              The system shall prevent
                                      double-billing of a quantity by
                                      validating cumulative billed
                                      quantity per BOQ item against the
                                      contracted (plus approved
                                      variation) quantity.
  -----------------------------------------------------------------------

### Business Rules

-   Percentage-of-completion revenue (BIL-08) is calculated from the
    same progress data used for the Progress Certificate (BIL-01),
    ensuring billed revenue and recognized revenue never diverge without
    an explicit, documented reason (e.g., over-billing/under-billing
    position, which the system tracks explicitly rather than silently
    reconciling).
-   A Variation Order (BIL-04) not yet approved may be tracked as a
    pending claim value in reporting but must not appear in a Progress
    Certificate as billable.

## 4.19 Module 19 --- Project Controls (Code: PC)

### Overview

The module intended to distinguish SiteForge from generic ERPs: a single
dashboard where schedule, cost, and risk data from every other module
converge into standard Earned Value Management analytics.

### Key Data Entities

`EVMSnapshot`, `ScheduleVarianceRecord`, `CostVarianceRecord`,
`ForecastAtCompletion`, `CashFlowForecast`, `RiskRegisterEntry`,
`DelayAnalysisSummary`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  PC-01                               The system shall calculate Planned
                                      Value (PV) from the baselined
                                      schedule and budget (Modules 5 and
                                      3).

  PC-02                               The system shall calculate Earned
                                      Value (EV) from recorded physical
                                      progress (Module 6) valued at
                                      baseline rates.

  PC-03                               The system shall calculate Actual
                                      Cost (AC) from posted project costs
                                      (Module 17).

  PC-04                               The system shall calculate Cost
                                      Performance Index (CPI = EV/AC) and
                                      Schedule Performance Index (SPI =
                                      EV/PV) at project, section, and
                                      cost-code level.

  PC-05                               The system shall calculate Schedule
                                      Variance (SV = EV − PV) and Cost
                                      Variance (CV = EV − AC).

  PC-06                               The system shall calculate Forecast
                                      at Completion (using configurable
                                      methods: CPI-based,
                                      atypical-variance, or manual
                                      re-estimate) and Budget at
                                      Completion.

  PC-07                               The system shall generate a rolling
                                      Cash Flow Forecast combining
                                      committed costs, planned billing,
                                      and payment terms.

  PC-08                               The system shall maintain a Risk
                                      Register with probability, impact,
                                      exposure value, and mitigation
                                      owner, feeding EST-09's risk
                                      allowance and informing forecast
                                      confidence.

  PC-09                               The system shall summarize Delay
                                      Analysis (from Module 5) alongside
                                      cost variance to distinguish
                                      schedule-driven from cost-driven
                                      performance issues.

  PC-10                               The system shall present all
                                      Project Controls metrics on a
                                      unified per-project dashboard with
                                      drill-down to the contributing
                                      transactions in the source module.

  PC-11                               The system shall calculate and
                                      trend all EVM metrics historically
                                      (period-over-period), not only as a
                                      current snapshot, to support
                                      trend-based AI Assistant queries
                                      such as forecasting budget
                                      overruns.
  -----------------------------------------------------------------------

### Business Rules

-   EVM calculations (PC-01 through PC-06) always use the currently
    active baseline (Module 5) and current CBS budget (Module 3), and
    must be recalculable at any prior period-end for audit purposes, not
    only from live current data.
-   A project whose CPI or SPI falls below a configurable threshold
    (default 0.9) automatically surfaces on the Executive Dashboard's
    risk list.

## 4.20 Module 20 --- Asset Management (Code: AST)

### Overview

Manages the completed infrastructure after project handover --- relevant
both for contractors retained on maintenance contracts and for
public-sector/asset-owner clients using SiteForge post-construction.

### Key Data Entities

`Asset` (Building/Road/Bridge/Drainage/Utility), `MaintenanceSchedule`,
`AssetInspection`, `WarrantyRecord`, `DefectsLiabilityRecord`,
`LifecycleCostRecord`.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  AST-01                              The system shall create Asset
                                      records at handover, populated from
                                      the project's As-Built Records
                                      (Module 15) and final BOQ/scope
                                      data.

  AST-02                              The system shall support asset
                                      categories including Buildings,
                                      Roads, Bridges, Drainage, and
                                      Utilities, each with
                                      category-specific attribute sets.

  AST-03                              The system shall maintain a
                                      Maintenance Schedule per asset,
                                      generating recurring maintenance
                                      tasks (routine and periodic) with
                                      due-date tracking.

  AST-04                              The system shall support Asset
                                      Inspections with condition scoring
                                      (e.g., a standard
                                      pavement/structural condition
                                      index) and photographic evidence.

  AST-05                              The system shall track Warranty
                                      records per asset/component with
                                      expiry alerts.

  AST-06                              The system shall manage the Defects
                                      Liability Period (DLP), tracking
                                      defects raised during the DLP,
                                      their resolution, and the retention
                                      release tied to DLP completion
                                      (Module 4/18).

  AST-07                              The system shall support Lifecycle
                                      Cost tracking, accumulating
                                      maintenance and rehabilitation
                                      spend against an asset over its
                                      operational life for
                                      whole-life-cost reporting.

  AST-08                              The system shall support
                                      hierarchical asset structuring
                                      (e.g., a road network containing
                                      individual road sections, each
                                      containing structures such as
                                      culverts) for network-level asset
                                      owners.

  AST-09                              The system shall allow
                                      client/asset-owner users (via the
                                      Client Portal) read access to asset
                                      condition and maintenance history
                                      for assets they own.
  -----------------------------------------------------------------------

### Business Rules

-   Retention release tied to DLP completion (AST-06) requires all
    defects raised during the DLP to be marked resolved and verified;
    the system blocks the release action otherwise.
-   Asset records (AST-01) are immutable as to their original as-built
    baseline; all subsequent changes are recorded as dated
    condition/maintenance events layered on top of that baseline.

## 4.21 Module 21 --- Executive Dashboard (Code: EXD)

### Overview

A single-screen, role-configured view for company leadership,
aggregating data that every other module produces.

### Key Data Entities

This module is primarily a read/aggregation layer; it introduces no new
core business entities but defines `DashboardWidget` and
`DashboardConfiguration` for personalization.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  EXD-01                              The system shall display
                                      consolidated Company Revenue
                                      (actual vs. budget) across all
                                      active projects and companies
                                      (Module 17).

  EXD-02                              The system shall display Project
                                      Profitability per project (revenue
                                      recognized minus actual cost, per
                                      Module 19).

  EXD-03                              The system shall display
                                      consolidated Cash Position across
                                      all bank accounts and companies
                                      (Module 17).

  EXD-04                              The system shall display Equipment
                                      Utilization company-wide and by
                                      category (Module 9).

  EXD-05                              The system shall display a Safety
                                      Score (composite of Module 14's
                                      leading/lagging indicators) per
                                      project and company-wide.

  EXD-06                              The system shall display Active
                                      Projects with status, % complete,
                                      and CPI/SPI (Module 19).

  EXD-07                              The system shall display the Tender
                                      Pipeline value and win-rate trend
                                      (Module 1/2).

  EXD-08                              The system shall display Accounts
                                      Receivable and Accounts Payable
                                      aging summaries (Module 17/18).

  EXD-09                              The system shall display Profit
                                      Margin trends by project, client,
                                      and project type.

  EXD-10                              The system shall display Labor
                                      Productivity metrics (Module 11
                                      cost allocation against Module 19
                                      earned value).

  EXD-11                              The system shall display a
                                      consolidated Project Risks list
                                      drawn from Module 19's Risk
                                      Register and threshold-breach
                                      flags.

  EXD-12                              The system shall support role-based
                                      dashboard configuration, so a
                                      Regional Director sees only their
                                      region's data while a Group CEO
                                      sees the full consolidation.

  EXD-13                              The system shall support
                                      natural-language querying of
                                      dashboard data via the AI
                                      Construction Assistant (Module 25).

  EXD-14                              The system shall support scheduled
                                      dashboard export/distribution
                                      (e.g., a Monday-morning PDF emailed
                                      to the board).
  -----------------------------------------------------------------------

### Business Rules

-   Dashboard figures are always traceable to source-module transactions
    via drill-down; the Executive Dashboard never stores an
    independently-editable number.

## 4.22 Module 22 --- Client Portal (Code: CLP)

### Overview

Gives the paying client (or asset owner) self-service visibility and
approval capability without needing full platform access.

### Key Data Entities

`ClientPortalUser`, `ClientApprovalAction` --- otherwise reads from the
core project entities with a restricted, client-scoped view.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  CLP-01                              The system shall allow client users
                                      to Track Progress against the
                                      schedule and physical completion
                                      percentage.

  CLP-02                              The system shall allow client users
                                      to View Photos and site diary
                                      summaries relevant to their
                                      project.

  CLP-03                              The system shall allow client users
                                      to Approve Variations (Variation
                                      Orders, Module 18) online, with a
                                      recorded digital approval and
                                      timestamp.

  CLP-04                              The system shall allow client users
                                      to Download Reports (progress
                                      reports, quality summaries) in PDF
                                      format.

  CLP-05                              The system shall allow client users
                                      to Approve Invoices/Progress
                                      Certificates online, feeding Module
                                      18's certification workflow.

  CLP-06                              The system shall allow client users
                                      to Review Schedules (read-only
                                      Gantt view) without exposing
                                      internal cost data.

  CLP-07                              The system shall allow client users
                                      to Submit Requests (e.g., RFIs to
                                      the contractor, service requests
                                      for asset-owner clients) tracked to
                                      resolution.

  CLP-08                              The system shall restrict Client
                                      Portal users to data for
                                      projects/assets explicitly assigned
                                      to their organization, enforced by
                                      the same tenant-and-scope isolation
                                      used elsewhere in the platform.
  -----------------------------------------------------------------------

### Business Rules

-   A Client Portal user can never view another client's project data,
    internal cost/margin data, or internal-only communications,
    regardless of any misconfiguration elsewhere in the permission
    matrix (defense in depth via a dedicated client-scope filter).

## 4.23 Module 23 --- Vendor Portal (Code: VNP)

### Overview

Gives suppliers and subcontractors self-service visibility into orders
and payment status, reducing procurement administrative overhead.

### Key Data Entities

`VendorPortalUser` --- otherwise reads/writes against Module 7 and 12
entities with vendor-scoped access.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  VNP-01                              The system shall allow vendor users
                                      to Receive Orders (Purchase Orders,
                                      Module 7) electronically with
                                      acknowledgment capability.

  VNP-02                              The system shall allow vendor users
                                      to Submit Quotes in response to an
                                      RFQ (Module 7) directly through the
                                      portal.

  VNP-03                              The system shall allow vendor users
                                      to Upload Invoices against a
                                      received Purchase Order or
                                      subcontract certificate.

  VNP-04                              The system shall allow vendor users
                                      to Track Payments (status and
                                      expected date) for their submitted
                                      invoices.

  VNP-05                              The system shall allow vendor users
                                      to Update Company Information
                                      (contacts, banking details,
                                      compliance document renewal)
                                      subject to internal review/approval
                                      before the change takes effect on
                                      live records.
  -----------------------------------------------------------------------

### Business Rules

-   A vendor-submitted banking-detail change (VNP-05) requires internal
    Finance approval before it can be used for payment, as a
    fraud-prevention control against payment-redirection attacks.

## 4.24 Module 24 --- Mobile Field App (Code: MFA)

### Overview

The primary interface for site-based roles; offline-first by design, per
the architectural constraint in Section 2.5 and Section 3.5.

### Key Data Entities

Mirrors server-side entities for the assigned user's projects in a local
SQLite store; introduces `SyncQueueEntry` and `ConflictRecord` for
offline operation management.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  MFA-01                              The system shall allow Site
                                      Engineers to Capture Photos with
                                      automatic geotagging, timestamping,
                                      and association to a diary entry,
                                      activity, or inspection.

  MFA-02                              The system shall allow Site
                                      Engineers to Record Progress
                                      against WBS activities and BOQ
                                      items while offline.

  MFA-03                              The system shall allow Site
                                      Engineers to Scan QR Codes for
                                      material issue/receipt and
                                      equipment identification (Module
                                      8/9).

  MFA-04                              The system shall allow Site
                                      Engineers to Approve Materials
                                      (delivery/quality acceptance) at
                                      point of receipt.

  MFA-05                              The system shall allow Site
                                      Engineers to Record Attendance for
                                      their crew, including casual
                                      workers, via the mobile device.

  MFA-06                              The system shall allow Site
                                      Engineers to Complete Checklists
                                      (ITPs, safety audits, permits) with
                                      required-field enforcement even
                                      while offline.

  MFA-07                              The system shall allow Site
                                      Engineers to Upload Documents
                                      (delivery notes, signed forms)
                                      captured via the device camera or
                                      file picker.

  MFA-08                              The system shall Sync Automatically
                                      when connectivity is available, in
                                      the background, without requiring
                                      the user to manually trigger a sync
                                      for routine operation.

  MFA-09                              The system shall clearly indicate
                                      Sync Status (pending, syncing,
                                      synced, conflict) per record to the
                                      user.

  MFA-10                              The system shall support a full
                                      offline session of at least 7 days
                                      of typical site activity without
                                      data loss, per local storage
                                      capacity planning.

  MFA-11                              The system shall enforce the same
                                      role-based permission restrictions
                                      offline as online, using a locally
                                      cached permission snapshot
                                      refreshed at each successful sync.
  -----------------------------------------------------------------------

### Business Rules

-   No mobile-captured record is considered final/official until
    successfully synced and accepted by the server; the UI must never
    represent a pending-sync record as equivalent to a confirmed server
    record.
-   Conflict Records (per Section 3.5) are never silently discarded;
    they are surfaced for review per the conflict-resolution rule
    defined in the architecture section.

## 4.25 Module 25 --- AI Construction Assistant (Code: AI)

### Overview

A long-term differentiator layered across the entire platform:
natural-language query and document-automation capability grounded in
the tenant's own project data.

### Key Data Entities

`AIQueryLog`, `AIGeneratedReport`, `AIDocumentExtractionJob` ---
otherwise operates as a read/generate layer over all other modules'
data, scoped strictly per tenant.

### Functional Requirements

  -----------------------------------------------------------------------
  ID                                  Requirement
  ----------------------------------- -----------------------------------
  AI-01                               The system shall answer
                                      natural-language questions about
                                      project status, e.g., "Which
                                      project is likely to exceed budget
                                      next month?", grounded in Module
                                      19's forecast data.

  AI-02                               The system shall answer
                                      natural-language questions about
                                      equipment status, e.g., "Show me
                                      all idle excavators," grounded in
                                      Module 9's utilization data
                                      (EQP-11).

  AI-03                               The system shall answer
                                      natural-language questions about
                                      schedule causation, e.g., "Why is
                                      Project A delayed?", grounded in
                                      Module 5's delay events and Module
                                      19's schedule variance.

  AI-04                               The system shall Forecast Cash Flow
                                      on request, extending Module 19's
                                      cash flow forecast with narrative
                                      explanation of key drivers.

  AI-05                               The system shall Generate Executive
                                      Reports on request or schedule,
                                      compiling data from the Executive
                                      Dashboard (Module 21) into a
                                      formatted narrative document.

  AI-06                               The system shall Read BOQs from
                                      PDFs, extracting item code,
                                      description, unit, and quantity
                                      into Module 3's BOQ Builder,
                                      flagging low-confidence extractions
                                      for human review rather than
                                      silently guessing.

  AI-07                               The system shall Extract Invoice
                                      Data from vendor invoice
                                      images/PDFs into Module 7's
                                      invoice-matching workflow,
                                      similarly flagging low-confidence
                                      fields.

  AI-08                               The system shall Summarize Site
                                      Diaries across a date range into a
                                      condensed narrative for reporting
                                      purposes, always linking back to
                                      the source diary entries.

  AI-09                               The system shall Predict Equipment
                                      Failures using historical
                                      maintenance and downtime patterns
                                      (Module 9), surfacing a risk score
                                      rather than a false-certain
                                      prediction.

  AI-10                               The system shall Forecast Material
                                      Shortages by comparing procurement
                                      lead times and consumption trends
                                      (Modules 7/8) against the schedule
                                      (Module 5).

  AI-11                               The system shall Detect Unusual
                                      Spending by flagging cost postings
                                      (Module 17) that deviate materially
                                      from historical or budgeted
                                      patterns for the same cost code.

  AI-12                               The system shall Answer
                                      Natural-Language Questions over
                                      project data generally, using
                                      tool-calling to retrieve structured
                                      data rather than generating answers
                                      from unstructured guesswork.

  AI-13                               The system shall log every AI
                                      Assistant query and the exact
                                      context retrieved to answer it, for
                                      auditability.

  AI-14                               The system shall never include data
                                      from a tenant other than the
                                      requesting user's tenant in any AI
                                      Assistant context, response, or
                                      generated document, enforced by the
                                      same Row-Level Security used
                                      elsewhere in the platform (Section
                                      3.4).
  -----------------------------------------------------------------------

### Business Rules

-   Any AI-generated figure that feeds a financial or contractual
    document (e.g., an AI-drafted report referencing revenue figures)
    must cite its source module/transaction; the Assistant does not
    present a number it cannot trace.
-   Document extraction (AI-06, AI-07) always produces a
    human-reviewable draft; it never auto-commits extracted data
    directly into a financial or contractual record without explicit
    user confirmation.

# 5. Database Schema and Entity Relationships

## 5.1 Schema Design Principles

-   Every table that stores tenant-specific data carries a
    `tenant_id UUID NOT NULL` column and a Row-Level Security policy
    (Section 3.4).
-   Primary keys are UUIDs (not auto-increment integers) to support
    offline mobile record creation without server round-trips and to
    avoid leaking sequence-based record counts across tenants.
-   Every table carries `created_at`, `updated_at`, `created_by`,
    `updated_by` audit columns.
-   Soft deletes (`deleted_at NULLABLE`) are used for records with
    downstream financial or contractual implications; hard deletes are
    reserved for genuinely transient data (e.g., draft-only records
    never submitted).
-   Monetary columns are `NUMERIC(18,4)` (fixed-point), never floating
    point, per Section 2.5.
-   All foreign keys are enforced at the database level; the ORM does
    not simulate referential integrity in application code alone.

## 5.2 Core Cross-Module Entities

These entities are shared/referenced across most modules and form the
backbone of traceability described in Section 2.1.

  -----------------------------------------------------------------------
  Table                   Key Columns             Referenced By
  ----------------------- ----------------------- -----------------------
  `tenants`               id, name,               every tenant-scoped
                          subscription_plan,      table
                          region                  

  `companies`             id, tenant_id, name,    financial, contracts
                          base_currency           

  `users`                 id, tenant_id, email,   every user-attributed
                          role_id, status         record

  `roles`                 id, tenant_id, name,    users, permission
                          permission_set (JSONB)  matrix

  `projects`              id, tenant_id,          virtually every module
                          company_id,             
                          contract_id, name,      
                          status                  

  `boq_items`             id, project_id,         estimating, planning,
                          wbs_node_id, item_code, execution, billing
                          description, unit,      
                          contracted_qty, rate    

  `cost_codes`            id, project_id,         CBS, procurement,
                          boq_item_id, code,      finance, controls
                          budget_amount           

  `wbs_nodes`             id, project_id,         planning, execution,
                          parent_id, name,        controls
                          sequence                

  `vendors`               id, tenant_id, name,    procurement, inventory,
                          tax_id, status          finance

  `employees`             id, tenant_id, name,    workforce, execution,
                          role, competency_ids    HSE

  `equipment`             id, tenant_id,          equipment, fuel,
                          project_id (nullable),  execution
                          asset_tag               

  `documents`             id, tenant_id,          virtually every module
                          project_id, file_key    
                          (S3), doc_type          
  -----------------------------------------------------------------------

## 5.3 Illustrative Entity-Relationship Diagram (Core Lifecycle)

    tenants (1)───(n) companies (1)───(n) projects
                                           │
            ┌──────────────────┬──────────┼───────────────┬─────────────────┐
            │                  │          │               │                 │
       tenders(1:1)      contracts(1:1)  wbs_nodes(1:n)  boq_items(1:n)  cost_codes(1:n)
            │                  │          │               │                 │
       tender_boq_items    contract_    activities(1:n)  rate_analyses   budget_lines
                            documents         │               │                 │
                                        daily_site_diaries  vendor_quotes  gl_entries
                                              │
                                     progress_entries ── measurement_sheets ── progress_certificates
                                              │
                                      equipment_usage_records ── equipment(1:n per project)
                                              │
                                      labor_usage_records ── employees(1:n per project)

## 5.4 Representative Table Definitions

The following are illustrative (not exhaustive) definitions for the
highest-traffic tables. Full DDL for all \~180 tables across the 25
modules is maintained in the Alembic migration history, not duplicated
here.

### `boq_items`

    id                UUID PRIMARY KEY
    tenant_id         UUID NOT NULL REFERENCES tenants(id)
    project_id        UUID NOT NULL REFERENCES projects(id)
    wbs_node_id       UUID REFERENCES wbs_nodes(id)
    item_code         VARCHAR(64) NOT NULL
    description       TEXT NOT NULL
    unit              VARCHAR(16) NOT NULL
    contracted_qty    NUMERIC(18,4) NOT NULL
    rate              NUMERIC(18,4) NOT NULL
    cumulative_billed_qty NUMERIC(18,4) NOT NULL DEFAULT 0
    created_at / updated_at / created_by / updated_by
    UNIQUE (project_id, item_code)

### `daily_site_diaries`

    id                UUID PRIMARY KEY
    tenant_id         UUID NOT NULL
    project_id        UUID NOT NULL REFERENCES projects(id)
    diary_date        DATE NOT NULL
    weather           JSONB
    narrative         TEXT
    signed_by         UUID REFERENCES users(id)
    signed_at         TIMESTAMPTZ
    sync_source       VARCHAR(16) -- 'web' | 'mobile'
    client_uuid       UUID -- for offline-created records, de-dupe key
    UNIQUE (project_id, diary_date, client_uuid)

### `gl_entries`

    id                UUID PRIMARY KEY
    tenant_id         UUID NOT NULL
    company_id        UUID NOT NULL REFERENCES companies(id)
    project_id        UUID REFERENCES projects(id)
    cost_code_id      UUID REFERENCES cost_codes(id)
    account_id        UUID NOT NULL REFERENCES chart_of_accounts(id)
    debit             NUMERIC(18,4) NOT NULL DEFAULT 0
    credit            NUMERIC(18,4) NOT NULL DEFAULT 0
    currency          CHAR(3) NOT NULL
    fx_rate           NUMERIC(18,6) NOT NULL DEFAULT 1
    source_module     VARCHAR(32) NOT NULL
    source_record_id  UUID NOT NULL
    posted_at         TIMESTAMPTZ NOT NULL
    CHECK (debit = 0 OR credit = 0)  -- a line is either a debit or a credit, never both

### `equipment_usage_records`

    id                UUID PRIMARY KEY
    tenant_id         UUID NOT NULL
    project_id        UUID NOT NULL REFERENCES projects(id)
    equipment_id      UUID NOT NULL REFERENCES equipment(id)
    usage_date        DATE NOT NULL
    hours_operated    NUMERIC(6,2)
    fuel_issued_liters NUMERIC(10,2)
    operator_id       UUID REFERENCES employees(id)
    activity_id       UUID REFERENCES activities(id)

## 5.5 Row-Level Security Policy Pattern

Every tenant-scoped table applies the same policy shape:

    ALTER TABLE boq_items ENABLE ROW LEVEL SECURITY;

    CREATE POLICY tenant_isolation ON boq_items
      USING (tenant_id = current_setting('app.tenant_id')::uuid);

The Flask request-scoped session sets `app.tenant_id` once at request
start:

    SET LOCAL app.tenant_id = '<tenant-uuid-from-verified-jwt>';

This ensures that even a query missing an explicit
`WHERE tenant_id = ...` clause cannot return another tenant's rows.

## 5.6 Indexing Strategy

-   Composite index `(tenant_id, project_id)` on every project-scoped
    table, since nearly all queries filter by both.
-   Partial indexes on frequently-filtered status columns (e.g.,
    `WHERE status = 'open'` on NCRs, permits, purchase orders) to keep
    operational dashboard queries fast as history accumulates.
-   GIN indexes on JSONB columns used for custom fields and AI Assistant
    context retrieval.
-   Full-text search indexes on `description` fields (BOQ items, NCRs,
    site issues) to support the AI Assistant's natural-language
    retrieval and general in-app search.

## 5.7 Data Retention and Archival

Transactional data is retained indefinitely by default (construction
contracts commonly carry liability periods of 10+ years). Tenants may
configure archival of closed-project data to cheaper storage tiers after
a configurable period, with archived data remaining queryable (at higher
latency) rather than deleted, to preserve audit and warranty-period
obligations.

# 6. API Contracts

## 6.1 Conventions

-   **Base URL:** `https://api.siteforge.app/v1/`
-   **Format:** JSON request/response bodies;
    `Content-Type: application/json`.
-   **Documentation:** Full OpenAPI 3.1 specification maintained
    alongside the codebase and published to an internal developer
    portal; this section defines conventions and representative
    endpoints only.
-   **Resource naming:** plural nouns matching the module's key entities
    (e.g., `/boq-items`, `/purchase-orders`).
-   **Pagination:** cursor-based (`?cursor=...&limit=50`), returning
    `next_cursor` in the response envelope, since offset pagination
    degrades on large transactional tables.
-   **Filtering:** query parameters map to indexed columns (e.g.,
    `?project_id=...&status=open`).
-   **Errors:** RFC 7807 Problem Details format (`type`, `title`,
    `status`, `detail`, `instance`).
-   **Idempotency:** all mutating mobile-sync endpoints require an
    `Idempotency-Key` header (the client-generated UUID) so a retried
    sync request cannot create a duplicate record.

## 6.2 Authentication

-   `POST /v1/auth/login` --- email/password (or SSO token) →
    short-lived access token (15 min) + refresh token (30 days, rotated
    on use).
-   `POST /v1/auth/refresh` --- refresh token → new access token.
-   `POST /v1/auth/logout` --- revokes the refresh token.
-   Access tokens are JWTs carrying `tenant_id`, `user_id`, `role_id`,
    and `permissions` claims, verified on every request and used to set
    the RLS session variable (Section 5.5).
-   All external portal users (Client Portal, Vendor Portal)
    authenticate through the same endpoint family but receive tokens
    scoped to a restricted permission set (Section 8).

## 6.3 Representative Endpoint Groups

### Tender & Estimating

    GET    /v1/tenders
    POST   /v1/tenders
    GET    /v1/tenders/{id}
    POST   /v1/tenders/{id}/boq-import        (multipart file upload)
    GET    /v1/tenders/{id}/rfis
    POST   /v1/tenders/{id}/submit            (enforces TBM-12 checklist gate)

    GET    /v1/projects/{id}/boq-items
    POST   /v1/projects/{id}/boq-items/{item_id}/rate-analysis
    POST   /v1/estimates/{id}/versions        (creates a new version, EST-14)

### Project Execution

    GET    /v1/projects/{id}/daily-diaries?date=2026-07-24
    POST   /v1/projects/{id}/daily-diaries
    POST   /v1/projects/{id}/daily-diaries/{diary_id}/sign
    POST   /v1/sync/batch                     (mobile offline batch upload, Section 3.5)
    GET    /v1/sync/pull?since=<server_cursor> (mobile incremental download)

### Procurement & Inventory

    POST   /v1/rfqs
    POST   /v1/rfqs/{id}/quotations
    POST   /v1/purchase-orders
    POST   /v1/purchase-orders/{id}/approve
    POST   /v1/goods-receipt-notes
    GET    /v1/warehouses/{id}/stock
    POST   /v1/stock-transfers

### Financial

    GET    /v1/projects/{id}/cost-report
    POST   /v1/progress-certificates
    POST   /v1/progress-certificates/{id}/approve   (Client Portal endpoint, restricted scope)
    GET    /v1/companies/{id}/financial-statements?period=2026-Q2

### Project Controls

    GET    /v1/projects/{id}/evm?as_of=2026-07-24
    GET    /v1/projects/{id}/cash-flow-forecast
    GET    /v1/dashboard/executive

### AI Construction Assistant

    POST   /v1/ai/query               { "prompt": "Which project is likely to exceed budget next month?" }
    POST   /v1/ai/extract/boq         (multipart PDF upload → draft BOQ items, AI-06)
    POST   /v1/ai/extract/invoice     (multipart file upload → draft invoice data, AI-07)
    POST   /v1/ai/reports/generate    { "report_type": "executive_weekly", "project_id": "..." }
    GET    /v1/ai/query-log           (audit trail, AI-13)

## 6.4 Representative Payloads

**Create Purchase Order ---** `POST /v1/purchase-orders`

    {
      "project_id": "b3f1...-uuid",
      "vendor_id": "a91c...-uuid",
      "currency": "NGN",
      "line_items": [
        {
          "cost_code_id": "f02e...-uuid",
          "description": "20mm graded aggregate",
          "unit": "m3",
          "quantity": 250,
          "unit_price": 18500.00
        }
      ],
      "delivery_address": "Site Store - Lekki Phase 2",
      "required_by": "2026-08-05"
    }

Response (`201 Created`) echoes the created resource with a
server-assigned `po_number`, `status: "pending_approval"`, and an
`approval_chain` array showing each required approver and their current
status, per PRC-06.

**Mobile Sync Batch ---** `POST /v1/sync/batch`

    {
      "device_id": "device-uuid",
      "records": [
        {
          "entity": "daily_site_diary",
          "client_uuid": "c7d2...-uuid",
          "operation": "create",
          "client_timestamp": "2026-07-24T07:15:00Z",
          "payload": { "project_id": "...", "diary_date": "2026-07-24", "weather": {"condition": "clear"} }
        },
        {
          "entity": "equipment_usage_record",
          "client_uuid": "e4a1...-uuid",
          "operation": "create",
          "client_timestamp": "2026-07-24T09:02:00Z",
          "payload": { "equipment_id": "...", "hours_operated": 6.5 }
        }
      ]
    }

Response returns, per record, either
`{"status": "accepted", "server_id": "..."}` or
`{"status": "conflict", "conflict_id": "..."}` per the conflict-handling
rule in Section 3.5, never a bare success/failure for the whole batch.

## 6.5 Webhooks (Outbound)

For integration with external systems (Section 3.7) and for notifying
tenant-side systems of state changes:

    project.milestone_completed
    progress_certificate.approved
    purchase_order.approved
    equipment.maintenance_due
    hse.incident_reported

Webhook payloads are signed (HMAC-SHA256) with a per-tenant secret, and
delivery is retried with exponential backoff up to 24 hours, after which
the event is surfaced in an in-app "failed webhook deliveries" log for
manual replay.

## 6.6 Rate Limiting

Default: 600 requests/minute per tenant for standard API usage, 60
requests/minute for AI Assistant endpoints (given upstream model-call
cost and latency), configurable per subscription tier. Mobile sync
endpoints are exempt from the standard limit but capped by payload size
(max 500 records per sync batch) to bound per-request processing time.

## 6.7 Versioning

The API is versioned by URL path segment (`/v1/`, `/v2/`). Breaking
changes are only introduced in a new major version; a deprecated version
is supported for a minimum of 12 months after the successor version's
general availability, communicated via the `Sunset` HTTP header.

# 7. UI/UX Specifications and Page-Level Flows

## 7.1 Navigation Model

SiteForge's primary web navigation is organized around the project
lifecycle (Section 2.1), not around departments. The left-hand
navigation rail shows:

1.  **Home** (role-appropriate dashboard --- Executive Dashboard for
    executives, My Tasks for site roles)
2.  **Business Development** (Module 1)
3.  **Tenders** (Module 2)
4.  **Projects** --- the primary workspace, expanding to a
    project-specific sub-navigation covering Estimating, Contract,
    Planning, Execution, Procurement, Inventory, Equipment, Workforce,
    Subcontractors, Quality, HSE, Survey, Finance, Billing, Controls
5.  **Company** --- cross-project modules: Vendors, Equipment Fleet
    (company-wide view), Workforce (company-wide), Financial Management,
    Asset Management
6.  **Reports & AI Assistant**
7.  **Admin** (tenant configuration, users, roles --- visible only to
    Administrator role)

## 7.2 Key Page Flows

### 7.2.1 Tender-to-Contract Flow (Modules 1--4)

1.  **Opportunity List** → filter by stage → open an Opportunity.
2.  **Opportunity Detail** → Bid/No-Bid decision panel → on "Bid"
    decision, "Create Tender" action generates a linked Tender record.
3.  **Tender Workspace** → tabs: Overview \| BOQ \| RFIs \| Documents \|
    Checklist \| Approval.
4.  **BOQ tab** → import wizard (column mapping preview before commit) →
    opens into the Estimating workspace.
5.  **Estimating Workspace** → BOQ tree (left) with rate analysis panel
    (right) opening per selected item → summary ribbon showing running
    tender price, markup, and margin.
6.  **Approval tab** → sequential approval stepper showing each required
    approver's status → "Submit" button disabled until all steps and
    checklist items are green (TBM-12).
7.  On win: **"Convert to Contract"** action → Contract Workspace
    pre-populated from the tender, prompting only for contract-specific
    fields (bond details, payment terms) not already captured.

### 7.2.2 Daily Site Diary Flow (Mobile, Module 6/24)

1.  **Today** screen (mobile home) → shows the current project's diary
    status (not started / in progress / signed).
2.  **Diary Entry** screen → sectioned form: Weather (auto-suggested
    from device location + API when online) → Workforce Present
    (quick-add from crew list) → Equipment On Site (scan QR or select) →
    Progress (tap an activity to log % or quantity) → Photos (camera
    roll or in-app capture) → Issues (quick-add with severity).
3.  Each section auto-saves locally; a status chip shows "Saved locally"
    vs. "Synced."
4.  **Sign-off** screen → summary review → signature capture
    (finger/stylus) → diary becomes read-only, with an "Add Amendment"
    option only, per the business rule in Section 4.6.

### 7.2.3 Procurement Flow (Module 7)

1.  **Purchase Request** form → cost-code selector (shows remaining
    budget live, PRC-04) → submit.
2.  **RFQ Workspace** → vendor multi-select → auto-generated RFQ
    documents per vendor → response tracker.
3.  **Quotation Comparison** view → grid with vendors as columns, line
    items as rows, lowest-price cells highlighted, non-price factors
    (lead time, terms) shown in a secondary row.
4.  **Purchase Order** generated from selected quotation → approval
    stepper (value-threshold-driven, PRC-06) → issued PO emailed to
    vendor and visible in the Vendor Portal.
5.  **Goods Receipt** (mobile or web) → PO line items pre-filled →
    quantity/condition entry → discrepancy flag if received ≠ ordered.

### 7.2.4 Progress Certificate Flow (Module 18/22)

1.  **Measurement Sheet** compiled from Module 6 work-completed records
    for the billing period.
2.  **Draft Certificate** → BOQ items with contracted qty, previously
    billed, this period, cumulative, retention calculation shown inline.
3.  Internal approval (PM/QS) → routes to **Client Portal** for external
    approval (CLP-05) → status visible in real time to both internal
    users and the client.
4.  On client approval → automatically posts to Accounts Receivable
    (FIN-03) and updates the Retention Ledger.

### 7.2.5 Executive Dashboard (Module 21)

Single scrollable page, top-to-bottom: KPI strip (Revenue, Cash,
Profitability, Safety Score) → Active Projects table (sortable by
CPI/SPI, color-coded risk) → Tender Pipeline funnel chart → AR/AP aging
chart → Equipment Utilization heat-map → Risks list. An embedded chat
input at the top allows direct natural-language queries to the AI
Assistant (EXD-13), with responses rendered inline as chart widgets or
text as appropriate to the query.

## 7.3 Design System Notes

-   Data-dense grids (BOQ, Gantt, quotation comparison) use a
    fixed-header, virtualized-row table component to remain performant
    with thousands of line items per project.
-   Every list/grid view supports column configuration, saved filters,
    and export to Excel/PDF, since procurement and finance users
    routinely need to work with data outside the platform for
    client/auditor submission.
-   Offline status is a persistent, unmissable UI element on mobile (not
    a subtle icon) given the operational consequence of unsynced data
    (Section 3.5).
-   Color coding for status is consistent platform-wide: green (on
    track/approved/complete), amber (attention needed/pending), red
    (overdue/rejected/breach), and this mapping is never repurposed for
    a different meaning within a single module --- a color always means
    the same status class everywhere in the product.

## 7.4 Accessibility

The web application targets WCAG 2.1 AA: keyboard navigability for all
primary workflows, sufficient color contrast (status colors are paired
with icons/text, not color alone), and screen-reader labeling for all
form controls, given the diversity of literacy levels and
assistive-technology needs among site-based users.

# 8. Permission Matrix

## 8.1 Model

SiteForge uses Role-Based Access Control (RBAC) with per-tenant
customizable roles built from a base set of permission templates. Each
permission is expressed as `module:action` (e.g., `procurement:approve`,
`finance:post`). Roles are assigned per user and, where relevant, scoped
to specific projects (a Project Manager may hold their role only on the
projects they are assigned to, not company-wide).

Access is evaluated at three layers, all of which must pass: 1.
**Authentication** --- valid, unexpired token. 2. **Tenant scope** ---
Row-Level Security restricts all queries to the user's tenant (Section
3.4). 3. **Role/project scope** --- the permission set attached to the
user's role, further filtered to the projects/records they are assigned
to.

## 8.2 Matrix (Representative --- × = full access, R = read-only, A = approve-only, --- = no access)

The full role set is split across two tables for readability; both cover
the same 25 modules.

**Table 8.2a --- Internal Operational Roles**

  ----------------------------------------------------------------------------------------------------
  Module          Exec     PM          Site Eng.   QS/Estimator   Procurement   Storekeeper   Fleet
                                                                                              Mgr
  --------------- -------- ----------- ----------- -------------- ------------- ------------- --------
  Business Dev &  R        R           ---         R              ---           ---           ---
  CRM                                                                                         

  Tender & Bid    R        R           ---         ×              R             ---           ---

  Estimating      R        R           ---         ×              R             ---           ---

  Contract Mgmt   R        ×           ---         R              ---           ---           ---

  Planning        R        ×           R           R              ---           ---           ---

  Execution       R        ×           ×           R              ---           R             R

  Procurement     R        R           R (request) R              ×             R             R

  Inventory       R        R           R           R              R             ×             R

  Equipment &     R        R           R           R              R             ---           ×
  Fleet                                                                                       

  Fuel Mgmt       R        R           R           ---            ---           R             ×

  Workforce       R        R           R (own      ---            ---           ---           ---
                                       crew)                                                  

  Subcontractor   R        ×           R           R              R             ---           ---
  Mgmt                                                                                        

  Quality (QMS)   R        R           R           ---            ---           ---           ---

  HSE             R        R           R           ---            ---           ---           ---

  Survey &        R        R           ×           R              ---           ---           ---
  Engineering                                                                                 

  Plant & Quarry  R        R           R           R              R             R             ×

  Financial Mgmt  R        R (project  ---         R              R             ---           ---
                           cost only)                                                         

  Client Billing  R        ×           R           R              ---           ---           ---

  Project         ×        ×           R           R              ---           ---           ---
  Controls                                                                                    

  Asset Mgmt      R        R           R           ---            ---           ---           ---

  Executive       ×        R (own      ---         ---            ---           ---           ---
  Dashboard                projects)                                                          

  Client Portal   ---      R           ---         ---            ---           ---           ---
  admin                                                                                       

  Vendor Portal   ---      ---         ---         ---            R             ---           ---
  admin                                                                                       

  AI Assistant    ×        ×           R (query    ×              R             ---           R
                                       own                                                    
                                       projects)                                              

  Admin Console   ---      ---         ---         ---            ---           ---           ---
  ----------------------------------------------------------------------------------------------------

**Table 8.2b --- Back-Office, External, and Administrative Roles**

  ------------------------------------------------------------------------------------------
  Module          HR/Payroll   Finance   QA/QC    HSE Officer Client     Vendor     Admin
                                                              (Portal)   (Portal)   
  --------------- ------------ --------- -------- ----------- ---------- ---------- --------
  Business Dev &  ---          ---       ---      ---         ---        ---        ×
  CRM                                                                               

  Tender & Bid    ---          ---       ---      ---         ---        ---        ×

  Estimating      ---          R         ---      ---         ---        ---        ×

  Contract Mgmt   ---          R         ---      ---         R          ---        ×

  Planning        ---          ---       ---      ---         R          ---        ×

  Execution       ---          ---       R        R           R          ---        ×

  Procurement     ---          R         ---      ---         ---        R          ×

  Inventory       ---          R         ---      ---         ---        ---        ×

  Equipment &     ---          R         ---      ---         ---        ---        ×
  Fleet                                                                             

  Fuel Mgmt       ---          R         ---      ---         ---        ---        ×

  Workforce       ×            R         ---      R (medical: ---        ---        ×
                                                  no)                               

  Subcontractor   ---          R         ---      ---         ---        ---        ×
  Mgmt                                                                              

  Quality (QMS)   ---          ---       ×        R           R          ---        ×

  HSE             R            ---       R        ×           R          ---        ×

  Survey &        ---          ---       R        ---         R          ---        ×
  Engineering                                                                       

  Plant & Quarry  ---          R         R        ---         ---        ---        ×

  Financial Mgmt  R            ×         ---      ---         ---        ---        ×

  Client Billing  ---          ×         ---      ---         A          ---        ×

  Project         ---          R         ---      ---         R          ---        ×
  Controls                                                                          

  Asset Mgmt      ---          ---       R        ---         R          ---        ×

  Executive       ---          R         ---      ---         ---        ---        ×
  Dashboard                                                                         

  Client Portal   ---          ---       ---      ---         × (own     ---        ×
  admin                                                       org)                  

  Vendor Portal   ---          ---       ---      ---         ---        × (own     ×
  admin                                                                  org)       

  AI Assistant    ---          R         R        R           ---        ---        ×

  Admin Console   ---          ---       ---      ---         ---        ---        ×
  ------------------------------------------------------------------------------------------

## 8.3 Field-Level Restrictions

Some restrictions are finer than module-level access and are enforced at
the field level regardless of the role's general module access:

-   **Medical Records (Module 11):** hidden from all roles except HR and
    HSE Officer, even for roles with otherwise full Workforce access
    (Section 4.11 business rule).
-   **Vendor Banking Details:** editable by Finance role only, even
    though Procurement has broader Vendor record access (Section
    4.7/4.23 business rule).
-   **Salary/Pay Rate fields:** visible only to HR/Payroll and Finance
    roles; a Project Manager sees labor cost totals but not individual
    pay rates.
-   **Margin/Markup fields on Estimating:** hidden from any role without
    an explicit "view margin" permission, since site-level and even some
    project-management roles are commonly restricted from seeing profit
    margin in construction businesses.

## 8.4 External User Scoping

Client Portal and Vendor Portal users are additionally restricted by an
organization-scope filter independent of role permissions: even a
permission that would nominally allow reading "all projects" is
intersected with "projects/orders belonging to this external
organization" before any data is returned, per the defense-in-depth
principle stated in Section 4.22/4.23.

## 8.5 Permission Configuration

Tenant Administrators may create custom roles by combining permission
templates, but may not grant a custom role any permission the tenant's
subscription tier does not include (e.g., a tenant without the Plant &
Quarry module licensed cannot grant `plant_quarry:*` permissions to any
role, since the module is not provisioned for that tenant at all).

# 9. Cross-Cutting Business Rules

Module-specific business rules are stated alongside each module in
Section 4. The rules below apply platform-wide.

## 9.1 Traceability

Every financial figure presented anywhere in the platform (Executive
Dashboard, client-facing report, AI Assistant response) must be
traceable, via drill-down, to the source transaction and originating
module. No module may display a manually-overridable "summary number"
that is not derived from underlying transactions.

## 9.2 Baseline Immutability

Any record designated a "baseline" (Cost Breakdown Structure, Schedule
Baseline, As-Built Record, Asset handover baseline) is immutable once
approved. Changes are captured as new, dated versions or explicit
revision records, never as edits to the original.

## 9.3 Approval Before Commitment

Any transaction with external financial or contractual consequence
(Purchase Order, Progress Certificate, Variation Order, Contract
Amendment) requires the configured approval workflow to complete before
it takes effect. Draft states are always visually distinct from approved
states.

## 9.4 Budget Awareness

Every cost-incurring action (Purchase Request, Purchase Order,
Subcontract Certificate) is checked in real time against the relevant
CBS cost-code budget and, per tenant configuration, either blocks or
warns on breach (Section 4.17 FIN-04).

## 9.5 Offline Parity

Any function available to a site-based role on the web must be available
offline on the Mobile Field App, with the same validation rules enforced
locally (Section 4.24).

## 9.6 Tenant Isolation

No feature, report, or AI Assistant response may ever surface data
belonging to a tenant other than the requester's, enforced at the
database layer via Row-Level Security, not solely at the application
layer (Section 3.4).

## 9.7 Audit Trail

Every create, update, and status-transition on a record with financial,
contractual, safety, or quality significance is logged with actor,
timestamp, and before/after values, retained per the data retention
policy (Section 5.7).

## 9.8 Currency Integrity

All monetary values are stored and calculated using fixed-point decimal
arithmetic; no module may introduce a floating-point currency
representation, regardless of the reporting or export format used
downstream.

## 9.9 Document Provenance

Any document generated by the AI Construction Assistant (report,
extracted BOQ, extracted invoice) is clearly labeled as
AI-generated/AI-assisted and requires human review before it is treated
as an official project record (Section 4.25).

## 9.10 Expiry-Driven Alerts, Not Silent Blocks

Compliance-related expiries (bonds, insurance, vendor compliance
documents, worker certifications) generate escalating alerts before they
become hard blocks, giving operational teams lead time to remediate
rather than being surprised by a sudden block on an in-progress workflow
--- except where a hard block is explicitly mandated (e.g., Permit to
Work issuance against expired safety training, per HSE-12), where safety
takes precedence over operational convenience.

# 10. Non-Functional Requirements

## 10.1 Performance

-   Web page interactive load time: p95 under 2 seconds on a 4G
    connection for standard list/detail views.
-   BOQ/Gantt grids: must remain interactive (scroll, edit) with up to
    10,000 line items via virtualized rendering.
-   Mobile sync batch: a batch of 500 records must process server-side
    within 10 seconds.
-   Dashboard aggregate queries (Executive Dashboard, Project Controls):
    p95 under 3 seconds, achieved via pre-aggregated materialized views
    refreshed on a scheduled or event-driven basis rather than computed
    live from raw transactions on every page load.

## 10.2 Scalability

-   The platform must support at least 500 concurrent tenants at general
    availability, scaling horizontally by adding application and
    database read-replica capacity without architectural change.
-   A single large tenant must be promotable to a dedicated database
    without application code changes (Section 2.7).

## 10.3 Availability

-   Target 99.9% uptime for the core web/API platform (excluding
    scheduled maintenance windows, communicated at least 48 hours in
    advance).
-   Mobile offline mode is, by design, independent of platform
    availability for core field-recording functions (Section 3.5).

## 10.4 Security

-   All data encrypted in transit (TLS 1.2+) and at rest (AES-256).
-   Passwords hashed with a modern adaptive algorithm (e.g., Argon2id);
    no plaintext or reversibly-encrypted password storage.
-   Role and permission changes are themselves audit-logged.
-   Regular third-party penetration testing (at minimum annually) and a
    documented responsible-disclosure process.
-   Compliance readiness for relevant regional data protection
    regulation (e.g., Nigeria's NDPR, Kenya's Data Protection Act, and
    GDPR where a tenant or its clients require it) including data
    subject access and deletion request handling.

## 10.5 Reliability & Data Integrity

-   Financial postings are atomic (a General Ledger entry either fully
    commits with balanced debits/credits or not at all).
-   Automated daily backups with point-in-time recovery, tested via
    regular restore drills.
-   Disaster recovery target: Recovery Point Objective (RPO) of 15
    minutes, Recovery Time Objective (RTO) of 4 hours.

## 10.6 Usability

-   Core field workflows (diary entry, material receipt, attendance)
    must be completable by a site-level user with basic smartphone
    literacy in under 3 minutes per entry.
-   Multi-language support planned from the architecture level (all
    user-facing strings externalized), with English as the initial
    language and French/Portuguese/Swahili as configurable additions
    given the target market's linguistic diversity.

## 10.7 Maintainability

-   Modular monolith structure (Section 3.3) with clear bounded-context
    boundaries to keep any single module's codebase comprehensible and
    independently testable.
-   Minimum 80% automated test coverage on financial, procurement, and
    permission-enforcement code paths specifically (not merely an
    aggregate coverage number across the whole codebase).

## 10.8 Interoperability

-   Standard import/export formats supported per module (Excel/CSV for
    BOQs and financial data, MPX/XML for schedules, LandXML for
    survey/design surfaces).
-   Documented, versioned REST API (Section 6) available to enterprise
    tenants for integration with existing systems during migration.

## 10.9 Compliance

-   Financial reporting must support statutory formats required in
    target jurisdictions (configurable chart of accounts and tax
    treatment, Section 4.17).
-   Explosives and blasting records (Module 16) must support the
    record-retention requirements typical of mining/quarrying regulation
    in target jurisdictions.

# 11. Development Roadmap

The roadmap is sequenced so that each phase delivers a usable, sellable
product slice, rather than requiring all 25 modules to be complete
before any tenant can go live.

## Phase 1 --- Foundation & Core Lifecycle (Months 1--4)

Multi-tenant platform scaffolding (auth, RBAC, RLS), Module 1 (Business
Development & CRM), Module 2 (Tender & Bid Management), Module 3
(Estimating & Cost Engineering), Module 4 (Contract Management). Goal: a
contractor can run their full pre-construction process, from lead to
signed contract, in SiteForge.

## Phase 2 --- Field Operations MVP (Months 4--8)

Module 5 (Project Planning), Module 6 (Project Execution), Module 24
(Mobile Field App, offline-first foundation), Module 13 (QMS --- core
ITP/NCR only), Module 14 (HSE --- core incident/permit only). Goal:
field teams can plan and run daily site operations, online and offline.

## Phase 3 --- Supply Chain & Resources (Months 8--12)

Module 7 (Procurement), Module 8 (Inventory & Warehouse), Module 9
(Equipment & Fleet), Module 10 (Fuel Management), Module 11 (Workforce
Management), Module 12 (Subcontractor Management). Goal: full
resource-side operational coverage.

## Phase 4 --- Financial Core & Billing (Months 12--16)

Module 17 (Financial Management --- full GL/AP/AR), Module 18 (Client
Billing), Module 19 (Project Controls/EVM). Goal: the ERP core is
complete and project financials are fully closed-loop from estimate to
certified billing.

## Phase 5 --- Differentiators & Portals (Months 16--20)

Module 15 (Survey & Engineering), Module 16 (Plant & Quarry Management),
Module 20 (Asset Management), Module 21 (Executive Dashboard), Module 22
(Client Portal), Module 23 (Vendor Portal). Goal: platform
differentiation for civil/heavy-construction contractors and
self-service for external stakeholders.

## Phase 6 --- AI Construction Assistant (Months 18--24, overlapping Phase 5)

Module 25, built incrementally: natural-language dashboard querying
first (lowest risk, highest visible value), then document extraction
(BOQ/invoice), then predictive features (equipment failure, material
shortage, spend anomaly detection) once sufficient historical data
exists in early tenants to make predictions meaningful.

## Roadmap Principles

-   No phase begins its final month without the previous phase's module
    set having at least one pilot tenant using it in a live
    (non-sandbox) capacity, to validate real-world assumptions before
    broader rollout.
-   The AI Assistant (Phase 6) is deliberately sequenced last among
    major capability areas, since its usefulness depends on the
    structured data produced by the other 24 modules already existing
    and being populated with real tenant history.
-   Mobile offline capability (Module 24) is treated as foundational
    infrastructure delivered in Phase 2 and extended incrementally as
    each subsequent module adds field-facing functionality, rather than
    being deferred as a "mobile version" of a web-first product.

# 12. Testing Requirements

## 12.1 Test Levels

  -------------------------------------------------------------------------
  Level                   Scope                     Tooling (indicative)
  ----------------------- ------------------------- -----------------------
  Unit                    Individual service        pytest
                          functions within a module 
                          (e.g., rate-analysis      
                          calculation, EVM formula) 

  Integration             Cross-module flows (e.g., pytest against a test
                          approved PO → GRN → GL    database with real
                          posting)                  Postgres/RLS enabled

  API/Contract            Every documented endpoint schemathesis / pytest +
                          against its OpenAPI       requests
                          schema                    

  End-to-End (Web)        Full user flows           Playwright
                          (tender-to-contract,      
                          procurement-to-payment)   

  Mobile                  Offline capture, sync,    Flutter integration
                          and conflict resolution   test suite, including
                                                    simulated network-loss
                                                    scenarios

  Security                Tenant-isolation,         Automated RLS-bypass
                          permission-boundary, and  attempts as a required
                          auth flows                CI gate, plus periodic
                                                    manual penetration
                                                    testing

  Performance/Load        Concurrent tenant load,   Locust/k6
                          large-BOQ rendering,      
                          dashboard aggregation     
  -------------------------------------------------------------------------

## 12.2 Mandatory Test Scenarios

-   **Tenant isolation:** an automated test suite must attempt, for
    every tenant-scoped table, to read/write another tenant's row using
    a valid token for a different tenant, and must assert failure in
    100% of cases. This suite runs on every CI build, not only
    periodically.
-   **Financial integrity:** every code path that posts to the General
    Ledger must be tested to guarantee debits equal credits and that no
    posting can occur without a linked source transaction (Section 9.1).
-   **Offline conflict resolution:** simulate two devices editing the
    same record offline, then syncing in different orders, and verify
    the conflict-handling behavior defined in Section 3.5 (no silent
    data loss, financially/safety-significant conflicts flagged for
    review).
-   **Approval-gate enforcement:** for every workflow with a mandatory
    approval gate (bid submission, PO issuance, progress certificate,
    permit to work), verify the action is blocked when any required step
    is incomplete.
-   **Budget-check enforcement:** verify Purchase Requests/Orders
    correctly block or warn per tenant configuration when exceeding
    remaining CBS budget (FIN-04, PRC-11).
-   **Baseline immutability:** verify that baselined schedules and
    approved CBS values cannot be altered by any user role without going
    through the explicit revision workflow.
-   **AI Assistant grounding:** verify that AI-generated responses
    referencing figures are always traceable to a source query result,
    and that no cross-tenant data can appear in a response regardless of
    prompt content (adversarial prompt testing included).

## 12.3 User Acceptance Testing (UAT)

Each phase in the roadmap (Section 11) concludes with a structured UAT
cycle involving at least one pilot tenant's real users across the
relevant roles (e.g., Phase 2 UAT involves actual Site Engineers using
the Mobile Field App on their own devices at an active site, including
in low-connectivity conditions). UAT sign-off is a phase-gate
requirement before the next phase's features are enabled for that
tenant.

## 12.4 Regression Testing

Given the cross-module traceability principle (Section 2.1), regression
suites must include cross-module scenarios (e.g., a change to
Estimating's rate-analysis calculation must be regression-tested against
Procurement's budget-check logic and Project Controls' EVM calculation,
since all three consume the same CBS data) rather than testing each
module purely in isolation.

## 12.5 Test Data & Environments

-   A synthetic multi-tenant test dataset representing at least three
    tenants of varying size (small single-project contractor, mid-size
    multi-project contractor, large multi-company group) is maintained
    for realistic performance and isolation testing.
-   Staging environments mirror production configuration (including RLS
    policies) exactly; no test environment may run with RLS disabled,
    since that would leave tenant-isolation bugs undetected until
    production.

# 13. Deployment Architecture

## 13.1 Environments

  -----------------------------------------------------------------------
  Environment                         Purpose
  ----------------------------------- -----------------------------------
  Development                         Local/ephemeral, per-developer or
                                      per-branch, seeded with synthetic
                                      data

  Staging                             Production-mirrored configuration,
                                      used for UAT (Section 12.3) and
                                      pre-release verification

  Production                          Live tenant environment,
                                      multi-region where a dedicated
                                      large-tenant deployment requires it
  -----------------------------------------------------------------------

## 13.2 Deployment Topology

    Internet
       │
       ▼
    [Load Balancer / CDN]  ── static assets (React build) served via CDN
       │
       ▼
    [Nginx reverse proxy]  ── TLS termination, rate limiting
       │
       ▼
    [Gunicorn workers running the Flask app]  ── horizontally scaled, stateless
       │            │
       ▼            ▼
    [PostgreSQL   [Redis]
     primary +     (cache, Celery broker)
     read replicas]     │
                         ▼
                  [Celery workers]  ── background jobs: report generation,
                                        AI Assistant calls, notification fan-out,
                                        scheduled reorder/expiry checks
       │
       ▼
    [S3-compatible object storage]  ── documents, photos, exports

## 13.3 CI/CD Pipeline

1.  Pull request triggers: lint, unit tests, integration tests
    (including the mandatory tenant-isolation suite, Section 12.2), and
    OpenAPI contract validation.
2.  Merge to main triggers: full test suite, container image build,
    staging deployment.
3.  Staging verification (automated smoke tests + manual QA sign-off for
    release-gated changes) precedes promotion to production.
4.  Production deployment uses a blue-green strategy: new version
    deployed alongside the old, traffic cut over after health checks
    pass, old version kept warm for immediate rollback.
5.  Database migrations (Alembic) run as a separate, reviewed step
    before application cutover, with a documented rollback migration for
    every forward migration.

## 13.4 Multi-Tenant Deployment Options

-   **Shared (default):** all tenants on shared application and database
    infrastructure, isolated via RLS (Section 3.4/5.5). Used for
    small-to-mid-size tenants.
-   **Dedicated database:** a large tenant's data is migrated to a
    dedicated PostgreSQL instance while remaining on shared application
    infrastructure; requires no application code change since the
    tenant-context middleware simply routes to a different connection
    string.
-   **Fully dedicated (private deployment):** for enterprise clients
    requiring data residency guarantees or regulatory isolation, the
    full stack (application, database, storage) is deployed to a
    dedicated environment, potentially in a client-specified cloud
    region.

## 13.5 Monitoring & Observability

-   **Metrics:** Prometheus scraping application and infrastructure
    metrics; Grafana dashboards per-tenant and platform-wide (request
    latency, error rate, queue depth, database connection pool
    utilization).
-   **Logging:** structured JSON logs, tagged with `tenant_id` and
    `request_id`, centralized for search and per-tenant filtering.
-   **Tracing:** OpenTelemetry distributed tracing across the API →
    Celery → database path, critical for diagnosing slow AI Assistant
    queries or sync-batch processing.
-   **Error tracking:** Sentry (or equivalent), with alerting thresholds
    tuned per environment (staging alerts to engineering Slack;
    production alerts page on-call).
-   **Alerting on business-significant events:** in addition to
    infrastructure alerts, the platform alerts on business-rule
    violations that should never occur (e.g., a GL posting with
    unbalanced debits/credits, Section 9.1) as a P1 incident, since
    these indicate a data-integrity defect rather than a routine
    operational issue.

## 13.6 Backup and Disaster Recovery

-   Automated daily full backups plus continuous WAL archiving for
    point-in-time recovery, per the RPO/RTO targets in Section 10.5.
-   Cross-region backup replication for production, with quarterly
    restore drills to verify backup integrity and recovery procedure
    accuracy.

# Appendix A --- Glossary

See Section 1.4 for core acronyms. Additional platform-specific terms:

  -----------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- -----------------------------------
  Bounded Context                     An internal module boundary within
                                      the modular monolith (Section 3.3)
                                      that owns its own tables and
                                      exposes a service interface to
                                      other modules

  Tenant Context Middleware           The request-handling layer that
                                      resolves the authenticated user's
                                      tenant and sets the database
                                      session's RLS variable

  Look-Ahead Plan                     A short-horizon (e.g., 2--6 week)
                                      schedule extract used for
                                      site-level planning, derived from
                                      but not overwriting the master
                                      schedule

  Baseline                            An immutable snapshot of schedule
                                      or budget data used as the
                                      reference point for variance
                                      calculation

  Conflict Record                     A platform record capturing two
                                      divergent offline edits to the same
                                      field, retained for review rather
                                      than silently resolved
  -----------------------------------------------------------------------

# Appendix B --- Open Items for Product Discovery

The following items are flagged for further discovery before or during
the relevant development phase, rather than being under-specified
silently within this SRS:

1.  Exact statutory payroll deduction rules per initial target
    jurisdiction (Module 11) --- to be confirmed with local compliance
    advisors per country of initial launch.
2.  Final selection of default construction-industry Chart of Accounts
    template (Module 17) --- to be validated against at least two pilot
    tenants' existing charts before finalizing the default.
3.  Specific biometric device vendor(s) to prioritize for first-class
    integration (Module 11) --- dependent on device prevalence in
    initial target markets.
4.  Government tender portal feed availability and terms of use per
    target country (Module 1) --- to be confirmed per-market before
    committing to automated ingestion versus manual entry only.
5.  Precise EVM forecast-at-completion method(s) to expose as
    tenant-configurable defaults (Module 19) --- CPI-based is specified
    as the baseline method; additional methods to be validated with
    pilot Project Controls users.

# Appendix C --- Traceability Note

Every module in Section 4 was derived directly from the platform module
list in the original product concept. Where this SRS introduces
additional detail (specific field names, business rules, or workflow
steps) beyond the original feature bullet points, that detail represents
the engineering elaboration necessary to make each feature buildable and
testable, and should be treated as the authoritative specification going
forward per Section 0's Purpose statement.
