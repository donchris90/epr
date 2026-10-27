# Factory sales (SAL)

Step 2 of making SiteForge usable by factories. Branch `factory-sales-orders`
(built on `factory-manufacturing`). Migration `0064_sales_orders`.

## What it does

- **Sales orders** (`/v1/sal/sales-orders`) for a BDC client, shipping from one warehouse. Lines default their price from the item's new **selling price** (set on the inventory item form), or take a typed price. VAT (default 7.5%) is calculated per order and the rate is **snapshotted**, so changing the VAT setting later does not rewrite old orders. A draft can be edited; confirmed orders cannot.
- **Delivery notes** (`POST .../deliveries`): partial deliveries are supported. Delivering takes the stock out of the warehouse (tenant's FIFO or weighted-average valuation) and records the **cost of the goods sold** on the delivery line. All-or-nothing: if any item is short, nothing leaves stock and no note is created. Cannot over-deliver a line.
- **Invoices** (`POST .../invoice`): invoices everything delivered and not yet invoiced, so partial deliveries invoice in steps and nothing is invoiced twice. It posts to the ledger through FIN's AR posting: **Dr receivable (gross), Cr revenue (net), Cr output VAT**. The AR invoice is created in the same transaction, with the due date from the payment terms.
- **Accounting settings** (`/v1/sal/settings`): which company, receivable, revenue and VAT accounts to post to, VAT rate and payment terms. Invoicing is refused until this is set.
- Each order shows delivered value, cost of goods delivered and **gross margin**.
- FIN's `post_accounts_receivable_invoice` gained optional VAT support and a `commit` flag (existing callers are unchanged).

Permissions: `sal:read`, `sal:write` (orders, deliveries), `sal:approve` (invoicing, settings).

UI: **Sales** in the Supply Chain menu → Sales orders / Invoices / Accounting settings.

## Printing

In an order's **Details**, each delivery note and invoice number is a link to a print-ready page (`/sales/print/<order>/invoice|delivery/<id>`): company, client name and billing address, lines, VAT and total (invoice), or quantities and signature lines (delivery note, no prices). The app menu is hidden when printing.

## Not built (honest limits)

- **No cost-of-goods-sold posting.** Delivery records the cost on the delivery line, but no journal entry moves it from inventory to COGS. Only the sales invoice posts (receivable, revenue, VAT).
- **No payments or receipts.** Invoices are created `unpaid` in FIN; recording a customer payment against them is not part of this step.
- **No credit notes or returns.** A delivered/invoiced order cannot be reversed from here.
- **No customer credit limits, discounts, price lists or quotations.** One price per line.
- **No stock reservation on confirm.** Stock is only checked at delivery.
- **Printing is the browser's print dialog** (Print / save as PDF), not a generated PDF file. The document shows the company *name* only (no logo, address or tax ID, which SiteForge does not store for companies yet). No emailing to the customer.
- **VAT is one rate per order**; no zero-rated or exempt lines.
- **Single currency** (NGN): the AR invoice is always posted in the default currency.
- **Order, delivery and invoice numbers** (`SO-`, `DN-`, `SI-`) are allocated by counting existing rows; two simultaneous creations can collide and one gets a retry message.
- **Editing a draft order in the UI** is not offered (the API supports it); no client or warehouse is shown beyond names.
