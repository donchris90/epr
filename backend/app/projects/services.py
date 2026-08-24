"""
Cross-cutting Project listing (backend/app/models/core.py:Project).

A real, previously-missing gap found in a broader audit: Project is
referenced by nearly every module in this codebase (CBS, contracts,
tenders, diaries, permits, equipment transfers -- all of it), but no
route anywhere actually let a client list or search projects. Every
frontend screen and the mobile app were reduced to a raw "paste a
project UUID" text field because there was genuinely nothing to
select from.

Deliberately NOT a per-user "assigned projects" system -- that's a
real, separate, larger feature (a genuine project-membership/
assignment model, with its own permission model for who gets added to
which project) that doesn't exist anywhere in this codebase yet and
wasn't invented here as a shortcut. This lists every project in the
caller's tenant, respecting RLS the same as every other query in this
codebase -- the same real, honest scope that CLP/VNP's OWN external
portal user-to-project assignment already models correctly for external
users, just not yet built for internal staff.
"""
from app.extensions import db
from app.utils.errors import APIError
from app.models.core import Project


def list_projects(tenant_id, *, search=None, status=None):
    query = Project.query.filter_by(tenant_id=tenant_id)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))
    return query.order_by(Project.name).all()


def _validate_company(tenant_id, company_id):
    from app.models.core import Company

    if not Company.query.filter_by(id=company_id, tenant_id=tenant_id).first():
        raise APIError("Company not found", status=404)


def _validate_client(tenant_id, client_id):
    if not client_id:
        return
    from app.modules.bdc.models import Client

    if not Client.query.filter_by(id=client_id, tenant_id=tenant_id).first():
        raise APIError("Client not found", status=404)


def _validate_project_manager(tenant_id, project_manager_id):
    if not project_manager_id:
        return
    from app.models.core import User

    if not User.query.filter_by(id=project_manager_id, tenant_id=tenant_id).first():
        raise APIError("Project manager not found", status=404)


def create_project(tenant_id, *, company_id, name, client_id=None, project_manager_id=None, start_date=None, end_date=None):
    _validate_company(tenant_id, company_id)
    _validate_client(tenant_id, client_id)
    _validate_project_manager(tenant_id, project_manager_id)

    project = Project(
        tenant_id=tenant_id, company_id=company_id, name=name, status="active",
        client_id=client_id, project_manager_id=project_manager_id, start_date=start_date, end_date=end_date,
    )
    db.session.add(project)
    db.session.commit()
    return project


def get_project_detail(tenant_id, project_id):
    project = Project.query.filter_by(id=project_id, tenant_id=tenant_id).first()
    if not project:
        raise APIError("Project not found", status=404)

    client_name = None
    if project.client_id:
        from app.modules.bdc.models import Client

        client = Client.query.filter_by(id=project.client_id).first()
        client_name = client.name if client else None

    # Real, not fabricated -- a project's contract value only shows
    # up here if a real Contract row actually links to it
    # (ctm_contracts.project_id). Budget/actual cost/progress are
    # deliberately NOT included: those are real, computed rollups
    # owned by other modules (EST, PC/finance, EXE) that aren't
    # aggregated here yet -- a separate, larger piece of work, not
    # faked with placeholder numbers.
    contract_value = None
    currency = None
    from app.modules.ctm.models import Contract

    contract = Contract.query.filter_by(project_id=project_id).first()
    if contract:
        contract_value = contract.contract_value
        currency = contract.currency

    return {
        "project": project,
        "client_name": client_name,
        "contract_value": contract_value,
        "currency": currency,
    }


def update_project(tenant_id, project_id, *, name=None, client_id=None, project_manager_id=None, start_date=None, end_date=None, status=None):
    project = Project.query.filter_by(id=project_id, tenant_id=tenant_id).first()
    if not project:
        raise APIError("Project not found", status=404)

    if client_id is not None:
        _validate_client(tenant_id, client_id)
        project.client_id = client_id or None
    if project_manager_id is not None:
        _validate_project_manager(tenant_id, project_manager_id)
        project.project_manager_id = project_manager_id or None
    if name is not None:
        project.name = name
    if start_date is not None:
        project.start_date = start_date
    if end_date is not None:
        project.end_date = end_date
    if status is not None:
        project.status = status

    db.session.commit()
    return project
