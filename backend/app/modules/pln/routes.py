"""
Module 5 — Project Planning (Code: PLN)
SRS Section 4.5 — Flask Blueprint. Base path: /v1/pln
"""
from flask import Blueprint, g, jsonify, request
from marshmallow import ValidationError

from app.extensions import db
from app.utils.decorators import require_permission
from app.utils.errors import APIError
from app.utils.pagination import envelope

from app.modules.pln import services
from app.modules.pln.models import (
    WBSNode,
    Activity,
    ActivityDependency,
    ResourceAssignment,
    Baseline,
    LookAheadPlan,
    LookAheadItem,
    DelayEvent,
)
from app.modules.pln.schemas import (
    WBSNodeSchema,
    ActivitySchema,
    ActivityDependencySchema,
    ResourceAssignmentSchema,
    BaselineSchema,
    CreateBaselineSchema,
    LookAheadPlanSchema,
    LookAheadItemSchema,
    DelayEventSchema,
)

bp = Blueprint("pln", __name__, url_prefix="/v1/pln")

wbs_node_schema = WBSNodeSchema()
activity_schema = ActivitySchema()
dependency_schema = ActivityDependencySchema()
resource_assignment_schema = ResourceAssignmentSchema()
baseline_schema = BaselineSchema()
look_ahead_plan_schema = LookAheadPlanSchema()
look_ahead_item_schema = LookAheadItemSchema()
delay_event_schema = DelayEventSchema()


def _load(schema):
    try:
        return schema.load(request.get_json(force=True) or {})
    except ValidationError as err:
        raise APIError("Validation failed", status=422, detail=str(err.messages))


def _get_wbs_node_or_404(node_id) -> WBSNode:
    node = WBSNode.query.filter_by(id=node_id, tenant_id=g.tenant_id).first()
    if not node:
        raise APIError("WBS node not found", status=404)
    return node


def _get_activity_or_404(activity_id) -> Activity:
    activity = Activity.query.filter_by(id=activity_id, tenant_id=g.tenant_id).first()
    if not activity:
        raise APIError("Activity not found", status=404)
    return activity


@bp.get("/health")
def health():
    return jsonify({"module": "pln", "name": "Project Planning", "status": "ok"})


# --- WBS (PLN-01) -----------------------------------------------------------

@bp.post("/wbs-nodes")
@require_permission("pln:write")
def create_wbs_node():
    data = _load(wbs_node_schema)
    node = WBSNode(tenant_id=g.tenant_id, **data)
    db.session.add(node)
    db.session.commit()
    return jsonify(wbs_node_schema.dump(node)), 201


@bp.get("/wbs-nodes")
@require_permission("pln:read")
def list_wbs_nodes():
    query = WBSNode.query.filter_by(tenant_id=g.tenant_id)
    project_id = request.args.get("project_id")
    if project_id:
        query = query.filter_by(project_id=project_id)
    nodes = query.order_by(WBSNode.sort_order).all()
    return jsonify(envelope(wbs_node_schema.dump(nodes, many=True)))


# --- Activities & dependencies (PLN-02, PLN-03, PLN-04) ---------------------

@bp.post("/wbs-nodes/<uuid:node_id>/activities")
@require_permission("pln:write")
def add_activity(node_id):
    node = _get_wbs_node_or_404(node_id)
    data = _load(activity_schema)
    activity = Activity(tenant_id=g.tenant_id, wbs_node_id=node.id, **data)
    db.session.add(activity)
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 201


@bp.get("/wbs-nodes/<uuid:node_id>/activities")
@require_permission("pln:read")
def list_activities(node_id):
    _get_wbs_node_or_404(node_id)
    activities = Activity.query.filter_by(wbs_node_id=node_id, tenant_id=g.tenant_id).all()
    return jsonify(envelope(activity_schema.dump(activities, many=True)))


@bp.get("/activities")
@require_permission("pln:read")
def list_project_activities():
    """A project-wide activity list, joined through the WBS tree --
    the schedule/Gantt view needs every activity under a project's WBS
    root in one call, not one node at a time."""
    project_id = request.args.get("project_id")
    if not project_id:
        raise APIError("project_id query parameter is required", status=400)

    node_ids = [n.id for n in WBSNode.query.filter_by(tenant_id=g.tenant_id, project_id=project_id).all()]
    activities = (
        Activity.query.filter(Activity.tenant_id == g.tenant_id, Activity.wbs_node_id.in_(node_ids))
        .order_by(Activity.planned_start)
        .all()
    )
    return jsonify(envelope(activity_schema.dump(activities, many=True)))


@bp.post("/activity-dependencies")
@require_permission("pln:write")
def add_dependency():
    data = _load(dependency_schema)

    pred = _get_activity_or_404(data["predecessor_id"])
    _get_activity_or_404(data["successor_id"])

    dep = ActivityDependency(tenant_id=g.tenant_id, **data)
    db.session.add(dep)
    db.session.commit()
    return jsonify(dependency_schema.dump(dep)), 201


@bp.post("/wbs-nodes/<uuid:node_id>/recalculate-schedule")
@require_permission("pln:write")
def recalculate_schedule(node_id):
    """PLN-03: triggers the CPM forward/backward pass for every
    activity under this WBS root."""
    node = _get_wbs_node_or_404(node_id)
    activities = services.recalculate_schedule(node)
    return jsonify(envelope(activity_schema.dump(activities, many=True)))


# --- Resource loading (PLN-05) -----------------------------------------------

@bp.post("/activities/<uuid:activity_id>/resource-assignments")
@require_permission("pln:write")
def add_resource_assignment(activity_id):
    activity = _get_activity_or_404(activity_id)
    data = _load(resource_assignment_schema)
    assignment = ResourceAssignment(tenant_id=g.tenant_id, activity_id=activity.id, **data)
    db.session.add(assignment)
    db.session.commit()
    return jsonify(resource_assignment_schema.dump(assignment)), 201


@bp.get("/resource-assignments/over-allocation")
@require_permission("pln:read")
def check_over_allocation():
    resource_name = request.args.get("resource_name")
    if not resource_name:
        raise APIError("resource_name query parameter is required", status=400)

    overlaps = services.find_overlapping_assignments(resource_name, g.tenant_id)
    return jsonify(
        {
            "resource_name": resource_name,
            "over_allocated": len(overlaps) > 0,
            "conflicts": [
                {
                    "activity_a": str(a.activity_id),
                    "activity_b": str(b.activity_id),
                }
                for a, b in overlaps
            ],
        }
    )


# --- Baselines (PLN-06, PLN-11) ----------------------------------------------

@bp.post("/baselines")
@require_permission("pln:approve")
def create_baseline():
    data = _load(CreateBaselineSchema())
    wbs_root = _get_wbs_node_or_404(data["wbs_root_id"])
    baseline = services.create_baseline(
        data.get("project_id"), wbs_root, label=data["label"], mark_current=data["mark_current"]
    )
    return jsonify(baseline_schema.dump(baseline)), 201


@bp.post("/baselines/<uuid:baseline_id>/mark-current")
@require_permission("pln:approve")
def mark_baseline_current(baseline_id):
    baseline = Baseline.query.filter_by(id=baseline_id, tenant_id=g.tenant_id).first()
    if not baseline:
        raise APIError("Baseline not found", status=404)
    baseline = services.mark_baseline_current(baseline)
    return jsonify(baseline_schema.dump(baseline))


@bp.get("/baselines/<uuid:baseline_id>/variance/<uuid:activity_id>")
@require_permission("pln:read")
def get_variance(baseline_id, activity_id):
    baseline = Baseline.query.filter_by(id=baseline_id, tenant_id=g.tenant_id).first()
    if not baseline:
        raise APIError("Baseline not found", status=404)
    activity = _get_activity_or_404(activity_id)

    return jsonify(services.schedule_variance(activity, baseline))


# --- Look-ahead plans (PLN-07) -----------------------------------------------

@bp.post("/look-ahead-plans")
@require_permission("pln:write")
def create_look_ahead_plan():
    data = _load(look_ahead_plan_schema)
    plan = LookAheadPlan(tenant_id=g.tenant_id, **data)
    db.session.add(plan)
    db.session.commit()
    return jsonify(look_ahead_plan_schema.dump(plan)), 201


@bp.post("/look-ahead-plans/<uuid:plan_id>/items")
@require_permission("pln:write")
def add_look_ahead_item(plan_id):
    plan = LookAheadPlan.query.filter_by(id=plan_id, tenant_id=g.tenant_id).first()
    if not plan:
        raise APIError("Look-ahead plan not found", status=404)

    data = _load(look_ahead_item_schema)
    _get_activity_or_404(data["activity_id"])

    item = LookAheadItem(tenant_id=g.tenant_id, plan_id=plan.id, **data)
    db.session.add(item)
    db.session.commit()
    return jsonify(look_ahead_item_schema.dump(item)), 201


# --- Delay events (PLN-08) ----------------------------------------------------

@bp.post("/delay-events")
@require_permission("pln:write")
def create_delay_event():
    data = _load(delay_event_schema)
    event = services.record_delay_event(g.tenant_id, **data)
    return jsonify(delay_event_schema.dump(event)), 201


@bp.get("/delay-events")
@require_permission("pln:read")
def list_delay_events():
    query = DelayEvent.query.filter_by(tenant_id=g.tenant_id)
    project_id = request.args.get("project_id")
    if project_id:
        query = query.filter_by(project_id=project_id)
    events = query.all()
    return jsonify(envelope(delay_event_schema.dump(events, many=True)))
