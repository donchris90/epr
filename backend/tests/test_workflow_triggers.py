"""Keeps the builder's trigger list honest."""
import re
from pathlib import Path

from app.workflow.triggers import TRIGGERS

CALL = re.compile(r"get_active_workflow\(\s*[^)]*?module_name=\"(\w+)\",\s*entity_type=\"(\w+)\"", re.S)


def _found_in_code():
    root = Path(__file__).resolve().parents[1] / "app" / "modules"
    found = set()
    for path in root.rglob("services.py"):
        found.update(CALL.findall(path.read_text()))
    return found


def test_registry_matches_every_get_active_workflow_call_site():
    registered = {(t["module_name"], t["entity_type"]) for t in TRIGGERS}
    found = _found_in_code()
    assert found, "scan found no call sites; the pattern is out of date"
    assert registered == found, (
        f"Update app/workflow/triggers.py. In code but not registered: {found - registered}. "
        f"Registered but not in code: {registered - found}."
    )


def test_endpoint_returns_registry_for_admins_only(client, seed_tenants, auth_headers):
    r = client.get("/v1/workflow/valid-triggers", headers=auth_headers("a", permissions=["workflow:admin"]))
    assert r.status_code == 200
    assert r.get_json()["data"] == TRIGGERS
    r = client.get("/v1/workflow/valid-triggers", headers=auth_headers("a", permissions=["workflow:approve"]))
    assert r.status_code == 403
