import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Badge, Input, Field, Table, Th, Td } from "../../components/ui";
import {
  useDiary,
  useUpdateDiary,
  useSignDiary,
  useCountersignDiary,
  useAddAmendment,
  useAmendments,
  useAddWeatherRecord,
  useWeatherRecords,
  useAddLaborUsage,
  useLaborUsage,
  useAddEquipmentUsage,
  useEquipmentUsage,
} from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green"> = {
  draft: "neutral",
  signed: "amber",
  countersigned: "green",
};

export default function DiaryDetailPage() {
  const { diaryId } = useParams();
  const { data: diary, isLoading } = useDiary(diaryId);
  const { data: amendments } = useAmendments(diaryId);
  const { data: weather } = useWeatherRecords(diaryId);
  const { data: laborUsage } = useLaborUsage(diaryId);
  const { data: equipmentUsage } = useEquipmentUsage(diaryId);

  const updateDiary = useUpdateDiary(diaryId);
  const signDiary = useSignDiary(diaryId);
  const countersignDiary = useCountersignDiary(diaryId);
  const addAmendment = useAddAmendment(diaryId);
  const addWeather = useAddWeatherRecord(diaryId);
  const addLabor = useAddLaborUsage(diaryId);
  const addEquipment = useAddEquipmentUsage(diaryId);

  const [narrative, setNarrative] = useState("");
  const [amendmentText, setAmendmentText] = useState("");
  const [weatherForm, setWeatherForm] = useState({ condition: "", temperature_c: "", rainfall_mm: "" });
  const [laborForm, setLaborForm] = useState({ trade: "", headcount: "", hours_worked: "" });
  const [equipForm, setEquipForm] = useState({ equipment_identifier: "", hours_used: "", operator_name: "" });

  if (isLoading || !diary) return <p>Loading…</p>;

  const isLocked = diary.status !== "draft";
  const narrativeValue = narrative || diary.narrative || "";

  async function handleSaveNarrative() {
    await updateDiary.mutateAsync({ narrative: narrativeValue });
  }

  async function handleAmend(e: React.FormEvent) {
    e.preventDefault();
    await addAmendment.mutateAsync(amendmentText);
    setAmendmentText("");
  }

  async function handleWeather(e: React.FormEvent) {
    e.preventDefault();
    await addWeather.mutateAsync({
      condition: weatherForm.condition || undefined,
      temperature_c: weatherForm.temperature_c || undefined,
      rainfall_mm: weatherForm.rainfall_mm || undefined,
    });
    setWeatherForm({ condition: "", temperature_c: "", rainfall_mm: "" });
  }

  async function handleLabor(e: React.FormEvent) {
    e.preventDefault();
    await addLabor.mutateAsync({
      trade: laborForm.trade,
      headcount: Number(laborForm.headcount),
      hours_worked: laborForm.hours_worked,
    });
    setLaborForm({ trade: "", headcount: "", hours_worked: "" });
  }

  async function handleEquipment(e: React.FormEvent) {
    e.preventDefault();
    await addEquipment.mutateAsync({
      equipment_identifier: equipForm.equipment_identifier,
      hours_used: equipForm.hours_used,
      operator_name: equipForm.operator_name || undefined,
    });
    setEquipForm({ equipment_identifier: "", hours_used: "", operator_name: "" });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Daily Site Diary"
        title={new Date(diary.diary_date).toLocaleDateString(undefined, {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        })}
        action={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Badge tone={STATUS_TONE[diary.status] ?? "neutral"}>{diary.status}</Badge>
            {diary.status === "draft" && (
              <Button onClick={() => signDiary.mutate()} disabled={signDiary.isPending}>
                {signDiary.isPending ? "Signing…" : "Sign diary"}
              </Button>
            )}
            {diary.status === "signed" && (
              <Button onClick={() => countersignDiary.mutate()} disabled={countersignDiary.isPending}>
                {countersignDiary.isPending ? "Countersigning…" : "Countersign"}
              </Button>
            )}
          </div>
        }
      />

      {isLocked && (
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            padding: "12px 16px",
            marginBottom: 20,
            background: "var(--sf-amber-dim)",
            border: "1px solid var(--sf-amber)",
            borderRadius: "var(--sf-radius)",
            fontSize: 13,
          }}
        >
          <span aria-hidden style={{ color: "#8a5f14" }}>
            🔒
          </span>
          <div>
            <strong style={{ color: "#8a5f14" }}>This diary is {diary.status} and locked.</strong>{" "}
            The narrative and figures above cannot be edited directly — the record of what was originally signed
            stays intact. To correct or add information, record a dated amendment below; it will appear
            alongside the original entry, never replace it.
          </div>
        </div>
      )}

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Narrative</h3>
            <textarea
              disabled={isLocked}
              value={narrativeValue}
              onChange={(e) => setNarrative(e.target.value)}
              rows={5}
              style={{
                width: "100%",
                padding: "8px 10px",
                border: "1px solid var(--sf-line)",
                borderRadius: "var(--sf-radius)",
                fontSize: 13,
                fontFamily: "inherit",
                resize: "vertical",
                background: isLocked ? "var(--sf-paper-dim)" : "#fff",
                color: isLocked ? "var(--sf-navy-600)" : "inherit",
              }}
            />
            {!isLocked && (
              <div style={{ marginTop: 10 }}>
                <Button variant="secondary" onClick={handleSaveNarrative} disabled={updateDiary.isPending}>
                  {updateDiary.isPending ? "Saving…" : "Save narrative"}
                </Button>
              </div>
            )}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Weather</h3>
            {weather?.length ? (
              <ul style={{ margin: "0 0 12px", padding: 0, listStyle: "none", fontSize: 13 }}>
                {weather.map((w: any) => (
                  <li key={w.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
                    <span className="sf-mono">{w.condition || "—"}</span>
                    {w.temperature_c && <span className="sf-mono"> · {w.temperature_c}°C</span>}
                    {w.rainfall_mm && <span className="sf-mono"> · {w.rainfall_mm}mm rain</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No weather logged yet.</p>
            )}
            {!isLocked && (
              <form onSubmit={handleWeather} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8 }}>
                <Input
                  placeholder="Condition"
                  value={weatherForm.condition}
                  onChange={(e) => setWeatherForm({ ...weatherForm, condition: e.target.value })}
                />
                <Input
                  placeholder="Temp °C"
                  value={weatherForm.temperature_c}
                  onChange={(e) => setWeatherForm({ ...weatherForm, temperature_c: e.target.value })}
                />
                <Input
                  placeholder="Rainfall mm"
                  value={weatherForm.rainfall_mm}
                  onChange={(e) => setWeatherForm({ ...weatherForm, rainfall_mm: e.target.value })}
                />
                <Button type="submit" variant="secondary" disabled={addWeather.isPending}>
                  Add
                </Button>
              </form>
            )}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Labor on site</h3>
            {laborUsage?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Trade</Th>
                    <Th>Headcount</Th>
                    <Th>Hours</Th>
                  </tr>
                </thead>
                <tbody>
                  {laborUsage.map((l: any) => (
                    <tr key={l.id}>
                      <Td>{l.trade}</Td>
                      <Td mono>{l.headcount}</Td>
                      <Td mono>{l.hours_worked}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No labor recorded yet.</p>
            )}
            {!isLocked && (
              <form
                onSubmit={handleLabor}
                className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginTop: 12 }}
              >
                <Input
                  required
                  placeholder="Trade (e.g. Mason)"
                  value={laborForm.trade}
                  onChange={(e) => setLaborForm({ ...laborForm, trade: e.target.value })}
                />
                <Input
                  required
                  type="number"
                  min={1}
                  placeholder="Headcount"
                  value={laborForm.headcount}
                  onChange={(e) => setLaborForm({ ...laborForm, headcount: e.target.value })}
                />
                <Input
                  required
                  placeholder="Hours"
                  value={laborForm.hours_worked}
                  onChange={(e) => setLaborForm({ ...laborForm, hours_worked: e.target.value })}
                />
                <Button type="submit" variant="secondary" disabled={addLabor.isPending}>
                  Add
                </Button>
              </form>
            )}
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Equipment on site</h3>
            {equipmentUsage?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Equipment</Th>
                    <Th>Hours used</Th>
                    <Th>Operator</Th>
                  </tr>
                </thead>
                <tbody>
                  {equipmentUsage.map((eq: any) => (
                    <tr key={eq.id}>
                      <Td>{eq.equipment_identifier}</Td>
                      <Td mono>{eq.hours_used}</Td>
                      <Td>{eq.operator_name || "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No equipment recorded yet.</p>
            )}
            {!isLocked && (
              <form
                onSubmit={handleEquipment}
                className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginTop: 12 }}
              >
                <Input
                  required
                  placeholder="Equipment ID"
                  value={equipForm.equipment_identifier}
                  onChange={(e) => setEquipForm({ ...equipForm, equipment_identifier: e.target.value })}
                />
                <Input
                  required
                  placeholder="Hours used"
                  value={equipForm.hours_used}
                  onChange={(e) => setEquipForm({ ...equipForm, hours_used: e.target.value })}
                />
                <Input
                  placeholder="Operator"
                  value={equipForm.operator_name}
                  onChange={(e) => setEquipForm({ ...equipForm, operator_name: e.target.value })}
                />
                <Button type="submit" variant="secondary" disabled={addEquipment.isPending}>
                  Add
                </Button>
              </form>
            )}
          </Card>
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>Signatures</h3>
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
              Signing locks the entry; countersigning is the client/consultant's independent confirmation.
            </p>
            <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Signed</div>
                <div className="sf-mono">{diary.signed_at ? new Date(diary.signed_at).toLocaleString() : "Not yet signed"}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Countersigned</div>
                <div className="sf-mono">
                  {diary.countersigned_at ? new Date(diary.countersigned_at).toLocaleString() : "Not yet countersigned"}
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Amendments</h3>
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
              The only way to correct a locked diary — every amendment is a dated, attributed addition, never an
              edit to the original.
            </p>
            {amendments?.length ? (
              <ul style={{ margin: "0 0 14px", padding: 0, listStyle: "none" }}>
                {amendments.map((a: any) => (
                  <li
                    key={a.id}
                    style={{
                      fontSize: 13,
                      padding: "8px 0",
                      borderBottom: "1px solid var(--sf-line)",
                    }}
                  >
                    <div style={{ marginBottom: 2 }}>{a.description}</div>
                    <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>
                      {new Date(a.created_at).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 14 }}>No amendments recorded.</p>
            )}
            <form onSubmit={handleAmend}>
              <Field label="Add an amendment">
                <Input
                  required
                  placeholder="e.g. Workforce count corrected from 24 to 26"
                  value={amendmentText}
                  onChange={(e) => setAmendmentText(e.target.value)}
                />
              </Field>
              <Button type="submit" variant="secondary" disabled={addAmendment.isPending}>
                {addAmendment.isPending ? "Recording…" : "Record amendment"}
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
