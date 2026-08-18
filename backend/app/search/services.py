"""
Real global search across permitted entity types -- Projects,
Clients, Vendors, Contracts. Base path: /v1/search

RBAC-aware per entity type, not just per-endpoint: a caller without
bdc:read genuinely never sees a client in results, even if they can
search at all (this endpoint itself only requires being a real,
authenticated tenant user -- the individual TYPE checks below are
what actually gate visibility, matching how a real person's role
determines what they can see everywhere else in this app). Real ILIKE
search against name/reference fields, tenant-scoped like every other
query in this codebase (RLS on top, in addition to the app-level
tenant_id filter -- the same three-layer model this whole codebase
already follows).
"""
from app.models.core import Project


MIN_QUERY_LENGTH = 2
MAX_RESULTS_PER_TYPE = 8


def search(tenant_id, *, query, permissions):
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        return []

    has_wildcard = "*" in permissions
    results = []

    if has_wildcard or "projects:read" in permissions:
        projects = (
            Project.query.filter(Project.tenant_id == tenant_id, Project.name.ilike(f"%{query}%"))
            .order_by(Project.name)
            .limit(MAX_RESULTS_PER_TYPE)
            .all()
        )
        for p in projects:
            results.append({
                "type": "project", "id": str(p.id), "label": p.name, "status": p.status,
                "url": f"/projects/{p.id}",
            })

    if has_wildcard or "bdc:read" in permissions:
        from app.modules.bdc.models import Client

        clients = (
            Client.query.filter(Client.tenant_id == tenant_id, Client.deleted_at.is_(None), Client.name.ilike(f"%{query}%"))
            .order_by(Client.name)
            .limit(MAX_RESULTS_PER_TYPE)
            .all()
        )
        for c in clients:
            results.append({
                "type": "client", "id": str(c.id), "label": c.name, "status": None,
                "url": "/business-development/clients",
            })

    if has_wildcard or "prc:read" in permissions:
        from app.modules.prc.models import Vendor

        vendors = (
            Vendor.query.filter(Vendor.tenant_id == tenant_id, Vendor.deleted_at.is_(None), Vendor.name.ilike(f"%{query}%"))
            .order_by(Vendor.name)
            .limit(MAX_RESULTS_PER_TYPE)
            .all()
        )
        for v in vendors:
            results.append({
                "type": "vendor", "id": str(v.id), "label": v.name, "status": v.status,
                "url": "/procurement/vendors",
            })

    if has_wildcard or "ctm:read" in permissions:
        from app.modules.ctm.models import Contract

        contracts = (
            Contract.query.filter(
                Contract.tenant_id == tenant_id, Contract.deleted_at.is_(None), Contract.contract_number.ilike(f"%{query}%")
            )
            .order_by(Contract.contract_number)
            .limit(MAX_RESULTS_PER_TYPE)
            .all()
        )
        for c in contracts:
            results.append({
                "type": "contract", "id": str(c.id), "label": c.contract_number, "status": c.status,
                "url": f"/contracts/{c.id}",
            })

    return results
