# BlinkHub frontend

React 19 + Vite + TypeScript (strict) + Tailwind CSS v4 + Recharts + React Router.
It talks to the FastAPI backend only through `/api`, following [`docs/api-contract.md`](../docs/api-contract.md).

## Install and run

```bash
npm install
npm run dev            # http://localhost:5173, proxies /api to http://localhost:8000
```

The backend must be running (from `../backend`):

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

**Port 8000 busy?** Some Windows machines run a system service on port 8000,
which prevents Uvicorn from binding to it. Run the backend on another port and point the proxy at it:

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8001        # in ../backend
API_PROXY_TARGET=http://localhost:8001 npm run dev              # bash
$env:API_PROXY_TARGET="http://localhost:8001"; npm run dev      # PowerShell
```

## Quality gates

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # ESLint (typescript-eslint + react-hooks)
npm run build       # typecheck + production build into dist/
```

## Demo identity

There is no real sign-in. The **role switcher** in the header lists the users from `GET /api/users`
and every request sends the picked user's id as `X-User-Id`. The choice is remembered in
localStorage. `?as=<userId>` on any URL opens the app as that user (useful for demo bookmarks
and tests), for example `/invoices/6?as=1` (finance) or `/submit?as=10` (Sisonke Trading).

## Layout

| Path | What |
|---|---|
| `src/api/types.ts` | Contract types, mirrored exactly from the API contract |
| `src/api/client.ts` | Typed fetch client, `X-User-Id` header, error shape parsing (`ApiError`) |
| `src/components/ui.tsx` | Hand-built button, badge (stamp), card, dialog, select, input, notice |
| `src/components/invoice.tsx` | Status stamps, invoice table, audit timeline |
| `src/pages/*` | One file per screen |
| `NOTES.md` | Contract ambiguities and the frontend's choices |
