/** Operator details shown on the legal pages. Set these at build time
 * (Render static-site env vars) -- the defaults are placeholders and
 * must be replaced before launch. */
export const LEGAL = {
  company: import.meta.env.VITE_LEGAL_COMPANY_NAME || "SiteForge",
  contactEmail: import.meta.env.VITE_LEGAL_CONTACT_EMAIL || "privacy@siteforge.example",
  address: import.meta.env.VITE_LEGAL_ADDRESS || "",
  governingLaw: import.meta.env.VITE_LEGAL_GOVERNING_LAW || "the laws of the Federal Republic of Nigeria",
  // Bump when the text of either page materially changes.
  lastUpdated: "26 October 2026",
};
