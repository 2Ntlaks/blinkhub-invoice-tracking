# BlinkHub Invoice & Payment Tracking (ProcureSense case study)

Prototype for the ProcureSense "BlinkHub Procurement Innovation Challenge", Path A, Option 3.

## Read first
- `docs/api-contract.md` - the API contract. Single source of truth. Change it before changing code.
- `docs/data-assumptions.md` - seed data, assumptions, and the expected numbers the app must reproduce.

## Layout and ownership
- `/backend` - FastAPI + SQLAlchemy 2 + Pydantic v2 + pytest. Backend agent only.
- `/frontend` - React + Vite + TypeScript + Tailwind + Recharts. Frontend agent only.
- `/docs`, `README.md`, `docker-compose.yml`, this file - coordinator only.
Do not edit another owner's folder.

## Non-negotiables
- Narrow and working beats wide and broken.
- Business rules live in `backend/app/rules.py` as pure functions with pytest tests.
- An unusual invoice is a **flag for review**, never an accusation. Suppliers never see flags.
- Every status change writes an insert-only audit event.
- Money is `Decimal` / `NUMERIC(14,2)` in the backend, never float arithmetic.
- `DATABASE_URL` selects the database: PostgreSQL in Docker Compose, SQLite file by default
  for local runs and tests.
- Comment non-obvious decisions; the author must be able to defend every line of business logic.
- Commit small and often with clear messages.

## Ports
Backend `http://localhost:8000` (docs at `/docs`). Frontend `http://localhost:5173`, proxies `/api` to the backend.
