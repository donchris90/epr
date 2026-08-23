export type PasswordStrength = "too_short" | "weak" | "fair" | "strong";

/** Real, simple, deliberately transparent scoring -- length plus
 * character variety (lowercase, uppercase, digit, symbol). No attempt
 * to match a specific backend policy, since the backend's only real
 * rule is a minimum length of 8 (backend/app/auth/schemas.py's
 * ResetPasswordSchema/ChangePasswordSchema, validate.Length(min=8)) --
 * this is purely a UX signal encouraging a stronger password than the
 * bare minimum, not a second source of truth for what's actually
 * required. The backend remains authoritative; a password this scores
 * "weak" that's still 8+ characters is still accepted. */
export function scorePasswordStrength(password: string): PasswordStrength {
  if (password.length < 8) return "too_short";

  let variety = 0;
  if (/[a-z]/.test(password)) variety++;
  if (/[A-Z]/.test(password)) variety++;
  if (/[0-9]/.test(password)) variety++;
  if (/[^a-zA-Z0-9]/.test(password)) variety++;

  if (password.length >= 12 && variety >= 3) return "strong";
  if (password.length >= 10 && variety >= 2) return "fair";
  if (variety >= 2) return "fair";
  return "weak";
}

export const PASSWORD_STRENGTH_LABEL: Record<PasswordStrength, string> = {
  too_short: "Too short (minimum 8 characters)",
  weak: "Weak",
  fair: "Fair",
  strong: "Strong",
};

export const PASSWORD_STRENGTH_COLOR: Record<PasswordStrength, string> = {
  too_short: "var(--sf-brick)",
  weak: "var(--sf-brick)",
  fair: "var(--sf-amber)",
  strong: "var(--sf-green)",
};
