"""
Workflow engine service layer -- see app/workflow/models.py for the
full design scope and honest limitations.
"""
from app.extensions import db
from app.utils.errors import APIError
from app.workflow.models import WorkflowDefinition, WorkflowStep, WorkflowInstance, WorkflowAction


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


def activate_workflow_definition(definition):
    """Deactivates any other active definition for the same
    (module_name, entity_type) first -- only one version should be
    live at a time. Instances already in flight under a
    now-deactivated definition are unaffected; they keep referencing
    the same workflow_id and finish under the rules they started
    with."""
    WorkflowDefinition.query.filter_by(
        tenant_id=definition.tenant_id,
        module_name=definition.module_name,
        entity_type=definition.entity_type,
        active=True,
    ).update({"active": False})

    definition.active = True
    db.session.commit()
    return definition


def deactivate_workflow_definition(definition):
    definition.active = False
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
        else:
            instance.current_step_number = next_number

    db.session.commit()
    return instance


def reject_step(instance, *, actor_id, role_id, comment=None, ip_address=None, user_agent=None):
    if instance.status != "pending":
        raise APIError(f"Cannot reject an instance that is already {instance.status}", status=400)

    step = _find_actionable_step_for_user(instance, user_id=actor_id, role_id=role_id)
    if step is None:
        raise APIError("You are not an approver for the current step of this workflow", status=403)

    old_status = instance.status
    if step.reject_to_step is not None:
        instance.current_step_number = step.reject_to_step
        new_status = "pending"
    else:
        instance.status = "rejected"
        new_status = "rejected"

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
