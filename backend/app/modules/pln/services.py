"""
Module 5 — Project Planning (Code: PLN)
Service layer — business logic other modules must call through rather
than querying pln_* tables directly (SRS Section 3.3).

The core of this module is services.recalculate_schedule: a real
Critical Path Method (CPM) implementation supporting all four SRS-4.4
dependency types (FS/SS/FF/SF) with lag/lead, via forward and backward
passes over the activity network.

Modeling simplification (documented, not hidden): dates are treated as
continuous calendar days -- there is no working-calendar (weekends,
holidays) concept yet. A zero-lag Finish-to-Start dependency means the
successor's early start equals the predecessor's early finish exactly
(not "the next working day after"). Adding a calendar is a natural
follow-up once Module 11 (Workforce Management) defines site working
patterns; bolting one on here first would mean guessing at data this
module doesn't own.

Business rules encoded here (SRS 4.5):
  - Changing an activity's dates after baselining does not alter the
    baseline; variance is always current-minus-baseline, never computed
    by overwriting history. (Baseline snapshots are write-once — see
    models.py — so this is enforced by construction, not by a check
    here.)
  - A Delay Event affecting the critical path automatically flags the
    project's forecast completion date for review.
"""
from collections import defaultdict, deque
from datetime import timedelta

from app.extensions import db
from app.utils.errors import APIError
from app.modules.pln.models import (
    WBSNode,
    Activity,
    ActivityDependency,
    Baseline,
    BaselineActivitySnapshot,
    ResourceAssignment,
    DelayEvent,
)


# --- Critical Path Method scheduling (PLN-02, PLN-03, PLN-04) --------------

def _topological_order(activities: list, dependencies: list) -> list:
    """Kahn's algorithm. Raises APIError on a cycle -- a cyclic network
    has no valid schedule, and CPM cannot proceed."""
    activity_ids = {a.id for a in activities}
    successors = defaultdict(list)
    in_degree = {aid: 0 for aid in activity_ids}

    for dep in dependencies:
        if dep.predecessor_id not in activity_ids or dep.successor_id not in activity_ids:
            continue
        successors[dep.predecessor_id].append(dep)
        in_degree[dep.successor_id] += 1

    queue = deque([aid for aid in activity_ids if in_degree[aid] == 0])
    order = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for dep in successors[current]:
            in_degree[dep.successor_id] -= 1
            if in_degree[dep.successor_id] == 0:
                queue.append(dep.successor_id)

    if len(order) != len(activity_ids):
        raise APIError(
            "Schedule network contains a cycle",
            status=409,
            detail="Activity dependencies form a cycle; no valid critical path exists.",
        )
    return order


def recalculate_schedule(wbs_root: WBSNode):
    """
    PLN-03: recomputes early/late start/finish, total float, and
    is_critical for every activity under this WBS root, via a full CPM
    forward + backward pass. Call this after any activity or dependency
    change under the root -- it is idempotent and safe to call
    liberally (e.g. after every mutating request in this module).
    """
    wbs_node_ids = _collect_wbs_subtree_ids(wbs_root)
    activities = Activity.query.filter(Activity.wbs_node_id.in_(wbs_node_ids)).all()
    if not activities:
        return []

    activity_by_id = {a.id: a for a in activities}
    activity_ids = list(activity_by_id.keys())
    dependencies = ActivityDependency.query.filter(
        ActivityDependency.predecessor_id.in_(activity_ids), ActivityDependency.successor_id.in_(activity_ids)
    ).all()

    predecessors_of = defaultdict(list)  # successor_id -> [(dep, predecessor_activity)]
    successors_of = defaultdict(list)  # predecessor_id -> [(dep, successor_activity)]
    for dep in dependencies:
        predecessors_of[dep.successor_id].append(dep)
        successors_of[dep.predecessor_id].append(dep)

    order = _topological_order(activities, dependencies)

    # --- Forward pass: early_start / early_finish ---
    for aid in order:
        activity = activity_by_id[aid]
        preds = predecessors_of[aid]
        if not preds:
            es = activity.planned_start
        else:
            candidates = []
            for dep in preds:
                pred = activity_by_id[dep.predecessor_id]
                lag = timedelta(days=dep.lag_days)
                if dep.dependency_type == "FS":
                    candidates.append(pred.early_finish + lag)
                elif dep.dependency_type == "SS":
                    candidates.append(pred.early_start + lag)
                elif dep.dependency_type == "FF":
                    candidates.append(pred.early_finish + lag - timedelta(days=activity.duration_days))
                elif dep.dependency_type == "SF":
                    candidates.append(pred.early_start + lag - timedelta(days=activity.duration_days))
            es = max(candidates)

        activity.early_start = es
        activity.early_finish = es + timedelta(days=activity.duration_days)

    project_finish = max(a.early_finish for a in activities)

    # --- Backward pass: late_start / late_finish ---
    for aid in reversed(order):
        activity = activity_by_id[aid]
        succs = successors_of[aid]
        if not succs:
            lf = project_finish
        else:
            candidates = []
            for dep in succs:
                succ = activity_by_id[dep.successor_id]
                lag = timedelta(days=dep.lag_days)
                if dep.dependency_type == "FS":
                    candidates.append(succ.late_start - lag)
                elif dep.dependency_type == "SS":
                    candidates.append(succ.late_start - lag + timedelta(days=activity.duration_days))
                elif dep.dependency_type == "FF":
                    candidates.append(succ.late_finish - lag)
                elif dep.dependency_type == "SF":
                    candidates.append(succ.late_finish - lag + timedelta(days=activity.duration_days))
            lf = min(candidates)

        activity.late_finish = lf
        activity.late_start = lf - timedelta(days=activity.duration_days)
        activity.total_float_days = (activity.late_start - activity.early_start).days
        activity.is_critical = activity.total_float_days <= 0

    db.session.commit()
    return activities


def _collect_wbs_subtree_ids(root: WBSNode) -> list:
    """All WBSNode ids under (and including) root, via one query per
    level -- WBS trees are shallow (a handful of levels), so this is
    simpler and plenty fast enough without a recursive CTE."""
    ids = [root.id]
    frontier = [root.id]
    while frontier:
        children = WBSNode.query.filter(WBSNode.parent_id.in_(frontier)).all()
        if not children:
            break
        frontier = [c.id for c in children]
        ids.extend(frontier)
    return ids


# --- Baselining (PLN-06, PLN-11, business rule) -----------------------------

def create_baseline(project_id, wbs_root: WBSNode, *, label: str, mark_current: bool = False):
    """
    PLN-06: snapshots every activity's current planned dates into
    write-once BaselineActivitySnapshot rows. Multiple baselines may
    coexist per project (PLN-11); `mark_current` designates the one
    used for contractual EOT claims.
    """
    wbs_node_ids = _collect_wbs_subtree_ids(wbs_root)
    activities = Activity.query.filter(Activity.wbs_node_id.in_(wbs_node_ids)).all()
    if not activities:
        raise APIError("Cannot baseline an empty schedule", status=400)

    baseline = Baseline(tenant_id=wbs_root.tenant_id, project_id=project_id, label=label, is_current=False)
    db.session.add(baseline)
    db.session.flush()

    for activity in activities:
        db.session.add(
            BaselineActivitySnapshot(
                tenant_id=wbs_root.tenant_id,
                baseline_id=baseline.id,
                activity_id=activity.id,
                planned_start=activity.early_start or activity.planned_start,
                planned_finish=activity.early_finish
                or (activity.planned_start + timedelta(days=activity.duration_days)),
                duration_days=activity.duration_days,
            )
        )

    if mark_current:
        mark_baseline_current(baseline)
    else:
        db.session.commit()

    return baseline


def mark_baseline_current(baseline: Baseline):
    """Only one baseline may be current (authoritative for EOT claims)
    at a time -- same single-designated-version pattern used by EST's
    submitted EstimateVersion."""
    others = Baseline.query.filter_by(
        tenant_id=baseline.tenant_id, project_id=baseline.project_id, is_current=True
    ).all()
    for other in others:
        if other.id != baseline.id:
            other.is_current = False

    baseline.is_current = True
    db.session.commit()
    return baseline


def schedule_variance(activity: Activity, baseline: Baseline) -> dict:
    """PLN-10: current (early_finish) minus baseline, surfaced for
    Module 19 (Project Controls). Never computed by mutating the
    baseline snapshot -- that row is immutable by construction."""
    snapshot = BaselineActivitySnapshot.query.filter_by(baseline_id=baseline.id, activity_id=activity.id).first()
    if not snapshot:
        raise APIError("Activity was not part of this baseline", status=404)

    current_finish = activity.early_finish or (activity.planned_start + timedelta(days=activity.duration_days))
    variance_days = (current_finish - snapshot.planned_finish).days

    return {
        "activity_id": str(activity.id),
        "baseline_finish": snapshot.planned_finish.isoformat(),
        "current_finish": current_finish.isoformat(),
        "variance_days": variance_days,  # positive = running late vs. this baseline
    }


# --- Resource over-allocation (PLN-05) --------------------------------------

def find_overlapping_assignments(resource_name: str, tenant_id) -> list:
    """
    Flags over-allocation: any two assignments of the SAME named
    resource whose activities' date ranges overlap. This is a
    read-time derived check, not a stored fact (an assignment isn't
    "wrong" on its own -- it's only over-allocated relative to others
    that exist at query time).

    Uses each activity's CPM-computed early_start/early_finish when
    available, falling back to planned_start/duration_days for
    activities that haven't been scheduled yet (recalculate_schedule
    not yet run, or a root activity with no predecessors, where
    planned_start IS the driving date). Using raw planned_start
    unconditionally would be wrong for any non-root activity, since
    recalculate_schedule is what actually determines when a dependent
    activity runs -- see the module docstring in services.py.
    """
    assignments = (
        ResourceAssignment.query.join(Activity, ResourceAssignment.activity_id == Activity.id)
        .filter(ResourceAssignment.tenant_id == tenant_id, ResourceAssignment.resource_name == resource_name)
        .all()
    )

    def _window(activity):
        if activity.early_start and activity.early_finish:
            return activity.early_start, activity.early_finish
        return activity.planned_start, activity.planned_start + timedelta(days=activity.duration_days)

    overlaps = []
    for i, a in enumerate(assignments):
        a_start, a_end = _window(a.activity)
        for b in assignments[i + 1 :]:
            b_start, b_end = _window(b.activity)
            if a_start < b_end and b_start < a_end:
                overlaps.append((a, b))

    return overlaps


# --- Delay events (PLN-08, business rule) -----------------------------------

def record_delay_event(tenant_id, *, project_id, activity_id, cause_classification, description, delay_days, occurred_on, analysis_method=None):
    affected_critical_path = False
    if activity_id:
        activity = Activity.query.filter_by(id=activity_id, tenant_id=tenant_id).first()
        if activity:
            affected_critical_path = bool(activity.is_critical)

    event = DelayEvent(
        tenant_id=tenant_id,
        project_id=project_id,
        activity_id=activity_id,
        cause_classification=cause_classification,
        description=description,
        delay_days=delay_days,
        occurred_on=occurred_on,
        analysis_method=analysis_method,
        affected_critical_path=affected_critical_path,
        # Business rule: a delay on the critical path automatically
        # flags the forecast completion date for review.
        flagged_for_review=affected_critical_path,
    )
    db.session.add(event)
    db.session.commit()
    return event
