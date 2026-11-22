import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { InvoiceQuery, InvoiceStatus } from "../api/types";
import { InvoiceTable } from "../components/invoice";
import { PageTitle } from "../components/Layout";
import { Button, Card, EmptyState, ErrorState, Loading, Select } from "../components/ui";
import { money } from "../lib/format";
import { useSession } from "../lib/session";
import { useAsync } from "../lib/useAsync";

const STATUSES: InvoiceStatus[] = ["SUBMITTED", "APPROVED", "PAID", "REJECTED"];
const SORTS: { value: NonNullable<InvoiceQuery["sort"]>; label: string }[] = [
  { value: "age_desc", label: "Oldest first" },
  { value: "amount_desc", label: "Largest amount" },
  { value: "submitted_desc", label: "Newest submitted" },
];

/** Finance queue (manager sees it read-only). Filters live in the URL so a view can be shared. */
export function InvoiceQueuePage() {
  const { user } = useSession();
  const [sp, setSp] = useSearchParams();
  const statusParam = sp.get("status");
  const status = STATUSES.includes(statusParam as InvoiceStatus) ? (statusParam as InvoiceStatus) : undefined;
  const overdue = sp.get("overdue") === "true";
  const flagged = sp.get("flagged") === "true";
  const sortParam = sp.get("sort");
  const sort = SORTS.some((s) => s.value === sortParam) ? (sortParam as InvoiceQuery["sort"]) : "age_desc";

  const query: InvoiceQuery = { status, overdue, flagged, sort };
  const q = useAsync(() => api.invoices(query), JSON.stringify(query));

  function update(key: string, value: string | null) {
    const next = new URLSearchParams(sp);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setSp(next, { replace: true });
  }

  const anyFilter = !!status || overdue || flagged;
  const total = q.data?.reduce((s, i) => s + i.amount, 0) ?? 0;

  return (
    <>
      <PageTitle kicker={user.role === "MANAGER" ? "Management · read-only" : "Finance"} title={user.role === "MANAGER" ? "All invoices" : "Invoice queue"} />

      <Card className="rise">
        <div className="flex flex-wrap items-end gap-4 border-b border-rule px-5 py-3.5" data-testid="queue-filters">
          <label className="flex flex-col gap-1 text-xs font-semibold tracking-wider text-muted uppercase">
            Status
            <Select data-testid="filter-status" value={status ?? ""} onChange={(e) => update("status", e.target.value)} className="min-w-[10rem] py-1.5 text-sm normal-case">
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0) + s.slice(1).toLowerCase()}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold tracking-wider text-muted uppercase">
            Sort
            <Select data-testid="filter-sort" value={sort} onChange={(e) => update("sort", e.target.value === "age_desc" ? null : e.target.value)} className="min-w-[10rem] py-1.5 text-sm normal-case">
              {SORTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </Select>
          </label>
          <Toggle label="Overdue only" checked={overdue} onChange={(v) => update("overdue", v ? "true" : null)} testId="filter-overdue" />
          <Toggle label="Needs review only" checked={flagged} onChange={(v) => update("flagged", v ? "true" : null)} testId="filter-flagged" />
          {anyFilter && (
            <Button variant="ghost" onClick={() => setSp(new URLSearchParams(), { replace: true })} data-testid="filter-clear" className="py-1.5">
              Clear filters
            </Button>
          )}
          {q.data && (
            <p className="ml-auto text-sm text-muted" data-testid="queue-summary">
              <span className="num font-semibold text-ink">{q.data.length}</span> invoice{q.data.length === 1 ? "" : "s"} ·{" "}
              <span className="num font-semibold text-ink">{money(total)}</span>
            </p>
          )}
        </div>

        {q.loading && !q.data ? (
          <Loading label="Loading invoices" />
        ) : q.error ? (
          <ErrorState message={q.error} onRetry={q.reload} />
        ) : !q.data || q.data.length === 0 ? (
          <EmptyState title={anyFilter ? "No invoices match these filters" : "No invoices yet"}>{anyFilter && "Try clearing a filter."}</EmptyState>
        ) : (
          <div className={q.loading ? "opacity-60 transition-opacity" : ""}>
            <InvoiceTable invoices={q.data} showSupplier showReview />
          </div>
        )}
      </Card>
      <p className="mt-3 text-xs text-muted">
        A red edge marks invoices open for more than 30 days. &ldquo;Needs review&rdquo; means an automatic check asks finance to take a closer look before approving.
      </p>
    </>
  );
}

function Toggle({ label, checked, onChange, testId }: { label: string; checked: boolean; onChange: (v: boolean) => void; testId: string }) {
  return (
    <label className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium select-none ${checked ? "border-ink bg-ink text-sheet" : "border-rule-strong bg-white/60 text-ink"}`}>
      <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid={testId} />
      <span aria-hidden className={`inline-block h-3 w-3 rounded-sm border ${checked ? "border-sheet bg-sheet" : "border-ink-2"}`} />
      {label}
    </label>
  );
}
