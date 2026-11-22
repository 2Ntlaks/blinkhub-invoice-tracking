import { Link } from "react-router";
import { api } from "../api/client";
import { InvoiceTable } from "../components/invoice";
import { PageTitle } from "../components/Layout";
import { Card, CardHeader, EmptyState, ErrorState, Loading } from "../components/ui";
import { money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

/** Supplier portal home: the supplier's own invoices. No review flags here, ever. */
export function MyInvoicesPage() {
  const q = useAsync(() => api.invoices({ sort: "submitted_desc" }), "mine");
  const open = q.data?.filter((i) => i.status === "SUBMITTED" || i.status === "APPROVED") ?? [];
  const openTotal = open.reduce((s, i) => s + i.amount, 0);

  return (
    <>
      <PageTitle
        kicker="Supplier portal"
        title="My invoices"
        right={
          <Link to="/submit" data-testid="btn-new-invoice" className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-sheet hover:bg-ink-2">
            + Submit an invoice
          </Link>
        }
      />
      {q.data && q.data.length > 0 && (
        <div className="rise mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Summary label="Awaiting payment" value={String(open.length)} testId="supplier-open-count" />
          <Summary label="Value awaiting payment" value={money(openTotal)} testId="supplier-open-amount" />
          <Summary label="Past 30-day terms" value={String(open.filter((i) => i.is_overdue).length)} testId="supplier-overdue-count" />
        </div>
      )}
      <Card className="rise">
        <CardHeader title="Invoice history" subtitle="Newest first. Days count from the day you submitted the invoice." />
        {q.loading && !q.data ? (
          <Loading label="Loading your invoices" />
        ) : q.error ? (
          <ErrorState message={q.error} onRetry={q.reload} />
        ) : !q.data || q.data.length === 0 ? (
          <EmptyState title="No invoices yet">
            <Link to="/submit" className="underline">
              Submit your first invoice
            </Link>{" "}
            against one of your purchase orders.
          </EmptyState>
        ) : (
          <InvoiceTable invoices={q.data} showSupplier={false} showReview={false} />
        )}
      </Card>
    </>
  );
}

function Summary({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div className="sheet px-4 py-3" data-testid={testId}>
      <p className="text-xs tracking-wider text-muted uppercase">{label}</p>
      <p className="num mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}
