# BlinkHub End-to-End Verification Report

This report records independent browser verification of the BlinkHub Invoice and Payment Tracking prototype. An independent verification agent executed the suite without modifying any application code under `backend/` or `frontend/`.

## Run metadata

| Field | Value |
|---|---|
| **Result** | **5 / 5 journeys PASSED** |
| **Recorded at (UTC)** | `2026-11-23T06:58:15.848Z` |
| **Git commit verified** | `4cc1b9c61a5638ce0bc94ac7349c776f8af42a7d` (`4cc1b9c`; `backend/` and `frontend/` unchanged from `main` at `f06df79`) |
| **Browser and viewport** | Real Chromium (Playwright 1.57.0), `1366x768` |
| **Backend and database** | Real FastAPI (`uvicorn` on port `8011`) backed by a freshly seeded SQLite database (`e2e.db`, reset with `app.seed --reset` immediately before the run) |
| **Frontend** | Real React 19 + Vite dev server (port `5183`, proxying `/api` to port `8011`) |
| **Playback pacing** | Actions were slowed by Playwright `slowMo` (400 ms per action) so a viewer can follow each click; nothing was edited afterwards. |
| **Structured results** | [`results.json`](results.json) |

## Evidence integrity (raw, unedited recordings)

Every recording in this folder is unedited:

- **Raw recordings (`raw/*.webm`):** Exact byte-for-byte copies of the `.webm` videos captured directly by Playwright for each test. No compilation, no title cards, no burned-in captions or overlays, no trimming, no cuts, and no post-capture speed changes.
- **MP4 conversions (`*.mp4`):** Straight H.264 format conversions (`ffmpeg -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart`, zero video filters). Each MP4 is a lossless-intent re-encode of the untouched WEBM with the exact same length and frame count, provided so the recordings play on every platform.
- **Inline previews (`*.gif`):** Each GIF shown below is a **preview GIF converted from the raw recording** (full length, no cuts, no text added; scaled to 960 px wide at 8 fps for inline Markdown display).

### Raw `.webm` SHA-256 checksums

Verify that the raw Playwright recordings have not been altered:

| Journey | Raw file | Size | Frames / Duration | SHA-256 |
|---|---|---|---|---|
| 01 | [`raw/01-manager-dashboard.webm`](raw/01-manager-dashboard.webm) | 357 KB | 90 frames (3.60 s) | `f963f53636d5b5ff10f1014e39f5a80cb3d29c6ad0b08b9dc435a70534cad527` |
| 02 | [`raw/02-supplier-submit.webm`](raw/02-supplier-submit.webm) | 734 KB | 199 frames (7.96 s) | `8ff78e84e4923e35dc54ac44d475cfb4974d8424ce246c27630eab8015df7341` |
| 03 | [`raw/03-inactive-supplier.webm`](raw/03-inactive-supplier.webm) | 200 KB | 63 frames (2.52 s) | `f5437b0e6459146606fcf8b5dc9a6855569fd0dbf22d894b2df4d13fb5957e1e` |
| 04 | [`raw/04-finance-review-approve-pay.webm`](raw/04-finance-review-approve-pay.webm) | 1,147 KB | 242 frames (9.68 s) | `a8c1b38eb0fb24bc82cc988fbb12f192585af651a0f4ef77230d87a3f65a8b80` |
| 05 | [`raw/05-finance-reject.webm`](raw/05-finance-reject.webm) | 723 KB | 160 frames (6.40 s) | `8084e038c255fef2f1aea2d46f620a4c736a28366db196f20c10b3c9a1976352` |

To check these locally from the repository root:

```bash
sha256sum docs/verification/raw/*.webm
```

---

## Results summary

The five journeys run sequentially in a single Playwright worker against one freshly seeded database so state changes from earlier journeys (such as clearing `INV006` and rejecting `INV008`) carry forward naturally into the final dashboard check.

| # | Journey | Spec file | Status | Test duration | Raw WEBM | Straight MP4 |
|---|---|---|---|---:|---|---|
| 01 | Manager dashboard and read-only view | `01-manager-dashboard.spec.ts` | **PASSED** | 3.36 s | [`raw/01-manager-dashboard.webm`](raw/01-manager-dashboard.webm) | [`01-manager-dashboard.mp4`](01-manager-dashboard.mp4) |
| 02 | Supplier submits invoice and duplicate number is refused | `02-supplier-submit.spec.ts` | **PASSED** | 7.84 s | [`raw/02-supplier-submit.webm`](raw/02-supplier-submit.webm) | [`02-supplier-submit.mp4`](02-supplier-submit.mp4) |
| 03 | Inactive supplier is told it cannot submit | `02-supplier-submit.spec.ts` | **PASSED** | 2.22 s | [`raw/03-inactive-supplier.webm`](raw/03-inactive-supplier.webm) | [`03-inactive-supplier.mp4`](03-inactive-supplier.mp4) |
| 04 | Finance reviews INV006 flags, approves, and pays | `03-finance-review-approve-pay.spec.ts` | **PASSED** | 9.29 s | [`raw/04-finance-review-approve-pay.webm`](raw/04-finance-review-approve-pay.webm) | [`04-finance-review-approve-pay.mp4`](04-finance-review-approve-pay.mp4) |
| 05 | Finance rejects INV008 with supplier-visible reason | `04-finance-reject.spec.ts` | **PASSED** | 6.00 s | [`raw/05-finance-reject.webm`](raw/05-finance-reject.webm) | [`05-finance-reject.mp4`](05-finance-reject.mp4) |

---

## Journey-by-journey evidence

### 01. Manager dashboard and read-only view

- **What this proves:** On the untouched case-study seed, the management dashboard (`Sipho Mokoena`) displays the exact expected figures: `5` outstanding invoices, `5` overdue invoices, `R955k` overdue value, `11.7` days average payment turnaround, `4` open review checks, and `16.3%` SMME share of committed spend, with `INV003` (Metro Logistics, 65 days) heading the attention list. When the manager opens flagged invoice `INV006`, the review panel is visible for oversight, while all approve, reject, pay, and flag-resolution actions are absent (strictly read-only).
- **Status:** PASSED (3.36 s)
- **Original recordings:** [Raw WEBM (`raw/01-manager-dashboard.webm`)](raw/01-manager-dashboard.webm) | [Straight MP4 (`01-manager-dashboard.mp4`)](01-manager-dashboard.mp4)

![Preview GIF converted from the raw recording for journey 01: manager dashboard and read-only view](01-manager-dashboard.gif)
*Preview GIF converted from the raw recording (`raw/01-manager-dashboard.webm`, full length, no cuts, no text added).*

---

### 02. Supplier submits invoice and duplicate number is refused

- **What this proves:** An active supplier (`Ubuntu Cleaning`) submits a new invoice (`UBC-E2E-001`, `R40,000`) against its own purchase order (`PO008`), lands on the saved invoice in `SUBMITTED` status, and sees no internal review flags or review wording. When the supplier attempts to submit the same invoice number again with different casing and surrounding whitespace (`  ubc-e2e-001 `), the hard block refuses it and keeps the user on the form without creating a second record.
- **Status:** PASSED (7.84 s)
- **Original recordings:** [Raw WEBM (`raw/02-supplier-submit.webm`)](raw/02-supplier-submit.webm) | [Straight MP4 (`02-supplier-submit.mp4`)](02-supplier-submit.mp4)

![Preview GIF converted from the raw recording for journey 02: supplier submits invoice and duplicate number is refused](02-supplier-submit.gif)
*Preview GIF converted from the raw recording (`raw/02-supplier-submit.webm`, full length, no cuts, no text added).*

---

### 03. Inactive supplier is told it cannot submit

- **What this proves:** When an inactive supplier (`Sisonke Trading`) opens the invoice submission screen, the portal immediately displays a clear explanation that the supplier account is inactive on the MICS register and hides the submit action up front (matching the backend's `422 SUPPLIER_INACTIVE` guard).
- **Status:** PASSED (2.22 s)
- **Original recordings:** [Raw WEBM (`raw/03-inactive-supplier.webm`)](raw/03-inactive-supplier.webm) | [Straight MP4 (`03-inactive-supplier.mp4`)](03-inactive-supplier.mp4)

![Preview GIF converted from the raw recording for journey 03: inactive supplier is told it cannot submit](03-inactive-supplier.gif)
*Preview GIF converted from the raw recording (`raw/03-inactive-supplier.webm`, full length, no cuts, no text added).*

---

### 04. Finance reviews INV006 flags, approves, and pays

- **What this proves:** On `INV006` (Ubuntu Cleaning, `R85,000`), approval is held while its two automatic review checks (`Possible duplicate` and `Purchase order over-invoiced`) remain open. Finance officer `Thandi Nkosi` clears both checks with a written explanation, which unlocks approval. She then approves the invoice and marks it paid with payment reference `EFT-E2E-0006`. The insert-only audit trail records two `FLAG_CLEARED` events, `APPROVED`, and `PAID`. Switching to the supplier view (`Ubuntu Cleaning`) shows `PAID` status with zero internal flags and zero flag-clearance events exposed.
- **Status:** PASSED (9.29 s)
- **Original recordings:** [Raw WEBM (`raw/04-finance-review-approve-pay.webm`)](raw/04-finance-review-approve-pay.webm) | [Straight MP4 (`04-finance-review-approve-pay.mp4`)](04-finance-review-approve-pay.mp4)

![Preview GIF converted from the raw recording for journey 04: finance reviews INV006 flags, approves, and pays](04-finance-review-approve-pay.gif)
*Preview GIF converted from the raw recording (`raw/04-finance-review-approve-pay.webm`, full length, no cuts, no text added).*

---

### 05. Finance rejects INV008 with supplier-visible reason

- **What this proves:** On `INV008` (Thuto Supplies, `R35,000`), finance officer `Thandi Nkosi` is blocked from rejecting with a too-short reason (`dup`) and then rejects the invoice with a clear written reason referencing `INV002` and `PO003`. Switching to `Thuto Supplies` confirms the supplier sees `REJECTED` status and the full written reason so it can act on it, while internal review checks remain hidden. Returning to management's dashboard confirms open review work has dropped to `0` (two checks cleared on `INV006`, and `INV008`'s two checks closed as history upon rejection).
- **Status:** PASSED (6.00 s)
- **Original recordings:** [Raw WEBM (`raw/05-finance-reject.webm`)](raw/05-finance-reject.webm) | [Straight MP4 (`05-finance-reject.mp4`)](05-finance-reject.mp4)

![Preview GIF converted from the raw recording for journey 05: finance rejects INV008 with supplier-visible reason](05-finance-reject.gif)
*Preview GIF converted from the raw recording (`raw/05-finance-reject.webm`, full length, no cuts, no text added).*

---

## How to reproduce

Prerequisites: Python 3.12 with `backend/.venv` (`requirements-dev.txt`), Node 20+ with `npm ci` in `frontend/` and `e2e/`, Playwright Chromium installed (`cd e2e && npx playwright install chromium`), and `ffmpeg` on `PATH`.

```bash
# Re-run all 5 journeys with raw video capture, MP4/GIF conversion, and results.json
scripts/record-evidence.sh

# Run the full verification stack (ruff, pytest, tsc, eslint, vite build, Playwright E2E)
scripts/verify.sh
```

The repository also runs automated checks (backend lint/format/tests, frontend typecheck/lint/build, and Playwright E2E with `E2E_VIDEO=1` uploading `test-results` and `playwright-report` artifacts) on every pull request and push to `main` via [`.github/workflows/verify.yml`](../../.github/workflows/verify.yml).

## Limits of this verification

These recordings prove that the five scripted end-to-end workflows pass against the real FastAPI backend, seeded SQLite database, and React frontend in Chromium. They do **not** prove:

- **Load, scale, or concurrency:** Tests run one worker at a time against a local SQLite database, not concurrent finance officers and suppliers against PostgreSQL under production load.
- **Security against active attackers:** Role enforcement is tested via the prototype's `X-User-Id` demo switcher rather than production identity (OIDC / Azure AD), penetration testing, or fuzzing.
- **Usability with real users:** Automated scripts confirm selectors, flows, and copy rules, not whether real MICS staff or SMME suppliers find the screens intuitive without guidance.
- **External integrations:** Email/SMS notifications, document uploads, and bank payment feeds are outside the prototype scope and therefore not verified here.
