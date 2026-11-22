# Frontend notes: contract gaps and the choices made

The contract (`docs/api-contract.md`) was not edited. Where it is silent or ambiguous, the
frontend made the conservative choice below. Each item is for the coordinator to confirm.

## 1. A supplier cannot see its own ACTIVE / INACTIVE status
`GET /api/suppliers` is FINANCE/MANAGER only, and `User` has no supplier status. The only signal
is `422 SUPPLIER_INACTIVE` on submit. Sisonke Trading (supplier 8, user 10) also has **no purchase
orders** in the seed, so the form can never be sent and that error never appears.

Choice: when a supplier has no POs, the submit page shows "You cannot submit an invoice right now",
explaining there is no PO to invoice against **and** that the account may not be active, with a
"contact BlinkHub procurement" instruction (`data-testid="no-po-notice"`). If `SUPPLIER_INACTIVE`
does come back from the server, a red "Your supplier account is inactive" notice shows the server
message and disables the form (`data-testid="supplier-inactive-notice"`).

Suggested contract fix (for a precise message): add `supplier_status` to `User` for supplier users
(or `GET /api/me` returning the supplier). The submit page could then show the inactive notice
before the supplier fills anything in.

## 2. Open flags on a rejected invoice
Rejecting an invoice does not resolve its flags, so a rejected invoice (for example INV008 after
rejection) keeps `OPEN` flags. They still appear on the Needs review page, in `flagged=true`
filters and in the dashboard "open flags" KPI. The UI shows whatever the API returns. The
contract could say either "reject auto-resolves open flags" or "`/api/flags?status=OPEN` and
`open_flag_count` ignore rejected invoices".

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
