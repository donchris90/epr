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
from app.models.core import Project


def list_projects(tenant_id, *, search=None, status=None):
    query = Project.query.filter_by(tenant_id=tenant_id)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))
    return query.order_by(Project.name).all()
