# Architecture

Technical companion to [`system-overview.md`](system-overview.md). The API contract in
[`api-contract.md`](api-contract.md) is the source of truth for every endpoint and payload;
this page explains how the pieces fit and why they were built this way.

## 1. System at a glance

```mermaid
flowchart LR
    subgraph Browser
        UI["React + TypeScript UI<br/>role switcher · invoice queue · dashboard"]
    end
    subgraph Backend["FastAPI backend (Python 3.12)"]
        AUTH["auth.py<br/>X-User-Id → user + role guard"]
        API["routers<br/>thin HTTP layer"]
        RULES["rules.py<br/>pure business rules<br/>(no DB, no HTTP)"]
        ORM["SQLAlchemy 2 models"]
    end
    DB[("SQLite (local)<br/>or PostgreSQL (Docker)")]

    UI -- "JSON over HTTP /api/*" --> AUTH --> API
    API -- "facts in, decision out" --> RULES
    API --> ORM --> DB
```

- The **frontend** never decides anything that matters. It hides buttons a role cannot use, but the
  backend re-checks every permission and rule on every request.
- The **routers** load data, call a rule, and save the result. They contain no business logic.
- **`rules.py`** holds every business rule as a pure function: it receives plain values (amounts,
  dates, statuses, lists of other invoices) and returns a decision. That is why the rules can be unit
  tested in milliseconds without a database, and why each one can be read and defended on its own.
- `DATABASE_URL` picks the database. The same code runs on SQLite for zero-setup local use and tests,
  and on PostgreSQL in Docker Compose.

## 2. Database (ERD)

```mermaid
erDiagram
    SUPPLIER ||--o{ PURCHASE_ORDER : "is issued"
    SUPPLIER ||--o{ INVOICE : submits
    SUPPLIER |o--o{ USER : "portal login for"
    PURCHASE_ORDER ||--o{ INVOICE : "is billed by"
    INVOICE ||--o{ FLAG : "may raise"
    INVOICE ||--o{ AUDIT_EVENT : "history of"
    INVOICE |o--o{ FLAG : "related to"
    USER ||--o{ AUDIT_EVENT : "acted in"
    USER |o--o{ FLAG : resolves

    SUPPLIER {
        int id PK
        string name
        string province "GP | LP | KZN | MP"
        string supplier_type "SMME | LARGE"
        int bbbee_level
        string status "ACTIVE | INACTIVE"
        bool is_synthetic
    }
    PURCHASE_ORDER {
        int id PK
        string po_number UK "PO001"
        int supplier_id FK
        string category
        string department
        numeric amount "NUMERIC(14,2)"
        bool is_synthetic
    }
    INVOICE {
        int id PK
        string invoice_number "unique per supplier unless REJECTED"
        int supplier_id FK
        int po_id FK
        numeric amount "NUMERIC(14,2)"
        date invoice_date
        datetime submitted_at
        string status "SUBMITTED | APPROVED | REJECTED | PAID"
        datetime approved_at
        datetime paid_at
        string payment_reference
        string rejection_reason
        string description
        bool is_synthetic
    }
    FLAG {
        int id PK
        int invoice_id FK
        string rule "POSSIBLE_DUPLICATE | PO_OVER_INVOICED"
        string message
        int related_invoice_id FK
        string status "OPEN | CLEARED | CONFIRMED"
        datetime raised_at
        int resolved_by_id FK
        datetime resolved_at
        string resolution_note
    }
    AUDIT_EVENT {
        int id PK
        int invoice_id FK
        int actor_user_id FK "null when system_actor is set"
        string system_actor "System import | Automatic check"
        string action
        string from_status
        string to_status
        string note
        datetime at
    }
    USER {
        int id PK
        string name
        string role "SUPPLIER | FINANCE | MANAGER"
        int supplier_id FK "only for SUPPLIER"
    }
```

Not stored on purpose: **days outstanding, overdue, ageing bucket, PO invoiced amount, dashboard totals**.
They are calculated from the rows above at request time, so they can never go stale or disagree with
the underlying invoices.

## 3. An invoice's lifecycle

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: supplier submits\n(hard checks pass, soft flags raised)
    SUBMITTED --> APPROVED: finance approves\n(only when no OPEN/CONFIRMED flag)
    SUBMITTED --> REJECTED: finance rejects\n(reason required)
    APPROVED --> REJECTED: finance rejects\n(reason required)
    APPROVED --> PAID: finance pays\n(payment reference required)
    REJECTED --> [*]
    PAID --> [*]
```

## 4. What happens when a supplier submits an invoice

```mermaid
sequenceDiagram
    actor S as Supplier
    participant API as FastAPI
    participant R as rules.py
    participant DB as Database
    S->>API: POST /api/invoices (X-User-Id)
    API->>API: role = SUPPLIER? supplier taken from the user, not the body
    API->>DB: load PO, supplier, this supplier's invoices
    API->>R: hard checks (PO exists, same supplier, active, amount ≤ PO, number unused)
    alt a hard check fails
        R-->>API: error code
        API-->>S: 409 / 422 with the contract error shape (nothing saved)
    else all pass
        API->>R: soft checks (possible duplicate, PO over-invoiced)
        R-->>API: flags to raise
        API->>DB: insert invoice + flags + audit events in ONE transaction
        API-->>S: 201 invoice (flags stripped for suppliers)
    end
```

## 5. Key engineering decisions

| Decision | Why | Trade-off |
|---|---|---|
| **Money as `Decimal` / `NUMERIC(14,2)`** | Floats cannot represent most cents exactly (0.1 + 0.2 ≠ 0.3). Finance totals must reconcile to the cent. | JSON still carries numbers, so the API converts at the edge. |
| **Business rules as pure functions in one module** | One place to read, test and defend every rule. Tests run without a database. Seeding uses the same functions, so seeded flags are produced by the real rules, not typed in. | Routers must gather the facts a rule needs before calling it. |
| **Insert-only audit trail** | Accountability: who did what, when and why. There is no update or delete path in the code, so history cannot be quietly rewritten. | A production system would also enforce this in the database (revoked UPDATE/DELETE rights or triggers). |
| **Flags, not verdicts** | The brief treats an unusual invoice as a risk indicator, not an accusation. Flags block approval until a person reviews them, and suppliers never see them. | A human must review every flag; with real volumes this needs a triage queue and SLAs. |
| **Hard blocks vs soft flags** | Clear-cut problems (wrong PO, inactive supplier, reused number) are refused at the door. Judgement calls (same amount twice) are accepted but held for review, so a legitimate invoice is never lost. | Thresholds such as the 90-day duplicate window are configurable guesses until real data is available. |
| **Derived values computed, not stored** | Overdue status changes every day by itself; storing it would need a scheduled job and could drift. | Slightly more work per request; trivial at this scale. |
| **Demo role switcher (`X-User-Id`)** | Real authentication is out of scope for a one-day prototype, but role checks are real and enforced server side. | Anyone can pick any user. Next step: OIDC/Azure AD login, same role guards. |
| **SQLite locally, PostgreSQL in Compose** | A reviewer can run it with Python and Node only. Portable SQLAlchemy types keep both paths identical. | SQLite is not used in production; Compose is the production-like path. |

## 6. Verification layers

| Layer | Tool | What it proves |
|---|---|---|
| Static checks | `ruff` (backend), `tsc --noEmit` + `eslint` (frontend) | Code style and type errors caught before running. |
| Rule unit tests | `pytest` on `rules.py` | Each business rule and its edge cases (30 vs 31 days, one cent over the PO, resubmit after rejection). |
| API + access tests | `pytest` + FastAPI `TestClient` | Error codes, role guards, suppliers never see flags, inactive supplier blocked, dashboard reproduces the case-study numbers exactly. |
| End-to-end | Playwright | The live-demo journeys work in a real browser against the real backend. |
| Independent review | A second agent | Code checked against `api-contract.md` and `data-assumptions.md` by a reviewer that did not write it. |

`scripts/verify.sh` runs the static checks and test layers in one command.
