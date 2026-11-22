# Frontend notes: contract gaps and the choices made

Where the contract (`docs/api-contract.md`) was silent or ambiguous, the frontend made the
conservative choice below. Items 1 and 2 are now **resolved by the contract**; the rest are for the
coordinator to confirm.

## 1. A supplier's ACTIVE / INACTIVE status (RESOLVED by the contract)
Resolved: the contract now gives `User.supplier_status` (`ACTIVE | INACTIVE` for supplier users, `null`
otherwise; section 4, User).

Now: when the current user's `supplier_status` is `INACTIVE` (for example Sisonke Trading, user 10),
the submit page shows the "Your supplier account is inactive" notice up front
(`data-testid="supplier-inactive-notice"`) and does not render the form; "My invoices" shows a short
inactive notice and hides the "Submit an invoice" button (`btn-new-invoice`).
Fallback: if `supplier_status` is missing (older backend), the old behaviour stays: a supplier with no
POs sees the "You cannot submit an invoice right now" notice (`no-po-notice`), and a server
`422 SUPPLIER_INACTIVE` on submit still shows the inactive notice with the server message.

## 2. Open flags on a rejected or paid invoice (RESOLVED by the contract)
Resolved by contract section 3.5: "needs review" counts and lists (`GET /api/flags`, `flagged=true`,
`open_flag_count`, the dashboard KPI) only include `OPEN` flags on `SUBMITTED` / `APPROVED` invoices,
and resolving a flag on a `REJECTED` / `PAID` invoice returns `409 INVALID_STATUS_TRANSITION`.

Now: on a rejected or paid invoice the review-checks panel is labelled as history, an `OPEN` flag shows
"Not reviewed (invoice closed)" and there is no "Record review outcome" button. If a resolve still
gets the 409 (the invoice closed while the dialog was open), the dialog shows the server message and
the page refreshes.

## 3. Resolve note length
The contract says `note: string` for flag resolution. The UI requires a non-empty trimmed note;
the backend enforces min 1 character.

## 4. Port 8000 on the dev laptop
Windows `DashClientService` holds `http://+:8000/` through http.sys, so uvicorn cannot bind to
port 8000 on this machine (WinError 10013). The Vite proxy target defaults to the contract's
`http://localhost:8000` but can be overridden with `API_PROXY_TARGET` (see README). For the demo
either stop that service (as administrator) or run the backend on 8001 with the override.

## 5. Small display choices
- Money is only displayed, never computed, except two display-only sums: the queue footer total and
  the supplier's "value awaiting payment". Both are rounded to cents by the formatter.
- "Days" for a PAID invoice is shown as "paid in N d" because the contract defines it as payment
  turnaround.
- Seeded supplier user names end with "(supplier portal)"; the switcher strips that suffix because
  the option group already says "Supplier portal".
- Date "not in the future" is checked against the browser's local date; the server is the authority.
- `?as=<userId>` picks the demo user from the URL. It is demo identity only, like the switcher.
