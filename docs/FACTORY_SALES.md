# Factory sales (SAL)

Step 2 (with payments and COGS added in `factory-sales-payments-cogs`) of making SiteForge usable by factories. Branch `factory-sales-orders`
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

## Payments and cost of goods sold (migration `0065_sales_payments_cogs`)

- **Cost of goods sold:** with both a COGS account and an inventory account in the sales settings, every delivery posts **Dr COGS / Cr inventory** for the cost of what left stock, inside the delivery's transaction (if the posting fails, the delivery is cancelled and the stock stays). Without them nothing is posted (the cost is still recorded on the delivery line).
- **Customer payments** (`POST /v1/sal/invoices/<id>/payments`, `sal:approve`): amount, date, method (cash, transfer, cheque, card, other), reference and the bank/cash account paid into (or the default receipt account from the settings). Posts **Dr bank/cash / Cr receivable**. The invoice shows paid, balance and status (unpaid, part paid, paid); a fully paid invoice also marks its finance (AR) invoice `paid`. The invoice row is locked while paying, so two payments cannot together exceed the balance, and over-payment is refused.
- The printed invoice shows paid and balance due once something has been paid.

## Printing

In an order's **Details**, each delivery note and invoice number is a link to a print-ready page (`/sales/print/<order>/invoice|delivery/<id>`): company, client name and billing address, lines, VAT and total (invoice), or quantities and signature lines (delivery note, no prices). The app menu is hidden when printing.

## Not built (honest limits)

- **Payments are per invoice.** A customer payment is recorded against one invoice; there is no single receipt allocated across several invoices, no customer account balance or statement, and no bank-statement matching to payments.
- **No refunds or payment reversals**: a recorded payment cannot be edited or deleted from here.
- **COGS and receipts post only if the accounts are set.** Without the cost-of-goods and inventory accounts, deliveries do not post cost; without a default receipt account every payment must name one.
- **No credit notes or returns.** A delivered/invoiced order cannot be reversed from here.
- **No customer credit limits, discounts, price lists or quotations.** One price per line.
- **No stock reservation on confirm.** Stock is only checked at delivery.
- **Printing is the browser's print dialog** (Print / save as PDF), not a generated PDF file. The document shows the company *name* only (no logo, address or tax ID, which SiteForge does not store for companies yet). No emailing to the customer.
- **VAT is one rate per order**; no zero-rated or exempt lines.
- **Single currency** (NGN): the AR invoice is always posted in the default currency.
- **Order, delivery and invoice numbers** (`SO-`, `DN-`, `SI-`) are allocated by counting existing rows; two simultaneous creations can collide and one gets a retry message.
- **Editing a draft order in the UI** is not offered (the API supports it); no client or warehouse is shown beyond names.
