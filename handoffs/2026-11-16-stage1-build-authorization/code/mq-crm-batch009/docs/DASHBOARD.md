# M&Q CRM: dashboard shell and Overview (Batch 009d, presentation only)

Black-and-gold dashboard following Josue's style reference: matte black, graphite cards,
thin gold borders, a left icon rail, a top bar, one highlighted gold KPI card and gold
area / line / bar charts. The reference was used for **style only**: no numbers, metrics
or features were copied from it.

No auth or permission change: every figure is read through `app.js` `api()` with the
signed-in session, so the existing role checks apply (viewers can read the Overview;
nothing on it writes). Charts are inline SVG built with DOM APIs; no chart library,
CDN, remote font or key.

## Where every number comes from (real CRM data only)

| Card / chart | Source | Notes |
|---|---|---|
| Payments received (gold card) | `GET /api/reports/summary` → `payments_received` | Largest currency shown; others listed under it |
| Invoiced vs. paid in full, 6 months | `GET /api/invoices` (`issued_at`, `total_minor`, `paid_at`, `paid_minor`) | One currency only; "paid in full" by the date the invoice was fully paid (partial payments are not dated per month by the API) |
| Customers (+ lapsed) | `summary.customers`, `summary.lapsed_customers` | Lapsed = no service in 90+ days |
| Upcoming bookings | `summary.upcoming_bookings` | |
| Open invoices | `summary.open_invoices` | Amount in the main currency + count |
| Open quotes | `GET /api/quotes` with status `sent` | Sent, awaiting an answer |
| Drafts awaiting approval | `GET /api/messages` with status `draft` | |
| Average rating | `summary.average_rating` | "—" when there are no reviews |
| Customers, 6 months | `GET /api/customers` → `created_at` | Running total at each month end |
| Upcoming bookings, 8 weeks | `GET /api/bookings` (`status = booked`, `starts_at_utc`) | Per week, from this Monday (UTC) |

Every card shows "—" and every chart "No data yet" when there is nothing to show.

## Not tracked (shown as "—", never estimated)

Pipeline value, revenue forecast and average deal size: the CRM has no deals, stages
or forecast data. **Decision for Josue:** which of these to build, and from what data.

## Test-data label

The top bar shows "Test data" in every build of this branch, because it only runs on
synthetic records. **Decision for Josue:** drive it from a server setting before any
real data is used.

## Languages

All dashboard text, including the dynamic lists in every tab (statuses, buttons, list
labels, empty states, notices), is in English, Español, Português and Kreyòl, and changes
with the language selector (lists re-render). PT and HT are pending native-speaker review.
Still English: error text that comes from the server, and stored codes such as a hold
reason (`promotional_content_in_transactional`).

## Follow-ups (not in this change)

- Android app (PR #2): match this styling.
- Server error messages: translate them.
