import { LegalLayout, Section } from "./LegalLayout";
import { LEGAL } from "./legalConfig";

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy">
      <p style={{ marginBottom: 20 }}>
        This policy explains how {LEGAL.company} ("we", "us") handles personal data when you use the SiteForge construction management platform,
        including the subcontractor, vendor and client portals. We process personal data in line with the Nigeria Data Protection Act 2023
        (NDPA).
      </p>

      <Section title="1. Who is responsible for your data">
        <p>
          Your employer or contracting company (the "workspace owner") decides what personal data is entered into its SiteForge workspace and
          why; for that data it is the data controller and we act as its processor. We are the controller for account, billing and security data
          we need to run the service. Questions about a specific workspace's data are best sent to that workspace owner first.
        </p>
      </Section>

      <Section title="2. What we collect">
        <ul>
          <li><strong>Account data:</strong> email address, a hashed password (never the plain password), role and access permissions, last sign-in time.</li>
          <li><strong>Workspace records entered by users:</strong> for example employees and casual workers (name, phone, trade, pay rate, certifications), client, vendor and subcontractor contacts, project records and uploaded documents. What an uploaded file contains is decided by the person uploading it.</li>
          <li><strong>Portal users:</strong> subcontractor, vendor and client portal accounts (email, organisation link) and what they submit, such as progress, claims, quotes, invoices and requested bank-detail changes.</li>
          <li><strong>Technical data:</strong> basic request and error logs used to keep the service secure and working.</li>
        </ul>
      </Section>

      <Section title="3. How we use it">
        <p>
          To provide and secure the service, authenticate users, send service emails (for example password resets and notifications), process
          subscription payments, diagnose errors, and meet legal obligations. We do not sell personal data.
        </p>
      </Section>

      <Section title="4. Who we share it with">
        <p>We use service providers who process data on our behalf, for the purposes above only:</p>
        <ul>
          <li>Cloud hosting and database (Render)</li>
          <li>File storage (S3-compatible object storage)</li>
          <li>Email delivery (Resend)</li>
          <li>Payment processing (Paystack)</li>
          <li>Error monitoring (Sentry)</li>
        </ul>
        <p>
          Some providers are located outside Nigeria, so data may be transferred internationally. Where this happens we rely on appropriate
          safeguards as the NDPA requires. We may also disclose data where the law requires it.
        </p>
      </Section>

      <Section title="5. Security">
        <p>
          Each workspace's data is isolated from others at the database level, passwords are stored using strong one-way hashing, and traffic
          is encrypted in transit. Regular backups are taken. No system is perfectly secure; if a breach affecting your personal data occurs we
          will notify the people and authorities required by law.
        </p>
      </Section>

      <Section title="6. How long we keep data">
        <p>
          Workspace data is kept while the workspace is active, because many construction records (for example certificates and journal
          entries) must remain as a permanent audit trail. After a workspace closes, or when a valid deletion request applies, we delete or
          anonymise personal data unless we must keep it by law. Backups are overwritten on a rolling schedule of about 30 days.
        </p>
      </Section>

      <Section title="7. Your rights">
        <p>
          Under the NDPA you may ask to access your personal data, correct it, delete it, restrict or object to its processing, receive a copy
          in a portable format, and withdraw consent where processing is based on consent. You may also complain to the Nigeria Data Protection
          Commission.
        </p>
        <p>
          To exercise these rights, email <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>. We aim to respond within 30 days.
          We may need to confirm your identity first, and where your data sits in a workspace controlled by your employer we may refer you to
          them.
        </p>
      </Section>

      <Section title="8. Children">
        <p>The service is for business use and is not directed at children.</p>
      </Section>

      <Section title="9. Changes">
        <p>We will update this page when our practices change and revise the date above. Material changes will be notified in the product or by email.</p>
      </Section>

      <Section title="10. Contact">
        <p>
          {LEGAL.company}
          {LEGAL.address ? `, ${LEGAL.address}` : ""} — <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>
        </p>
      </Section>
    </LegalLayout>
  );
}
