# Executive Dashboard — Backend Gaps

Written the same way every other `*_GAPS.md` in this repo was: an
honest account of what this rebuild found, fixed, and built on real
data, and what remains genuinely unbacked — not a feature list.

## Real bugs found and fixed, not just cosmetic gaps

Before adding anything new, inspecting the existing dashboard turned
up real, already-broken functionality:

- **Revenue and Equipment Utilization have never worked.**
  `CompanyRevenueQuerySchema` and `EquipmentUtilizationQuerySchema`
  both require `period_start`/`period_end` (confirmed directly in
  `backend/app/modules/exd/schemas.py`), but the frontend hooks never
  sent them. Reproduced directly: `company-revenue` returns a 422;
  `equipment-utilization` doesn't even catch the validation error and
  returns a raw 500. Both silently rendered as a fake "No data yet"
  empty state on the dashboard — indistinguishable from genuinely
  having no data. Fixed with a real year-to-date default
  (`modules/exd/hooks.ts`).
- **The revenue widget read a field that doesn't exist.** The real
  field is `budget_amount`; the page read `revenue.budgeted_revenue`,
  always `undefined`. TypeScript caught this the moment the response
  was properly typed instead of left as `any`.
- **The CPI/SPI table showed a raw, truncated project UUID** instead
  of the project's name — `active-projects-performance` never joins
  to `Project` (confirmed directly in
  `backend/app/modules/exd/services.py`; it only knows `project_id`
  from Module 19's `EVMSnapshot`). Fixed by fetching real project
  names and mapping client-side, the same established pattern already
  used elsewhere in this codebase (e.g. `prc/PurchaseOrdersPage.tsx`'s
  `vendorsById`).

## Real, small backend addition

`Incident.occurred_at` already existed on the model but was never
dumped by `IncidentSchema` — there was no way to build a real safety
trend without it. Exposed the existing column (no migration, no new
logic, `dump_only`) specifically so the dashboard's Safety trend could
group real incidents by real month instead of inventing one.

## What each new section is real, and isn't

**Commercial**: tender pipeline (real counts by status from `GET
/v1/tbm/tenders`) and win rate (`awarded / (awarded + lost)`, computed
from the same real, already-decided tenders). No fabricated "contract
value" or "opportunities" figure was added beyond what's directly
computable from real tender records — see the gap below for why
contract value specifically isn't shown.

**HSE**: real incident counts by classification and a real trend by
month (`GET /v1/hse/incidents`, now with `occurred_at`). Deliberately
**not** TRIR/LTIFR rates, near-miss counts, or a formal "safety trend"
score — see the gap below.

**Workforce**: real active headcount and a real permanent/contract
split (`GET /v1/wfm/employees`, filtered/grouped client-side, no
fabricated aggregation).

## Genuine gaps — not built, and not faked

**No TRIR/LTIFR rates, no near-miss count.** The real, existing
rate-calculating endpoint (`GET /v1/hse/safety-indicators`) requires a
real `total_hours_worked` figure — confirmed `required=True` on
`SafetyIndicatorsQuerySchema`, and confirmed via that service
function's own docstring that HSE doesn't own hours-worked data itself
("`total_hours_worked` is supplied by the caller since HSE does not
own Module 6/11's hours data"). There is no dashboard-accessible,
honest source for this figure today; passing a placeholder would
produce a fake rate dressed up as a real one, which is worse than not
showing a rate at all. Near-miss counts have the identical problem —
only reachable via that same endpoint, for the same reason.

```
BACKEND GAP:
Endpoint: none directly -- would need either a real hours-worked
  aggregation endpoint (summing real WFM timesheet/attendance data
  for a period) or a documented, deliberate simplification the
  dashboard could cite honestly (e.g. headcount x period length as an
  approximation, clearly labeled as such)
Why frontend requires it: without a real hours figure, TRIR/LTIFR
  and near-miss counts have no honest value to display.
```

**No Margin, Cash, or Budget variance beyond revenue's own
variance.** `get_company_revenue` computes actual-vs-budget revenue
variance, already shown — but there's no real "cost" or "margin"
aggregation endpoint in `exd`, `fin`, or `pc` that this dashboard
could honestly reuse (`fin`'s income-statement generation is a
per-request report, not a dashboard-ready summary, and computing a
tenant-wide margin figure correctly would mean replicating real
accounting logic this dashboard shouldn't own independently).

**No "on track / at risk / delayed / over budget" project
classification, no completion percentage.** The real CPI/SPI data
shown lets a person judge this themselves (a project below 0.9 on
either is already flagged in red), but there's no backend-defined
threshold or classification scheme to reuse honestly — inventing one
here would mean deciding a business rule (what counts as "at risk")
that belongs in the EVM/PC module itself, not fabricated on the
dashboard.

**No workforce productivity.** No real, existing endpoint computes
this anywhere in the codebase for any module; nothing to reuse
honestly.

**No opportunities count for Commercial**, distinct from the tender
pipeline already shown — Module 3's own BDC opportunity pipeline
(`bdc/OpportunitiesPage.tsx`) is a real, separate concept from
tenders, and combining them into one "Commercial" figure without a
clear, backend-defined relationship between an opportunity and the
tender(s) it produced would be misleading rather than useful. Left as
two genuinely separate concerns.

## What was deliberately not built as a fake feature

No TRIR/LTIFR score, no margin/cash figure, no project-status
classification, no productivity metric, no combined opportunities
count — each omitted rather than approximated with a number that
looks real but isn't backed by anything real. This matches every
other gaps document in this repo: an honest dashboard showing less is
better than a complete-looking one showing invented numbers.
