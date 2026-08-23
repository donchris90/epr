import { scorePasswordStrength, PASSWORD_STRENGTH_LABEL, PASSWORD_STRENGTH_COLOR } from "../lib/passwordStrength";

const BAR_COUNT = 4;
const STRENGTH_LEVEL: Record<string, number> = { too_short: 0, weak: 1, fair: 2, strong: 4 };

/** Real, visible password strength feedback -- shown for both the
 * reset-password and change-password flows (the task's own explicit
 * requirement for both). Purely a UX signal on top of the backend's
 * real, authoritative minimum-length rule (see passwordStrength.ts's
 * own docstring) -- never blocks submission itself, that's the
 * backend's job via the real 8-character minimum it already enforces. */
export function PasswordStrengthMeter({ password }: { password: string }) {
  if (!password) return null;

  const strength = scorePasswordStrength(password);
  const level = STRENGTH_LEVEL[strength];
  const color = PASSWORD_STRENGTH_COLOR[strength];

  return (
    <div style={{ marginTop: -8, marginBottom: 14 }} aria-live="polite">
      <div style={{ display: "flex", gap: 4 }}>
        {Array.from({ length: BAR_COUNT }).map((_, i) => (
          <div
            key={i}
            style={{
              height: 4,
              flex: 1,
              borderRadius: 2,
              background: i < level ? color : "var(--sf-line)",
              transition: "background 0.15s",
            }}
          />
        ))}
      </div>
      <div style={{ fontSize: 11, color, marginTop: 4 }}>{PASSWORD_STRENGTH_LABEL[strength]}</div>
    </div>
  );
}
