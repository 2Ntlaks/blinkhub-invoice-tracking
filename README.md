# BlinkHub Invoice & Payment Tracking

A working prototype for the ProcureSense **BlinkHub Procurement Innovation Challenge**
(Path A: full-stack, Option 3: Invoice and Payment Tracking).

MICS, the case study's fictional client, loses track of supplier invoices in email and spreadsheets.
One local cleaning company waited 75 days to be paid. This app gives every invoice one visible path:

**Supplier submits → automatic checks → finance reviews → approved → paid** (or rejected with a reason),
with every step recorded in an audit trail that cannot be edited, and a live dashboard for management.

- Clear-cut problems (wrong PO, inactive supplier, reused invoice number, amount above the PO) are **refused**.
- Judgement calls (same amount twice, a PO billed beyond its value) are accepted but marked **Needs review**,
  and cannot be approved until a finance officer clears or confirms them. A flag is a question, not an accusation,
  so suppliers never see flags.
- Loaded with the case study's sample data, it surfaces: R4,027,000 listed spend (16.3% to SMMEs),
  5 open invoices worth R955,000 all overdue, INV003 waiting 65 days, and 4 review flags on INV006 and INV008.

| Read this | If you want |
|---|---|
| [`docs/system-overview.md`](docs/system-overview.md) | the problem, roles, rules and findings in plain language |
| [`docs/architecture.md`](docs/architecture.md) | architecture diagram, database ERD, key engineering decisions |
| [`docs/api-contract.md`](docs/api-contract.md) | every endpoint, payload, error code and business rule |
| [`docs/data-assumptions.md`](docs/data-assumptions.md) | how gaps in the sample data were filled, and the expected numbers |

## Run it locally (no Docker needed)

Requires **Python 3.12** and **Node 20+**. Commands are for Git Bash; PowerShell variants are in
[`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md).

```bash
# 1. Backend (terminal 1): creates and seeds a local SQLite database on first start
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 2. Frontend (terminal 2)
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**, pick a user in the role switcher (top right), and try:

1. **Ubuntu Cleaning (supplier portal):** submit an invoice against PO008; track its status.
2. **Thandi Nkosi (Finance):** open INV006, see why it needs review, clear or confirm the flags, then approve and pay.
3. **Sipho Mokoena (Management):** read-only dashboard: ageing, spend by supplier, SMME share, attention list.
4. **Sisonke Trading (supplier portal):** an inactive supplier; submitting is refused with an explanation.

API documentation (Swagger UI) is at **http://localhost:8000/docs**.

**Port 8000 already in use?** (some Windows machines run a service on it) Start the backend with
`--port 8001` and the frontend with `API_PROXY_TARGET=http://localhost:8001 npm run dev`.

**Reset to the exact case-study state** (invoice ages count from seed time; stop the backend first):
`cd backend && .venv/Scripts/python -m app.seed --reset`

## Run it with Docker (PostgreSQL)

```bash
docker compose up --build
```

Open **http://localhost:8080**. This runs PostgreSQL, the FastAPI backend, and the built frontend behind nginx,
seeded with the same data. Settings are documented in [`.env.example`](.env.example).

## Verify everything

```bash
cd e2e && npm ci && npx playwright install chromium && cd ..   # once, for the browser tests
scripts/verify.sh            # lint, types, rule tests, API tests, frontend build, browser journeys
scripts/verify.sh --fast     # everything except the browser journeys
```

| Layer | What it checks |
|---|---|
| `ruff` | backend lint and formatting |
| `pytest backend/tests/test_rules.py` | every business rule and its edge cases, without a database |
| `pytest backend/tests/test_api.py` | every error code, role permissions, suppliers never see flags, inactive supplier blocked, dashboard reproduces the case-study numbers exactly |
| `tsc` + `eslint` + `vite build` | frontend types, lint and production build |
| Playwright (`e2e/`) | the demo journeys in a real browser against the real backend |

## Project layout

```
backend/    FastAPI app: rules.py (business rules), services, routers, seed, tests
frontend/   React + TypeScript UI: role switcher, supplier portal, finance queue, dashboard
e2e/        Playwright browser journeys
docs/       contract, assumptions, overview, architecture
docker/     Dockerfiles and nginx config used by docker-compose.yml
scripts/    verify.sh
```

## Limitations and next steps

This is a prototype. Not built yet: real login (the role switcher stands in for it), invoice and delivery-note
uploads, email/SMS reminders, payment-system integration, separation of duties (approver cannot also pay),
cloud deployment, and further Problem 6 checks (payments just below approval thresholds, bank detail changes
before payment). See [`docs/system-overview.md`](docs/system-overview.md#7-what-it-does-not-do-yet-and-what-comes-next).

## How it was built

Built with AI coding agents working against a shared API contract (`docs/api-contract.md`): one agent for the
backend, one for the frontend, and a separate agent reviewing the code independently. Every business rule
lives in `backend/app/rules.py` with a plain-English explanation of why it exists.
