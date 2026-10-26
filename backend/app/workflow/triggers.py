"""
The (module_name, entity_type) pairs that really start an approval
workflow, i.e. every place in the codebase that calls
`get_active_workflow`. The workflow builder offers exactly these.

This is a hand-kept registry on purpose (a runtime scan would be
fragile), so it is guarded by tests/test_workflow_triggers.py, which scans
the module services for `get_active_workflow(... module_name=..., entity_type=...)`
and fails when this list and the code disagree. Adding an approval
integration without adding it here breaks the build, not the builder.
"""

TRIGGERS = [
    {"module_name": "prc", "entity_type": "purchase_request", "label": "Procurement — Purchase Request"},
    {"module_name": "ctm", "entity_type": "contract_amendment", "label": "Contracts — Contract Amendment"},
    {"module_name": "est", "entity_type": "budget_revision", "label": "Estimating — Budget Revision"},
    {"module_name": "hse", "entity_type": "permit_to_work", "label": "HSE — Permit to Work"},
]
