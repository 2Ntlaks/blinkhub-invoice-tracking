# BlinkHub backend

FastAPI + SQLAlchemy 2 + Pydantic v2. The API contract is `../docs/api-contract.md`;
choices where the contract was silent are in [NOTES.md](NOTES.md).

Where things live:

- `app/rules.py` - every business rule, as pure functions (start here)
- `app/services.py` - loads facts, calls the rules, writes the outcome and the audit trail
- `app/routers/` - thin HTTP endpoints; `app/auth.py` - `X-User-Id` demo identity and role guards
- `app/seed.py` - case-study data, loaded through the same submit path as real invoices
- `tests/test_rules.py` (rule unit tests), `tests/test_api.py` (full-stack tests)

## Setup (once)

Git Bash:

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Run

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000      # Git Bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000      # PowerShell
```

API docs: `http://localhost:8000/docs`. On first start the database (`blinkhub.db`) is
created and seeded automatically.

If port 8000 is taken (on the dev laptop a Windows service holds it), use `--port 8001`
and start the frontend with `API_PROXY_TARGET=http://localhost:8001`.

## Reset to the exact case-study state (do this right before the demo)

```bash
.venv/Scripts/python -m app.seed --reset      # Git Bash
.venv\Scripts\python -m app.seed --reset      # PowerShell
```

Stop the server first: SQLite cannot drop tables another process is using. Invoice ages
are counted from seed time, so a fresh reset shows the case study's 65 / 47 / 42 / 38 days.

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `sqlite:///./blinkhub.db` (PostgreSQL: `postgresql+psycopg://user:pass@host/db`) |
| `SEED_ON_STARTUP` | `true` |
| `CORS_ORIGINS` | `http://localhost:5173` (comma-separated) |

Git Bash: `DATABASE_URL=sqlite:///./e2e.db .venv/Scripts/python -m app.seed --reset`
PowerShell: `$env:DATABASE_URL = "sqlite:///./e2e.db"; .venv\Scripts\python -m app.seed --reset`

## Test and lint

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
```

(PowerShell: the same commands with `.venv\Scripts\...`.) Each API test gets its own
freshly seeded SQLite file and a frozen clock (22 Nov 2026 10:00 UTC), so the dashboard
numbers are checked exactly: spend R4,027,000, SMME 16.3%, 5 outstanding / R955,000, all
overdue, turnaround 11.7 days, 4 open flags, INV003 first on the attention list.
