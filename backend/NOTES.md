# Backend notes: contract ambiguities and the choices made

The API contract (`docs/api-contract.md`) was not changed. Where it was silent or
ambiguous, the backend took the most conservative reading below. Each one is a
candidate for the coordinator to confirm in the contract.

| # | Topic | Contract says | Backend does | Why |
|---|---|---|---|---|
| N1 | Order of hard checks | Lists 1 fields, 2 PO exists, 3 PO owner, 4 supplier active, 5 amount, 6 duplicate | Fields, then **supplier active**, then PO exists, PO owner, amount, duplicate | Sisonke Trading has no POs, so with the listed order an inactive supplier could only ever get `PO_SUPPLIER_MISMATCH` and `SUPPLIER_INACTIVE` could not happen. An inactive supplier should get the real reason, and is told nothing about POs. |
| N2 | `PO_SUPPLIER_MISMATCH` message | Example: "PO005 belongs to Khula Electrical, not Ubuntu Cleaning." | "PO005 does not belong to Ubuntu Cleaning." | The example tells one supplier who another supplier's PO is with. Same error code, less disclosure. |
| N3 | "Within 90 days" | Not defined precisely | `abs(new.submitted_at - other.submitted_at) <= 90 days` (exactly 90 days apart is inside) | Symmetric, so the seed gives the same flags whatever order history is loaded in. |
| N4 | Several possible-duplicate matches | `related_invoice_id` is a single value | One flag per rule. It points at a PAID match first (paying twice is the costly mistake), then the closest in time; the message lists the other matches ("Also matches: ...") | One clear question per concern for the reviewer. |
| N5 | "Invoice date not in the future" | Time zone not stated | "Today" is the South African date (UTC+2, no daylight saving) | A supplier submitting just after midnight SAST is not told today's date is in the future. |
| N6 | Seeded paid invoices | Case study has no approval date or payment reference | `approved_at` and `payment_reference` stay `null`; the imported PAID audit event goes `SUBMITTED -> PAID` with a note saying the approval date was not recorded | Nothing is invented. |
| N7 | Actor of `FLAG_RAISED` | Only seeded events are specified ("System import") | Live flags use actor `{ "id": 0, "name": "Automatic check", "role": "SYSTEM" }` | The rules raised the flag, not the supplier who submitted. Suppliers never see these events anyway. |
| N8 | Flag events' `from_status` / `to_status` | Not specified | Both `null` (the invoice status does not change) | Avoids implying a status change. |
| N9 | Dashboard `open_flag_count` | "open flags" | OPEN flags on invoices that are **not REJECTED** (4 at seed) | A flag left OPEN on a rejected invoice needs no action. `GET /api/flags?status=OPEN` still lists every OPEN flag, and the invoice's own `open_flag_count` is the raw count. |
| N10 | `overdue=false`, `flagged=false` | Only `=true` is described | `true` filters; `false` or absent means no filter | Only the defined behaviour is implemented. |
| N11 | `flagged=true` from a supplier | Not specified | Ignored (returns their normal list) | Answering it would reveal which of their invoices are flagged. |
| N12 | Supplier asks for `supplier_id` of another supplier in list endpoints | Not specified | Empty list (`[]`), not 404 | Lists reveal nothing either way; 404 stays for single records. |
| N13 | `spend_by_supplier` | Not specified which suppliers appear | Suppliers with at least one PO, largest first (Sisonke has no POs, so it is absent); ties by name | Keeps the chart free of zero bars. |
| N14 | Sort tie-breaks | Only "SMMEs first on ties" for age | `age_desc`: days desc, SMME first, invoice number. `amount_desc`: amount desc, invoice number. `submitted_desc`: submitted_at desc, id desc. Rejected invoices (no age) sort last in `age_desc`. | Stable, predictable order for the UI and tests. |
| N15 | Flag resolve `note` | `note: string` | Required, 1..500 characters after trimming | The note is the evidence for the decision. |
| N16 | Other length limits | Only `invoice_number` (50) and `description` (500) given | `reason` 5..500, `payment_reference` 1..100, approve `note` up to 500 | Match the database column sizes. |
| N17 | `405` responses | Not in the error table | `405 METHOD_NOT_ALLOWED` in the standard error shape | Every non-2xx uses one shape. Unhandled errors are `500 INTERNAL_ERROR`. |
| N18 | Pydantic messages | Example "must be greater than 0" | Pydantic's own wording, e.g. "Input should be greater than 0" (rule-level checks use the contract wording) | Not worth a translation layer for a prototype. |

## Other things worth knowing

- **Port 8000 is taken on the dev laptop** by a Windows service (`RtDashService` /
  DashClientService via http.sys, PID 4 listening on `[::]:8000`). Uvicorn cannot bind it
  (`WinError 10013`). Run the backend on another port (for example `--port 8001`) and point
  the frontend's `API_PROXY_TARGET` at it, or stop that service before the demo.
- **No unique index on invoice numbers.** A number may be reused after rejection and
  partial unique indexes are not portable between SQLite and PostgreSQL, so the check is in
  `rules.find_exact_duplicate`. Two simultaneous submissions of the same number could both
  pass; acceptable for a single-user demo, fixed in production with a PostgreSQL partial
  unique index on `(supplier_id, upper(trim(invoice_number))) WHERE status <> 'REJECTED'`.
- **Stable seed ids** come from inserting rows in order into empty tables (portable, no
  PostgreSQL sequence fix-ups). The seed checks the ids and stops with a clear message if
  they are wrong; `python -m app.seed --reset` always gives a clean database.
- **Audit events are insert-only** in code: there is no update or delete path, and a
  SQLAlchemy `before_flush` guard raises `PermissionError` if anything tries.
- **Lists are computed in Python** (ages, filters, sorts) because ageing depends on "now".
  Fine for the case-study size; at scale, filter in SQL first.
