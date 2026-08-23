"""
Workflow engine service layer -- see app/workflow/models.py for the
full design scope and honest limitations.
"""
from app.extensions import db
from app.utils.errors import APIError
from app.workflow.models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowAction
from app.notifications import services as notification_services


# --- Notification helper ---------------------------------------------------

def _notify_approvers_for_step(instance, workflow, step_number, *, event_title, event_body):
    """Resolves every real user who can act on a given step -- a
    single named user for `specific_user`, or every user in the
    tenant holding the required Role for `specific_role` -- and
    notifies each. This is the one real, concrete use of the
    Notifications module (app/notifications/) added specifically
    because the Workflow Engine's own docs flagged "no notifications
    of any kind" as a real gap; this closes it for the one place a
    notification is most obviously needed, not everywhere at once."""
    from app.models.core import User

    steps = _applicable_steps_at_number(workflow, step_number, instance.amount)
    user_ids = set()
    for step in steps:
        if step.approver_type == "specific_user" and step.specific_user_id:
            user_ids.add(step.specific_user_id)
        elif step.approver_type == "specific_role" and step.required_role_id:
            role_users = User.query.filter_by(tenant_id=instance.tenant_id, role_id=step.required_role_id).all()
            user_ids.update(u.id for u in role_users)

    if user_ids:
        notification_services.notify_many(
            instance.tenant_id,
            user_ids=user_ids,
            type="workflow.approval_requested",
            title=event_title,
            body=event_body,
            channel="email",
            data={
                "workflow_instance_id": str(instance.id),
                "module_name": instance.module_name,
                "entity_type": instance.entity_type,
                "entity_id": str(instance.entity_id),
                "step_number": step_number,
            },
        )


def _notify_user(instance, user_id, *, type, title, body):
    if not user_id:
        return
    notification_services.notify(
        instance.tenant_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        channel="email",
        data={
            "workflow_instance_id": str(instance.id),
            "module_name": instance.module_name,
            "entity_type": instance.entity_type,
            "entity_id": str(instance.entity_id),
        },
    )


# --- Definitions ----------------------------------------------------------

def create_workflow_definition(tenant_id, *, module_name, entity_type, workflow_name, description, steps, created_by):
    """Creates a new, inactive definition -- call activate_workflow_definition
    separately once it's ready to actually route real submissions.
    Inactive by default so a definition can be built and reviewed
    without immediately affecting live entities."""
    existing_count = WorkflowDefinition.query.filter_by(
        tenant_id=tenant_id, module_name=module_name, entity_type=entity_type
    ).count()

    definition = WorkflowDefinition(
        tenant_id=tenant_id,
        module_name=module_name,
        entity_type=entity_type,
        workflow_name=workflow_name,
        description=description,
        active=False,
        version=existing_count + 1,
        created_by=created_by,
    )
    db.session.add(definition)
    db.session.flush()

    for step_data in steps:
        db.session.add(WorkflowStep(tenant_id=tenant_id, workflow_id=definition.id, **step_data))

    db.session.commit()
    return definition


def activate_workflow_definition(definition, *, actor_id=None):
    """
    Deactivates any other active definition for the same
    (module_name, entity_type) first -- only one version should be
    live at a time. Instances already in flight under a
    now-deactivated definition are unaffected; they keep referencing
    the same workflow_id and finish under the rules they started
    with.

    actor_id is passed through to updated_by explicitly -- AuditMixin's
    updated_by (backend/app/models/base.py) is nullable and never
    auto-populated by anything, so without this, "who published"
    would stay null forever regardless of who actually activated it.
    """
    WorkflowDefinition.query.filter_by(
        tenant_id=definition.tenant_id,
        module_name=definition.module_name,
        entity_type=definition.entity_type,
        active=True,
    ).update({"active": False})

    definition.active = True
    if actor_id:
        definition.updated_by = actor_id
    db.session.commit()
    return definition


def deactivate_workflow_definition(definition, *, actor_id=None):
    definition.active = False
    if actor_id:
        definition.updated_by = actor_id
    db.session.commit()
    return definition


def get_active_workflow(tenant_id, *, module_name, entity_type):
    return WorkflowDefinition.query.filter_by(
        tenant_id=tenant_id, module_name=module_name, entity_type=entity_type, active=True
    ).first()


# --- Step applicability (amount-based skipping) ----------------------------

def _step_applies(step, amount):
    """A step with no configured amount range always applies. A step
    with a range only applies if the instance's amount is inside it --
    missing amount on an instance with a ranged step means the step
    does NOT apply (there's nothing to threshold-check against)."""
    if step.minimum_amount is None and step.maximum_amount is None:
        return True
    if amount is None:
        return False
    if step.minimum_amount is not None and amount < step.minimum_amount:
        return False
    if step.maximum_amount is not None and amount > step.maximum_amount:
        return False
    return True


def _applicable_steps_at_number(workflow, step_number, amount):
    return [s for s in workflow.steps if s.step_number == step_number and _step_applies(s, amount)]


def _next_applicable_step_number(workflow, after_step_number, amount):
    """The next step_number strictly after `after_step_number` that has
    at least one applicable step, or None if the chain is complete."""
    candidate_numbers = sorted({s.step_number for s in workflow.steps if s.step_number > after_step_number})
    for number in candidate_numbers:
        if _applicable_steps_at_number(workflow, number, amount):
            return number
    return None


def _first_applicable_step_number(workflow, amount):
    return _next_applicable_step_number(workflow, after_step_number=0, amount=amount)


# --- Instances --------------------------------------------------------------

def start_workflow_instance(tenant_id, workflow, *, module_name, entity_type, entity_id, initiated_by, amount=None):
    first_number = _first_applicable_step_number(workflow, amount)
    if first_number is None:
        raise APIError("Workflow has no applicable steps for this amount", status=400)

    instance = WorkflowInstance(
        tenant_id=tenant_id,
        workflow_id=workflow.id,
        module_name=module_name,
        entity_type=entity_type,
        entity_id=entity_id,
        status="pending",
        current_step_number=first_number,
        amount=amount,
        initiated_by=initiated_by,
    )
    db.session.add(instance)
    db.session.flush()

    _notify_approvers_for_step(
        instance, workflow, first_number,
        event_title=f"Approval requested: {workflow.workflow_name}",
        event_body=f"A new {entity_type.replace('_', ' ')} needs your approval.",
    )

    db.session.commit()
    return instance


def get_pending_approvals_for_user(tenant_id, *, user_id, role_id):
    """Every pending instance whose *current* step group includes a
    step this user can act on -- either named directly
    (specific_user_id) or via role (required_role_id), or delegated to
    them for this specific step."""
    pending = WorkflowInstance.query.filter_by(tenant_id=tenant_id, status="pending").all()
    result = []
    for instance in pending:
        step = _find_actionable_step_for_user(instance, user_id=user_id, role_id=role_id)
        if step is not None:
            result.append(instance)
    return result


def _find_actionable_step_for_user(instance, *, user_id, role_id):
    workflow = instance.workflow_id and db.session.get(WorkflowDefinition, instance.workflow_id)
    if not workflow:
        return None
    candidates = _applicable_steps_at_number(workflow, instance.current_step_number, instance.amount)

    delegated_user_ids = {
        str(a.delegated_to)
        for a in WorkflowAction.query.filter_by(
            instance_id=instance.id, step_number=instance.current_step_number, action_type="delegate"
        ).all()
    }

    for step in candidates:
        if str(user_id) in delegated_user_ids:
            return step
        if step.approver_type == "specific_user" and str(step.specific_user_id) == str(user_id):
            return step
        if step.approver_type == "specific_role" and str(step.required_role_id) == str(role_id):
            return step
    return None


def _step_already_actioned_by(instance, step, action_type="approve"):
    # Deliberately a direct query, not instance.actions -- that's a
    # cached ORM relationship collection, and once it's been accessed
    # once in this session (e.g. by _find_actionable_step_for_user's
    # delegation check, which runs before this), later accesses don't
    # reflect a newly-flushed row even after db.session.flush(). A
    # direct query always hits the database fresh.
    return (
        WorkflowAction.query.filter_by(
            instance_id=instance.id, step_number=step.step_number, action_type=action_type
        ).first()
        is not None
    )


def approve_step(instance, *, actor_id, role_id, comment=None, ip_address=None, user_agent=None):
    if instance.status != "pending":
        raise APIError(f"Cannot approve an instance that is already {instance.status}", status=400)

    workflow = db.session.get(WorkflowDefinition, instance.workflow_id)
    step = _find_actionable_step_for_user(instance, user_id=actor_id, role_id=role_id)
    if step is None:
        raise APIError("You are not an approver for the current step of this workflow", status=403)

    db.session.add(WorkflowAction(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        step_number=instance.current_step_number,
        action_type="approve",
        actor_id=actor_id,
        old_status=instance.status,
        new_status=instance.status,  # not yet known if this advances the instance itself
        comment=comment,
        ip_address=ip_address,
        user_agent=user_agent,
    ))

    required = _applicable_steps_at_number(workflow, instance.current_step_number, instance.amount)
    # instance.actions doesn't include the just-added action until a
    # flush makes it visible through the relationship.
    db.session.flush()
    all_satisfied = all(_step_already_actioned_by(instance, s) for s in required)

    if all_satisfied:
        next_number = _next_applicable_step_number(workflow, instance.current_step_number, instance.amount)
        if next_number is None:
            instance.status = "approved"
            _notify_user(
                instance, instance.initiated_by,
                type="workflow.instance_approved",
                title=f"Approved: {workflow.workflow_name}",
                body=f"Your {instance.entity_type.replace('_', ' ')} has been fully approved.",
            )
        else:
            instance.current_step_number = next_number
            _notify_approvers_for_step(
                instance, workflow, next_number,
                event_title=f"Approval requested: {workflow.workflow_name}",
                event_body=f"A {instance.entity_type.replace('_', ' ')} has advanced to the next approval step and needs your review.",
            )

    db.session.commit()
    return instance


def reject_step(instance, *, actor_id, role_id, comment=None, ip_address=None, user_agent=None):
    if instance.status != "pending":
        raise APIError(f"Cannot reject an instance that is already {instance.status}", status=400)

    workflow = db.session.get(WorkflowDefinition, instance.workflow_id)
    step = _find_actionable_step_for_user(instance, user_id=actor_id, role_id=role_id)
    if step is None:
        raise APIError("You are not an approver for the current step of this workflow", status=403)

    old_status = instance.status
    if step.reject_to_step is not None:
        instance.current_step_number = step.reject_to_step
        new_status = "pending"
        _notify_approvers_for_step(
            instance, workflow, step.reject_to_step,
            event_title=f"Returned for rework: {workflow.workflow_name}",
            event_body=f"A {instance.entity_type.replace('_', ' ')} was rejected and returned to your step for rework."
            + (f' Reason: "{comment}"' if comment else ""),
        )
    else:
        instance.status = "rejected"
        new_status = "rejected"
        _notify_user(
            instance, instance.initiated_by,
            type="workflow.instance_rejected",
            title=f"Rejected: {workflow.workflow_name}",
            body=f"Your {instance.entity_type.replace('_', ' ')} was rejected." + (f' Reason: "{comment}"' if comment else ""),
        )

    db.session.add(WorkflowAction(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        step_number=step.step_number,
        action_type="reject",
        actor_id=actor_id,
        old_status=old_status,
        new_status=new_status,
        comment=comment,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    db.session.commit()
    return instance


def delegate_step(instance, *, actor_id, role_id, delegate_to, comment=None, ip_address=None, user_agent=None):
    if instance.status != "pending":
        raise APIError(f"Cannot delegate on an instance that is already {instance.status}", status=400)

    step = _find_actionable_step_for_user(instance, user_id=actor_id, role_id=role_id)
    if step is None:
        raise APIError("You are not an approver for the current step of this workflow", status=403)

    db.session.add(WorkflowAction(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        step_number=instance.current_step_number,
        action_type="delegate",
        actor_id=actor_id,
        old_status=instance.status,
        new_status=instance.status,
        comment=comment,
        delegated_to=delegate_to,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    db.session.commit()
    return instance


def cancel_instance(instance, *, actor_id, comment=None, ip_address=None, user_agent=None):
    """Cancellation is deliberately not gated by "are you the current
    step's approver" -- it's the initiator (or an admin) withdrawing
    the request entirely, a different authorization question than
    approving a specific step. Route-level permission enforcement
    handles who's allowed to call this at all."""
    if instance.status != "pending":
        raise APIError(f"Cannot cancel an instance that is already {instance.status}", status=400)

    old_status = instance.status
    instance.status = "cancelled"

    db.session.add(WorkflowAction(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        step_number=instance.current_step_number,
        action_type="cancel",
        actor_id=actor_id,
        old_status=old_status,
        new_status="cancelled",
        comment=comment,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    db.session.commit()
    return instance


def add_comment(instance, *, actor_id, comment, ip_address=None, user_agent=None):
    db.session.add(WorkflowAction(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        step_number=instance.current_step_number,
        action_type="comment",
        actor_id=actor_id,
        comment=comment,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    db.session.commit()
    return instance
