import { Link } from "react-router";
import { api } from "../api/client";
import { PageTitle } from "../components/Layout";
import { Badge, Card, CardHeader, EmptyState, ErrorState, Loading } from "../components/ui";
import { date, RULE_EXPLAIN, RULE_LABEL } from "../lib/format";
import { useSession } from "../lib/session";
import { useAsync } from "../lib/useAsync";

/** Open review checks across all invoices, grouped by invoice. Internal users only. */
export function NeedsReviewPage() {
  const { user } = useSession();
  const q = useAsync(() => api.flags("OPEN"), "flags-open");

  // Group by invoice so a finance officer reviews one invoice at a time.
  const groups = new Map<number, NonNullable<typeof q.data>>();
  for (const f of q.data ?? []) {
    const list = groups.get(f.invoice_id) ?? [];
    list.push(f);
    groups.set(f.invoice_id, list);
  }

  return (
    <>
      <PageTitle kicker={user.role === "MANAGER" ? "Management · read-only" : "Finance"} title="Needs review" />
      <Card className="rise">
        <CardHeader
          title="Open review checks"
          subtitle="Raised automatically when an invoice is submitted. Each one asks for a closer look before approval; none of them is an accusation."
          right={q.data ? <Badge tone="amber" testId="open-flag-total">{q.data.length} open</Badge> : undefined}
        />
        {q.loading && !q.data ? (
          <Loading label="Loading review checks" />
        ) : q.error ? (
          <ErrorState message={q.error} onRetry={q.reload} />
        ) : !q.data || q.data.length === 0 ? (
          <EmptyState title="Nothing needs review">All automatic checks have been reviewed.</EmptyState>
        ) : (
          <ul className="divide-y divide-rule" data-testid="review-list">
            {[...groups.entries()].map(([invoiceId, flags]) => (
              <li key={invoiceId} className="px-5 py-4" data-testid={`review-item-${flags[0]?.invoice_number}`}>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <p>
                    <Link to={`/invoices/${invoiceId}`} className="num text-lg font-semibold underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                      {flags[0]?.invoice_number}
                    </Link>
                    <span className="ml-2 text-ink-2">{flags[0]?.supplier_name}</span>
                  </p>
                  <Link to={`/invoices/${invoiceId}`} className="text-sm font-semibold text-stamp-blue underline" data-testid={`review-open-${flags[0]?.invoice_number}`}>
                    {user.role === "FINANCE" ? "Review invoice →" : "View invoice →"}
                  </Link>
                </div>
                <ul className="mt-2 flex flex-col gap-2">
                  {flags.map((f) => (
                    <li key={f.id} className="rounded-md border border-stamp-amber/30 bg-amber-wash/60 px-3 py-2 text-sm" data-testid={`review-flag-${f.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="amber">Needs review</Badge>
                        <span className="font-semibold">{RULE_LABEL[f.rule] ?? f.rule}</span>
                        <span className="ml-auto text-xs text-muted">raised {date(f.raised_at)}</span>
                      </div>
                      <p className="mt-1 text-ink-2">{f.message}</p>
                      <p className="text-xs text-muted">{RULE_EXPLAIN[f.rule]}</p>
                      {f.related_invoice_id && (
                        <p className="mt-1">
                          Compare with{" "}
                          <Link to={`/invoices/${f.related_invoice_id}`} className="num font-semibold underline">
                            {f.related_invoice_number}
                          </Link>
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
