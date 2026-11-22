# BlinkHub Invoice & Payment Tracking - API Contract (v1)

This file is the single source of truth between `/backend` and `/frontend`.
If either side needs a change, change this file first, then the code.

- Base URL: `/api` (Vite dev server proxies `/api` to `http://localhost:8000`)
- Format: JSON. Dates `YYYY-MM-DD`, timestamps ISO 8601 UTC (`2026-11-22T10:00:00Z`).
- Money: JSON numbers in South African rand (ZAR), max 2 decimals (e.g. `85000.0`).
  Stored as `NUMERIC(14,2)` in the database, never as float.
- IDs: integers.

---

## 1. Identity and roles (demo auth)

Real authentication is out of scope. The frontend has a **role switcher** that picks
one of the seeded users and sends that user's id on every request:

```
X-User-Id: 3
```

| Situation | Response |
|---|---|
| Header missing or not an integer | `401 UNAUTHENTICATED` |
| User id does not exist | `401 UNAUTHENTICATED` |
| User exists but role not allowed for this endpoint | `403 FORBIDDEN` |
| Supplier user asks for another supplier's data | `404 NOT_FOUND` (do not reveal it exists) |

Roles:

| Role | Can do |
|---|---|
| `SUPPLIER` | Submit invoices for **their own** supplier, see their own POs and invoices, see status timeline. **Never sees flags** (a flag is a risk indicator for internal review, not something to show or accuse a supplier with). |
| `FINANCE` | See all invoices, approve, reject, mark paid, review flags. |
| `MANAGER` | Read-only access to everything, plus the dashboard. |

Dashboard is available to `FINANCE` and `MANAGER`.

---

## 2. Error format

Every non-2xx response uses one shape:

```json
{
  "error": {
    "code": "PO_SUPPLIER_MISMATCH",
    "message": "PO005 belongs to Khula Electrical, not Ubuntu Cleaning.",
    "details": null
  }
}
```

Pydantic validation errors are mapped to `422` with `code: "VALIDATION_ERROR"` and
`details: [{ "field": "amount", "message": "must be greater than 0" }]`.

Error codes used:

| HTTP | code | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | see section 1 |
| 403 | `FORBIDDEN` | role not allowed |
| 404 | `NOT_FOUND` | resource missing or not visible to this user |
| 422 | `VALIDATION_ERROR` | bad field values |
| 422 | `PO_NOT_FOUND` | `po_id` does not exist |
| 422 | `PO_SUPPLIER_MISMATCH` | PO belongs to another supplier |
| 422 | `SUPPLIER_INACTIVE` | supplier status is `INACTIVE` |
| 422 | `AMOUNT_EXCEEDS_PO` | single invoice amount > PO amount |
| 409 | `DUPLICATE_INVOICE_NUMBER` | same supplier already has a non-rejected invoice with this number |
| 409 | `INVALID_STATUS_TRANSITION` | e.g. paying a `SUBMITTED` invoice |
| 409 | `FLAGS_UNRESOLVED` | approving while a flag is `OPEN` or `CONFIRMED` |
| 409 | `FLAG_ALREADY_RESOLVED` | resolving a flag that is not `OPEN` |

---

## 3. Business rules (the heart of the system)

All rules live in one backend module (`app/rules.py`) as pure functions so they can be
unit tested without a database.

### 3.1 Hard checks on submit (invoice is NOT created)
1. `amount > 0`, `invoice_number` non-empty after trimming, `invoice_date` not in the future.
2. PO must exist (`PO_NOT_FOUND`).
3. PO must belong to the submitting supplier (`PO_SUPPLIER_MISMATCH`).
4. Supplier must be `ACTIVE` (`SUPPLIER_INACTIVE`).
5. Invoice amount must not exceed the PO amount (`AMOUNT_EXCEEDS_PO`).
6. **Exact duplicate**: same supplier + same invoice number (compared trimmed, upper-case)
   where the existing invoice is not `REJECTED` -> `409 DUPLICATE_INVOICE_NUMBER`.
   A supplier may resubmit a number after its earlier invoice was rejected.

### 3.2 Soft checks on submit (invoice IS created, a flag is raised for review)
Flags are risk indicators, never accusations. Approval is blocked until a finance
officer reviews each flag.

| Rule | Condition |
|---|---|
| `POSSIBLE_DUPLICATE` | Same supplier + same amount as another non-rejected invoice submitted within 90 days. Message says whether the other invoice is already paid. |
| `PO_OVER_INVOICED` | Sum of all non-rejected invoices on this PO (including this one) > PO amount. |

### 3.3 Status lifecycle

```
SUBMITTED --approve--> APPROVED --pay--> PAID
    \--reject--> REJECTED (terminal)
```
- `approve`: only from `SUBMITTED`, only if no flag on the invoice is `OPEN` or `CONFIRMED`.
- `reject`: only from `SUBMITTED` or `APPROVED`; `reason` required (min 5 chars).
- `pay`: only from `APPROVED`; `payment_reference` required.
- Every transition and every flag raise/resolve writes an **audit event** (who, when, from, to, note).
  Audit events are insert-only; there is no update or delete endpoint.

### 3.4 Ageing and overdue (computed, not stored)
- `days_outstanding`:
  - `SUBMITTED` / `APPROVED`: whole days from `submitted_at` to now.
  - `PAID`: whole days from `submitted_at` to `paid_at` (that is the payment turnaround).
  - `REJECTED`: `null`.
- `is_overdue`: status is `SUBMITTED` or `APPROVED` and `days_outstanding > 30`.
- `is_due_soon`: status is `SUBMITTED` or `APPROVED` and `21 <= days_outstanding <= 30`.
- `ageing_bucket` (open invoices only, else `null`): `"0-30"`, `"31-60"`, `"61-90"`, `"90+"`.
- The 30-day threshold is a config constant (`PAYMENT_TERMS_DAYS = 30`).

### 3.5 Which flags count as open review work
A flag needs attention only while its invoice can still be paid. Everywhere the system counts or lists
"needs review" work, it uses flags with status `OPEN` on invoices whose status is `SUBMITTED` or `APPROVED`:
`GET /api/flags`, the `flagged=true` filter, `open_flag_count` on invoices, and the dashboard `open_flag_count`.
Rejecting an invoice does not change its flags (a rejection is not a finding about the flag); they stay
visible as history in the invoice detail but drop out of the review queue and counts.

---

## 4. Resources

### User
```json
{ "id": 1, "name": "Thandi Nkosi", "role": "FINANCE", "supplier_id": null, "supplier_status": null }
```
`supplier_status` is the linked supplier's `ACTIVE | INACTIVE` for SUPPLIER users, `null` otherwise.
The UI uses it to explain up front that an inactive supplier cannot submit (the API still enforces
`SUPPLIER_INACTIVE` on submit).

### Supplier
```json
{
  "id": 1, "name": "Ubuntu Cleaning", "province": "GP",
  "supplier_type": "SMME", "bbbee_level": 1, "status": "ACTIVE", "is_synthetic": false
}
```
`province`: `GP | LP | KZN | MP`. `supplier_type`: `SMME | LARGE`. `status`: `ACTIVE | INACTIVE`.

### PurchaseOrder
```json
{
  "id": 1, "po_number": "PO001", "supplier_id": 1, "supplier_name": "Ubuntu Cleaning",
  "category": "Cleaning", "department": "Facilities", "amount": 85000.0,
  "invoiced_amount": 170000.0, "remaining_amount": -85000.0, "is_synthetic": false
}
```
`invoiced_amount` = sum of non-rejected invoices on the PO. `remaining_amount` may be negative (over-invoiced).

### Invoice (list item)
```json
{
  "id": 6, "invoice_number": "INV006",
  "supplier": { "id": 1, "name": "Ubuntu Cleaning", "supplier_type": "SMME" },
  "po": { "id": 1, "po_number": "PO001", "amount": 85000.0 },
  "amount": 85000.0, "invoice_date": "2026-10-06", "submitted_at": "2026-10-06T08:00:00Z",
  "status": "SUBMITTED",
  "days_outstanding": 47, "is_overdue": true, "is_due_soon": false, "ageing_bucket": "31-60",
  "open_flag_count": 2,
  "approved_at": null, "paid_at": null, "payment_reference": null, "rejection_reason": null,
  "is_synthetic": false
}
```
For `SUPPLIER` users `open_flag_count` is always `null`.

### Invoice (detail) = list item plus
```json
{
  "description": "Office cleaning - October",
  "flags": [ Flag, ... ],
  "audit": [ AuditEvent, ... ]
}
```
For `SUPPLIER` users: `flags` is `[]`, and audit events of type `FLAG_*` are omitted;
`note` is `null` on all events except `REJECTED` (the rejection reason is the supplier's to see).

### Flag
```json
{
  "id": 2, "invoice_id": 6, "invoice_number": "INV006", "supplier_name": "Ubuntu Cleaning",
  "rule": "POSSIBLE_DUPLICATE",
  "message": "Same supplier and amount (R85,000.00) as INV001, which is already PAID.",
  "related_invoice_id": 1, "related_invoice_number": "INV001",
  "status": "OPEN", "raised_at": "2026-10-06T08:00:00Z",
  "resolved_at": null, "resolved_by": null, "resolution_note": null
}
```
`status`: `OPEN | CLEARED | CONFIRMED`. `CLEARED` = reviewed, legitimate. `CONFIRMED` = reviewed, real problem (invoice should then be rejected).
`resolved_by`: `{ "id": 3, "name": "Thandi Nkosi" }` or `null`.

### AuditEvent
```json
{
  "id": 10, "at": "2026-11-22T10:00:00Z",
  "actor": { "id": 3, "name": "Thandi Nkosi", "role": "FINANCE" },
  "action": "APPROVED",
  "from_status": "SUBMITTED", "to_status": "APPROVED", "note": "Checked against delivery note"
}
```
`action`: `SUBMITTED | APPROVED | REJECTED | PAID | FLAG_RAISED | FLAG_CLEARED | FLAG_CONFIRMED`.
Seeded legacy events use actor `{ "id": 0, "name": "System import", "role": "SYSTEM" }`.

---

## 5. Endpoints

| Method | Path | Roles | Body | Returns |
|---|---|---|---|---|
| GET | `/api/health` | none | - | `{ "status": "ok" }` |
| GET | `/api/users` | none (demo switcher) | - | `User[]` |
| GET | `/api/me` | any | - | `User` |
| GET | `/api/suppliers` | FINANCE, MANAGER | - | `Supplier[]` |
| GET | `/api/purchase-orders` | all (SUPPLIER: own only) | query `supplier_id?` | `PurchaseOrder[]` |
| GET | `/api/invoices` | all (SUPPLIER: own only) | query below | `Invoice[]` |
| POST | `/api/invoices` | SUPPLIER | `InvoiceCreate` | `201` Invoice detail |
| GET | `/api/invoices/{id}` | all (SUPPLIER: own only) | - | Invoice detail |
| POST | `/api/invoices/{id}/approve` | FINANCE | `{ "note": string? }` | Invoice detail |
| POST | `/api/invoices/{id}/reject` | FINANCE | `{ "reason": string }` | Invoice detail |
| POST | `/api/invoices/{id}/pay` | FINANCE | `{ "payment_reference": string }` | Invoice detail |
| GET | `/api/flags` | FINANCE, MANAGER | query `status?` | `Flag[]` |
| POST | `/api/flags/{id}/resolve` | FINANCE | `{ "outcome": "CLEARED"\|"CONFIRMED", "note": string }` | Flag |
| GET | `/api/dashboard` | FINANCE, MANAGER | - | `Dashboard` |

`GET /api/invoices` query params (all optional, combinable):
`status` (one of the four), `supplier_id`, `overdue=true`, `flagged=true` (has an OPEN flag),
`sort` = `age_desc` (default) | `amount_desc` | `submitted_desc`.

### InvoiceCreate
```json
{
  "invoice_number": "UBC-2026-114",
  "po_id": 8,
  "amount": 95000.0,
  "invoice_date": "2026-11-20",
  "description": "Office cleaning - November"
}
```
`supplier_id` is **not** in the body: it comes from the logged-in supplier user.
`description` optional, max 500 chars. `invoice_number` max 50 chars.

### Dashboard
```json
{
  "as_of": "2026-11-22T10:00:00Z",
  "payment_terms_days": 30,
  "kpis": {
    "outstanding_count": 5, "outstanding_amount": 955000.0,
    "overdue_count": 5, "overdue_amount": 955000.0,
    "due_soon_count": 0,
    "avg_payment_turnaround_days": 11.7,
    "open_flag_count": 4,
    "smme_spend_share_pct": 16.3
  },
  "ageing": [
    { "bucket": "0-30", "count": 0, "amount": 0.0 },
    { "bucket": "31-60", "count": 4, "amount": 335000.0 },
    { "bucket": "61-90", "count": 1, "amount": 620000.0 },
    { "bucket": "90+", "count": 0, "amount": 0.0 }
  ],
  "spend_by_supplier": [
    { "supplier_id": 7, "name": "Apex Infrastructure", "supplier_type": "LARGE", "amount": 1200000.0 }
  ],
  "spend_by_department": [ { "department": "Operations", "amount": 1900000.0 } ],
  "smme_share": { "smme_amount": 657000.0, "total_amount": 4027000.0, "pct": 16.3 },
  "attention": [ Invoice, ... ]
}
```
- **Spend** = committed purchase order value (sum of `PurchaseOrder.amount`), matching the
  case study's "listed procurement spend" of R4,027,000.
- `attention` = open invoices that are overdue **or** have an open flag, sorted by
  `days_outstanding` desc, SMMEs first on ties (SMME cash flow is the brief's key story).
- `avg_payment_turnaround_days` = mean `days_outstanding` over `PAID` invoices.

---

## 6. Running, config and seed data

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./blinkhub.db` | Any SQLAlchemy URL. Docker Compose sets a PostgreSQL URL. |
| `SEED_ON_STARTUP` | `true` | On startup, if the database has no suppliers, create tables and load the case-study seed. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated. |

- Reset to the exact case-study state: `python -m app.seed --reset` (from `backend/`). This drops and
  recreates all tables, then seeds. Run it right before the demo so "days outstanding" match the brief.
- The seed must create flags by running the **same rule functions** used by `POST /api/invoices`,
  in invoice-number order. Flags are never hard-coded in the seed.
- E2E tests start the backend with a throwaway SQLite file (`DATABASE_URL=sqlite:///./e2e.db`) and reset it first.

### Seeded users (ids are stable, the frontend role switcher lists them from `GET /api/users`)

| id | name | role | supplier |
|---|---|---|---|
| 1 | Thandi Nkosi | FINANCE | - |
| 2 | Sipho Mokoena | MANAGER | - |
| 3..10 | "`<Supplier name>` (supplier portal)" | SUPPLIER | suppliers 1..8 in case-study order (Ubuntu Cleaning = supplier 1, user 3; Sisonke Trading = supplier 8, user 10) |

Supplier ids follow the case-study register order: 1 Ubuntu Cleaning, 2 Prime Facilities, 3 Thuto Supplies,
4 Metro Logistics, 5 Khula Electrical, 6 Rapid Transport, 7 Apex Infrastructure, 8 Sisonke Trading.
PO ids 1..12 = PO001..PO012. Invoice ids 1..8 = INV001..INV008.

### UI wording rule
Flags are shown as **"Needs review"** with the rule name in plain words. Never use the words
"fraud", "suspicious" or "fraudulent" anywhere in the UI or API messages.
