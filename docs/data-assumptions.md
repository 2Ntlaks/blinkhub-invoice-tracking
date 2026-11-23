# Seed data and assumptions

All data comes from the case study's sample tables (section 6). Where the case study is
silent, the choice below is an **assumption**, documented explicitly here.

## 1. What the case study gives us
- 8 suppliers, 12 purchase orders, 8 invoices.
- Invoices have supplier, amount, "days outstanding" and status (`Paid` / `Outstanding`).
- Invoices have **no PO reference, no invoice date, no payment date**.

## 2. Assumptions

| # | Gap | Assumption | Why |
|---|---|---|---|
| A1 | Invoices have no PO reference | Each invoice is linked to the PO of the **same supplier with exactly the same amount**. Result: INV001->PO001, INV002->PO003, INV003->PO004, INV004->PO005, INV005->PO006, INV006->PO001, INV007->PO002, INV008->PO003. | Deterministic and explainable. It also means INV006 and INV008 land on POs that are already fully invoiced, which the system then flags. |
| A2 | "Outstanding" is not one of our statuses | `Outstanding` -> `SUBMITTED` (awaiting finance review). | Nothing in the data says they were approved. |
| A3 | No dates for open invoices | `submitted_at = invoice_date = seed time - days outstanding`. Days keep growing after seeding, as in real life. Re-seed with `python -m app.seed --reset` to match the case study numbers exactly. | Keeps the case study's ageing visible on the dashboard. |
| A4 | For paid invoices, "days outstanding" | Read as **payment turnaround** (submission to payment). Submission dates are assumed: INV001 80 days ago, INV004 70 days ago, INV007 60 days ago; `paid_at = submitted_at + days`. | Needed to compute turnaround. INV001 is placed before INV006 so the duplicate check can see it. |
| A5 | Payment terms | 30 days from submission (`PAYMENT_TERMS_DAYS`). | The case study asks about "invoices exceeding 30 days". |
| A6 | "Spend" | Committed PO value (total R4,027,000). | Matches the case study's "listed procurement spend". |
| A7 | Provinces | Gauteng=GP, Limpopo=LP, KwaZulu-Natal=KZN, Mpumalanga=MP. | Short codes. |
| A8 | Users | Fictional demo users: one finance officer, one manager, one supplier login per supplier. | No real auth in scope. |

## 3. Expected findings after seeding (used as acceptance tests)
- Total spend R4,027,000; SMME spend R657,000 = **16.3%**.
- Outstanding: 5 invoices, R955,000. **All 5 are overdue** (> 30 days). Worst: INV003, Metro Logistics, R620,000, 65 days.
- Average payment turnaround (paid invoices): (15 + 12 + 8) / 3 = **11.7 days**.
- Flags (4, all OPEN):
  - INV006: `POSSIBLE_DUPLICATE` (same amount as INV001, already paid) and `PO_OVER_INVOICED` (PO001).
  - INV008: `POSSIBLE_DUPLICATE` (same amount as INV002, same day) and `PO_OVER_INVOICED` (PO003).
- Sisonke Trading is `INACTIVE`, so its user cannot submit invoices.

## 4. Notable details in the sample data
- The case study's "75 days unpaid cleaning company" does not appear in the invoice table
  (the oldest Ubuntu Cleaning invoice is 47 days). We treat it as the motivating story,
  not a data point.
- INV006 is Ubuntu Cleaning's only open invoice and it is flagged. A flag must not quietly
  freeze payment to a struggling SMME, so every overdue or flagged invoice appears on the
  finance attention list (oldest first, SMMEs first on ties), and approval is blocked only
  until a finance officer reviews the flag.

## 5. Synthetic data
None yet. Any synthetic record added later must have `is_synthetic = true` and be shown
as "synthetic" in the UI. Synthetic records must never be presented as MICS performance.
