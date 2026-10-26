# Factory manufacturing (MFG)

First slice of making SiteForge usable by factories, not only contractors.
Branch `factory-manufacturing`. Migration `0063_factory_manufacturing`.

## What it does

- **Item types** on the inventory catalog (raw material, semi-finished, finished good, consumable, other). Existing items become `other`.
- **Batch quality hold**: a batch is `released`, `quarantined` or `rejected`. `PUT /v1/inv/batch-numbers/<id>/status` (needs `inv:approve`); `GET /v1/inv/batch-numbers?status=`.
- **Work centers** (`/v1/mfg/work-centers`): a line or machine with an hourly labour+overhead rate and an optional linked equipment record.
- **Bills of materials** (`/v1/mfg/boms`): components per output quantity, with an expected scrap percentage per line. Editing a BOM replaces its lines.
- **Production orders** (`/v1/mfg/production-orders`): draft → released → in progress → done (or cancelled). Creating one snapshots the components needed, so later BOM edits do not change it.
- **Completing a run** (`POST .../complete`, needs `mfg:approve`) in one transaction:
  1. draws each component from the order's warehouse (default = the BOM quantity for the good + scrapped units actually run; you can override per component),
  2. costs the run: materials (at the tenant's FIFO / weighted-average valuation) + labour hours × work-center rate + fuel,
  3. receives the finished goods at `total cost / good units` (scrap cost is carried by the good units),
  4. creates the finished-goods batch when given a batch number (required for batch-tracked products), optionally quarantined.
  If anything fails (e.g. a component is short) everything is rolled back; nothing is half-consumed.
- **Availability** (`.../availability`): needed vs available per component before starting.
- **Variances** (`.../variances`): used minus what the BOM expected for the quantity actually run.
- **Fuel in the cost**: pass `fuel_litres` with either a `fuel_tank_id` (draws the litres from the tank as a fuel issue against the work center's linked equipment, priced at the tank's latest confirmed purchase unless `fuel_unit_cost` is given) or just `fuel_unit_cost` (costed only, no tank movement).

Permissions: `mfg:read`, `mfg:write`, `mfg:approve` (completion). Grant them to the roles that need them; `*` already covers them.

UI: **Manufacturing** in the Supply Chain menu → Production orders / Bills of materials / Work centers. Inventory's item form now has item type and batch tracking.

## Not built (honest limits)

- **Quarantine is a record, not a lock.** Stock issue is not batch-aware, so a quarantined or rejected batch is flagged and filterable but not blocked from being issued.
- **Single-level BOMs.** Multi-level products work by making the semi-finished good with its own order first; there is no automatic explosion or MRP planning (no demand forecast, no auto-created purchase requests).
- **No routings or per-operation steps**, no machine scheduling or capacity planning, no work-in-progress stock between start and completion (components are drawn at completion).
- **Co-products / by-products** are not supported.
- **Labour is hours × a work-center rate**, not tied to attendance or payroll records.
- **Fuel from a tank needs a work center linked to equipment.** There is no per-litre allocation across several runs sharing one generator; enter the litres attributable to this run.
- **Order numbers** (`PRD-00001`) are allocated by counting existing orders; two simultaneous creations can collide and one gets a retry message.
- **No finance posting.** The cost is recorded on the order and in inventory valuation; no journal entries are created.
- **No sales orders or delivery notes yet**: finished goods are in stock but selling them is still the existing contract/progress-billing flow (next step in the plan).
- No BOM edit screen in the UI (the API supports it); no edit/deactivate for work centers in the UI.
