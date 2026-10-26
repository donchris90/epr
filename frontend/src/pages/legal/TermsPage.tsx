import { Link } from "react-router-dom";
import { LegalLayout, Section } from "./LegalLayout";
import { LEGAL } from "./legalConfig";

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service">
      <p style={{ marginBottom: 20 }}>
        These terms govern your use of SiteForge, provided by {LEGAL.company} ("we", "us"). By creating a workspace or signing in you agree to
        them. If you use SiteForge on behalf of a company, you confirm you are authorised to bind that company.
      </p>

      <Section title="1. The service">
        <p>
          SiteForge is a cloud platform for managing construction projects, including estimating, procurement, subcontracting, workforce, finance
          and external portals. We may improve or change features from time to time.
        </p>
      </Section>

      <Section title="2. Accounts and workspaces">
        <p>
          Keep your sign-in details secure and tell us promptly if you suspect misuse. The workspace owner is responsible for the users it
          invites, the access it grants (including to subcontractors, vendors and clients) and everything done under its accounts.
        </p>
      </Section>

      <Section title="3. Acceptable use">
        <p>
          Do not misuse the service: no unlawful content, no attempts to access other workspaces' data, no probing or disrupting the platform,
          no reverse engineering, and no uploading of malware. We may suspend access that threatens the service or other customers.
        </p>
      </Section>

      <Section title="4. Your data">
        <p>
          You keep ownership of the data you put into SiteForge. You give us the right to host and process it only to provide the service. You
          are responsible for having the right to enter personal data into your workspace and for using it lawfully. How we handle personal
          data is described in our <Link to="/privacy">Privacy Policy</Link>.
        </p>
      </Section>

      <Section title="5. Subscriptions and payment">
        <p>
          Paid plans are billed in advance through our payment provider. Unless a plan says otherwise, fees are non-refundable once a billing
          period starts. If a trial or subscription lapses, access to the workspace is restricted until it is renewed; we keep your data for a
          reasonable period so you can reactivate.
        </p>
      </Section>

      <Section title="6. Availability and support">
        <p>
          We work to keep SiteForge available and take regular backups, but we do not guarantee uninterrupted or error-free service. Planned
          maintenance may cause short interruptions.
        </p>
      </Section>

      <Section title="7. Liability">
        <p>
          The service supports your decisions but does not replace professional judgement: you remain responsible for the accuracy of estimates,
          certificates, payments and compliance records you rely on. To the extent the law permits, we are not liable for indirect or
          consequential loss, and our total liability for any claim is limited to the fees you paid us in the 12 months before it arose.
          Nothing here limits liability that cannot lawfully be limited.
        </p>
      </Section>

      <Section title="8. Ending the agreement">
        <p>
          You may stop using SiteForge and close your workspace at any time. We may suspend or end access for breach of these terms or non-payment.
          On closure we handle your data as described in the Privacy Policy.
        </p>
      </Section>

      <Section title="9. Changes to these terms">
        <p>We may update these terms; we will give notice of material changes. Continued use after a change means you accept it.</p>
      </Section>

      <Section title="10. Governing law">
        <p>These terms are governed by {LEGAL.governingLaw}. Disputes will be dealt with by the courts of that jurisdiction.</p>
      </Section>

      <Section title="11. Contact">
        <p><a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a></p>
      </Section>
    </LegalLayout>
  );
}
