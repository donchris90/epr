import { useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ReactFlow, Background, Controls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { createWorkflowDefinition, activateWorkflowDefinition } from "./hooks";
import { validateWorkflowDraft } from "./validation";
import { KNOWN_MODULE_ENTITY_PAIRS, type WorkflowDefinition, type WorkflowStep } from "./types";
import { hasPermission } from "../../lib/permissions";
import { UserSelect } from "../../components/UserSelect";
import { RoleSelect } from "../../components/RoleSelect";
import { Modal } from "../../components/Modal";
import { PageHeader, Card, Button, Input, Select, Field, ErrorBanner, Badge } from "../../components/ui";

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function newStep(stepNumber: number): WorkflowStep {
  return {
    step_number: stepNumber,
    name: "",
    approver_type: "specific_role",
    auto_escalate: false,
    allow_skip: false,
    parallel: false,
  };
}

/** Real, honest node-based builder over the actual backend data model
 * (backend/app/workflow/models.py) -- not a generic, arbitrary-graph
 * workflow designer. The real model is fundamentally linear (steps
 * ordered by step_number, with steps sharing a step_number forming a
 * real parallel-approval group, and an optional reject_to_step
 * pointing backward for rework), so that's exactly what this canvas
 * represents: no free-form edge drawing, no node types the backend
 * can't actually execute. Trigger is a real node here, but it only
 * ever configures module_name/entity_type -- there's no separate,
 * backend-configurable trigger condition beyond that pair.
 *
 * "Condition" and "action" node types from the brief have no real
 * backend representation beyond a step's own amount-range fields
 * (minimum_amount/maximum_amount) -- see docs/WORKFLOW_BUILDER_GAPS.md.
 * Rather than fake a generic condition/action node with nothing real
 * behind it, amount-range is exposed as part of each approval step's
 * own configuration, matching the real data model exactly. */
export default function WorkflowBuilderPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  // Real "Duplicate" support (WorkflowListPage's own Duplicate
  // action) -- a full WorkflowDefinition passed via navigation state,
  // not a URL param, since encoding a whole step array into a query
  // string would be unwieldy. There is no real backend "duplicate"
  // endpoint (create always makes a new version of the SAME
  // module/entity pair, not an independent copy) -- this is a
  // genuine frontend convenience: pre-fill the builder, let the
  // person adjust anything, then a real, ordinary create call saves
  // it as its own new definition.
  const duplicateFrom = (location.state as { duplicateFrom?: WorkflowDefinition } | null)?.duplicateFrom;

  const [workflowName, setWorkflowName] = useState(duplicateFrom ? `${duplicateFrom.workflow_name} (Copy)` : "");
  const [description, setDescription] = useState(duplicateFrom?.description ?? "");
  const [moduleName, setModuleName] = useState(duplicateFrom?.module_name ?? searchParams.get("module_name") ?? "");
  const [entityType, setEntityType] = useState(duplicateFrom?.entity_type ?? searchParams.get("entity_type") ?? "");
  const [customTrigger, setCustomTrigger] = useState(
    !KNOWN_MODULE_ENTITY_PAIRS.some((p) => p.module_name === moduleName && p.entity_type === entityType)
  );
  // Real ids stripped -- these are new, unsaved steps once duplicated,
  // not references back to the original definition's own step rows.
  const [steps, setSteps] = useState<WorkflowStep[]>(
    duplicateFrom ? duplicateFrom.steps.map((s) => ({ ...s, id: undefined })) : []
  );
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);


  const canManage = hasPermission("workflow:admin");

  function handleTriggerSelect(value: string) {
    if (value === "__custom__") {
      setCustomTrigger(true);
      return;
    }
    setCustomTrigger(false);
    const [m, e] = value.split("::");
    setModuleName(m);
    setEntityType(e);
  }

  function addStep() {
    const nextNumber = steps.length === 0 ? 1 : Math.max(...steps.map((s) => s.step_number)) + 1;
    setSteps((prev) => [...prev, newStep(nextNumber)]);
    setEditingIndex(steps.length);
  }

  function addParallelApprover(stepNumber: number) {
    setSteps((prev) => {
      const updated = [...prev, { ...newStep(stepNumber), parallel: true }];
      // Mark every step at this number as parallel, including the
      // original -- a group of one was never really "parallel" until
      // a second approver joined it.
      return updated.map((s) => (s.step_number === stepNumber ? { ...s, parallel: true } : s));
    });
    setEditingIndex(steps.length);
  }

  function removeStep(index: number) {
    setSteps((prev) => {
      const removedNumber = prev[index].step_number;
      const withoutStep = prev.filter((_, i) => i !== index);
      const stillHasNumber = withoutStep.some((s) => s.step_number === removedNumber);
      // If that was the only step at this number, close the gap by
      // shifting every later step_number down by one -- keeps the
      // sequential-numbering invariant validateWorkflowDraft checks
      // for, without asking the person to manually renumber anything.
      if (!stillHasNumber) {
        return withoutStep.map((s) => (s.step_number > removedNumber ? { ...s, step_number: s.step_number - 1 } : s));
      }
      return withoutStep;
    });
    setEditingIndex(null);
  }

  function updateStep(index: number, patch: Partial<WorkflowStep>) {
    setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  const draft = useMemo(
    () => ({ workflow_name: workflowName, module_name: moduleName, entity_type: entityType, steps }),
    [workflowName, moduleName, entityType, steps]
  );

  const stepGroups = useMemo(() => {
    const numbers = Array.from(new Set(steps.map((s) => s.step_number))).sort((a, b) => a - b);
    return numbers.map((num) => ({ number: num, steps: steps.map((s, i) => ({ ...s, _index: i })).filter((s) => s.step_number === num) }));
  }, [steps]);

  const { nodes, edges } = useMemo(() => {
    const flowNodes: Node[] = [
      {
        id: "trigger",
        position: { x: 260, y: 0 },
        data: { label: `Trigger\n${moduleName || "?"} / ${entityType || "?"}` },
        style: { background: "var(--sf-amber)", color: "#fff", borderRadius: 10, padding: 10, width: 220, textAlign: "center", whiteSpace: "pre-line", fontSize: 12 },
      },
    ];
    const flowEdges: Edge[] = [];
    let previousNodeIds = ["trigger"];

    stepGroups.forEach((group, groupIndex) => {
      const y = (groupIndex + 1) * 130;
      const currentNodeIds: string[] = [];
      const groupWidth = group.steps.length;
      group.steps.forEach((step, i) => {
        const nodeId = `step-${step._index}`;
        currentNodeIds.push(nodeId);
        const x = 260 + (i - (groupWidth - 1) / 2) * 240;
        flowNodes.push({
          id: nodeId,
          position: { x, y },
          data: {
            label: `${step.name || "(unnamed step)"}\nStep ${step.step_number}${step.parallel ? " · parallel" : ""}`,
          },
          style: {
            background: step.approver_type === "specific_user" ? "var(--sf-steel)" : "var(--sf-navy-700)",
            color: "#fff",
            borderRadius: 10,
            padding: 10,
            width: 220,
            textAlign: "center",
            whiteSpace: "pre-line",
            fontSize: 12,
          },
        });
        for (const prevId of previousNodeIds) {
          flowEdges.push({ id: `${prevId}-${nodeId}`, source: prevId, target: nodeId });
        }
        if (step.reject_to_step != null) {
          const targetGroup = stepGroups.find((g) => g.number === step.reject_to_step);
          if (targetGroup) {
            for (const target of targetGroup.steps) {
              flowEdges.push({
                id: `${nodeId}-reject-${target._index}`,
                source: nodeId,
                target: `step-${target._index}`,
                style: { stroke: "var(--sf-brick)", strokeDasharray: "4 4" },
                label: "on reject",
              });
            }
          }
        }
      });
      previousNodeIds = currentNodeIds;
    });

    return { nodes: flowNodes, edges: flowEdges };
  }, [stepGroups, moduleName, entityType]);

  function runValidation(): boolean {
    const errors = validateWorkflowDraft(draft);
    setValidationErrors(errors);
    return errors.length === 0;
  }

  async function handleSaveDraft() {
    if (!runValidation()) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createWorkflowDefinition(draft);
      navigate(`/workflows/${created.id}`);
    } catch (err: any) {
      setSaveError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!runValidation()) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createWorkflowDefinition(draft);
      await activateWorkflowDefinition(created.id);
      navigate(`/workflows/${created.id}`);
    } catch (err: any) {
      setSaveError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!canManage) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px" }}>
        <ErrorBanner
          title="You don't have permission to build workflows"
          detail="Creating and publishing workflows requires the workflow:admin permission. The real check also runs on the backend regardless of what this page shows."
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Workflow Engine"
        title={duplicateFrom ? `Duplicate: ${duplicateFrom.workflow_name}` : "New Workflow"}
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={handleSaveDraft} disabled={saving}>
              {saving ? "Saving…" : "Save Draft"}
            </Button>
            <Button onClick={handlePublish} disabled={saving}>
              {saving ? "Publishing…" : "Publish"}
            </Button>
          </div>
        }
      />

      {saveError && <ErrorBanner title="Something went wrong" detail={saveError} onDismiss={() => setSaveError(null)} />}
      {validationErrors.length > 0 && (
        <ErrorBanner
          title={`This workflow can't be published yet (${validationErrors.length} issue${validationErrors.length > 1 ? "s" : ""})`}
          detail={validationErrors.join(" ")}
          onDismiss={() => setValidationErrors([])}
        />
      )}

      <Card>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="Workflow name">
            <Input value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} placeholder="e.g. Purchase Request Approval" />
          </Field>
          <Field label="Trigger — module / entity type">
            <Select
              value={customTrigger ? "__custom__" : `${moduleName}::${entityType}`}
              onChange={(e) => handleTriggerSelect(e.target.value)}
            >
              <option value="">Select a trigger…</option>
              {KNOWN_MODULE_ENTITY_PAIRS.map((p) => (
                <option key={`${p.module_name}::${p.entity_type}`} value={`${p.module_name}::${p.entity_type}`}>
                  {p.label}
                </option>
              ))}
              <option value="__custom__">Custom (type module / entity type)</option>
            </Select>
          </Field>
        </div>
        {customTrigger && (
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 12 }}>
            <Field label="Module name">
              <Input value={moduleName} onChange={(e) => setModuleName(e.target.value)} placeholder="e.g. prc" />
            </Field>
            <Field label="Entity type">
              <Input value={entityType} onChange={(e) => setEntityType(e.target.value)} placeholder="e.g. purchase_request" />
            </Field>
          </div>
        )}
        <div style={{ marginTop: 12 }}>
          <Field label="Description">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" />
          </Field>
        </div>
      </Card>

      <div style={{ marginTop: 16, height: 420, border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", background: "#fff" }}>
        <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div style={{ marginTop: 16 }}>
        {stepGroups.map((group) => (
          <Card key={group.number} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>
                Step {group.number} {group.steps.length > 1 && <Badge tone="steel">Parallel</Badge>}
              </div>
              <Button variant="ghost" onClick={() => addParallelApprover(group.number)}>
                + Parallel approver
              </Button>
            </div>
            {group.steps.map((step) => (
              <div
                key={step._index}
                onClick={() => setEditingIndex(step._index)}
                style={{ padding: "8px 10px", borderTop: "1px solid var(--sf-line)", cursor: "pointer", display: "flex", justifyContent: "space-between" }}
              >
                <span>{step.name || <em style={{ color: "var(--sf-navy-400)" }}>Click to configure</em>}</span>
                <Button variant="ghost" onClick={(e) => { e.stopPropagation(); removeStep(step._index); }}>
                  Remove
                </Button>
              </div>
            ))}
          </Card>
        ))}
        <Button variant="secondary" onClick={addStep}>
          + Add Step
        </Button>
      </div>

      {editingIndex !== null && steps[editingIndex] && (
        <StepConfigModal
          step={steps[editingIndex]}
          allStepNumbers={Array.from(new Set(steps.map((s) => s.step_number))).filter((n) => n < steps[editingIndex].step_number)}
          onChange={(patch) => updateStep(editingIndex, patch)}
          onClose={() => setEditingIndex(null)}
        />
      )}
    </div>
  );
}

function StepConfigModal({
  step,
  allStepNumbers,
  onChange,
  onClose,
}: {
  step: WorkflowStep;
  allStepNumbers: number[];
  onChange: (patch: Partial<WorkflowStep>) => void;
  onClose: () => void;
}) {
  return (
    <Modal title={`Configure: ${step.name || "New step"}`} onClose={onClose} width={480}>
      <Field label="Step name">
        <Input value={step.name} onChange={(e) => onChange({ name: e.target.value })} placeholder="e.g. Finance Approval" autoFocus />
      </Field>

      <Field label="Approver type">
        <Select value={step.approver_type} onChange={(e) => onChange({ approver_type: e.target.value as WorkflowStep["approver_type"], specific_user_id: undefined, required_role_id: undefined })}>
          <option value="specific_role">A specific role — anyone holding it can approve</option>
          <option value="specific_user">A specific person</option>
        </Select>
      </Field>

      {step.approver_type === "specific_user" ? (
        <Field label="Approver">
          <UserSelect value={step.specific_user_id ?? ""} onChange={(id) => onChange({ specific_user_id: id })} required />
        </Field>
      ) : (
        <Field label="Approver role">
          <RoleSelect value={step.required_role_id ?? ""} onChange={(id) => onChange({ required_role_id: id })} required />
        </Field>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <Field label="Minimum amount (₦, optional)">
            <Input
              type="number"
              value={step.minimum_amount ?? ""}
              onChange={(e) => onChange({ minimum_amount: e.target.value || undefined })}
              placeholder="No minimum"
            />
          </Field>
        </div>
        <div style={{ flex: 1 }}>
          <Field label="Maximum amount (₦, optional)">
            <Input
              type="number"
              value={step.maximum_amount ?? ""}
              onChange={(e) => onChange({ maximum_amount: e.target.value || undefined })}
              placeholder="No maximum"
            />
          </Field>
        </div>
      </div>
      <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: -8, marginBottom: 12 }}>
        Leave both blank for a step that always applies. If set, this step is skipped automatically for submissions outside this range.
      </p>

      {allStepNumbers.length > 0 && (
        <Field label="On rejection, return to (optional)">
          <Select value={step.reject_to_step ?? ""} onChange={(e) => onChange({ reject_to_step: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">Reject terminates the request</option>
            {allStepNumbers.map((n) => (
              <option key={n} value={n}>
                Step {n} (for rework)
              </option>
            ))}
          </Select>
        </Field>
      )}

      <Field label="SLA duration, hours (optional)">
        <Input
          type="number"
          value={step.timeout_hours ?? ""}
          onChange={(e) => onChange({ timeout_hours: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="No SLA"
        />
      </Field>
      {step.timeout_hours && (
        <div style={{ marginTop: -8, marginBottom: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <input type="checkbox" checked={step.auto_escalate} onChange={(e) => onChange({ auto_escalate: e.target.checked })} />
            Escalate after SLA elapses
          </label>
          <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 4, marginLeft: 24 }}>
            Recorded, not yet enforced by a scheduler -- no automatic escalation actually happens yet. There's also no
            real "escalation target" field on the backend today (who it would escalate to); this checkbox only
            records the intent.
          </p>
        </div>
      )}

      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
        <input type="checkbox" checked={step.allow_skip} onChange={(e) => onChange({ allow_skip: e.target.checked })} />
        Allow this step to be skipped
      </label>

      <div style={{ marginTop: 16, textAlign: "right" }}>
        <Button onClick={onClose}>Done</Button>
      </div>
    </Modal>
  );
}
