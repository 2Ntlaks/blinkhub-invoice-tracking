import { Link } from "react-router";
import { api } from "../api/client";
import { InvoiceTable } from "../components/invoice";
import { PageTitle } from "../components/Layout";
import { Card, CardHeader, EmptyState, ErrorState, Loading, Notice } from "../components/ui";
import { money } from "../lib/format";
import { useSession } from "../lib/session";
import { useAsync } from "../lib/useAsync";

/** Supplier portal home: the supplier's own invoices. No review flags here, ever. */
export function MyInvoicesPage() {
  const { user } = useSession();
  // Contract 4 (User.supplier_status). Unknown (missing) behaves as before: the button stays.
  const inactive = user.supplier_status === "INACTIVE";
  const q = useAsync(() => api.invoices({ sort: "submitted_desc" }), "mine");
  const open = q.data?.filter((i) => i.status === "SUBMITTED" || i.status === "APPROVED") ?? [];
  const openTotal = open.reduce((s, i) => s + i.amount, 0);

  return (
    <>
      <PageTitle
        kicker="Supplier portal"
        title="My invoices"
        right={
          inactive ? undefined : (
            <Link to="/submit" data-testid="btn-new-invoice" className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-sheet hover:bg-ink-2">
              + Submit an invoice
            </Link>
          )
        }
      />
      {inactive && (
        <div className="rise mb-4">
          <Notice tone="amber" title="Your supplier account is inactive" testId="my-invoices-inactive-notice">
            New invoices cannot be submitted while your account is inactive on the BlinkHub supplier register. Please contact the BlinkHub
            procurement office to reactivate it. You can still follow your existing invoices below.
          </Notice>
        </div>
      )}
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
            {inactive ? (
              "Invoices you submit will appear here once your account is active again."
            ) : (
              <>
                <Link to="/submit" className="underline">
                  Submit your first invoice
                </Link>{" "}
                against one of your purchase orders.
              </>
            )}
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
