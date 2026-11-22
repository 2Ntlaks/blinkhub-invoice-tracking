import { Link } from "react-router";
import type { AuditEvent, Invoice, InvoiceStatus } from "../api/types";
import { date, dateTime, money, ROLE_LABEL, STATUS_LABEL } from "../lib/format";
import { Badge } from "./ui";

const STATUS_TONE: Record<InvoiceStatus, "blue" | "green" | "red"> = {
  SUBMITTED: "blue",
  APPROVED: "green",
  PAID: "green",
  REJECTED: "red",
};

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]} testId="status-badge">
      {status === "PAID" && <span aria-hidden>✓</span>}
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export function OverdueBadge({ invoice, termsDays = 30 }: { invoice: Invoice; termsDays?: number }) {
  if (invoice.is_overdue) {
    return (
      <Badge tone="red" testId="overdue-badge" title={`Open for more than ${termsDays} days (payment terms)`}>
        Overdue
      </Badge>
    );
  }
  if (invoice.is_due_soon) {
    return (
      <Badge tone="amber" testId="due-soon-badge" title={`Will pass the ${termsDays}-day payment terms soon`}>
        Due soon
      </Badge>
    );
  }
  return null;
}

/** Internal-only badge. Never render for supplier users (open_flag_count is null for them anyway). */
export function ReviewBadge({ count }: { count: number | null }) {
  if (!count) return null;
  return (
    <Badge tone="amber" testId="needs-review-badge" title={`${count} check${count === 1 ? "" : "s"} waiting for a finance review`}>
      Needs review · {count}
    </Badge>
  );
}

export function SmmeTag() {
  return (
    <span data-testid="smme-tag" title="Small, medium or micro enterprise" className="ml-1.5 rounded-sm bg-series-smme/12 px-1 py-px font-mono text-[0.65rem] font-semibold tracking-wider text-[#8a3f19]">
      SMME
    </span>
  );
}

export function DaysOutstanding({ invoice }: { invoice: Invoice }) {
  if (invoice.days_outstanding === null) return <span className="text-muted">-</span>;
  const label = invoice.status === "PAID" ? "paid in" : "";
  return (
    <span className={`num ${invoice.is_overdue ? "font-semibold text-stamp-red" : ""}`} data-testid="days-outstanding">
      {label && <span className="mr-1 font-sans text-xs text-muted">{label}</span>}
      {invoice.days_outstanding}
      <span className="ml-0.5 font-sans text-xs text-muted">d</span>
    </span>
  );
}

/**
 * Invoice ledger table. `showSupplier` / `showReview` are off for the supplier portal:
 * a supplier only sees their own invoices and never sees review flags.
 */
export function InvoiceTable({ invoices, showSupplier, showReview }: { invoices: Invoice[]; showSupplier: boolean; showReview: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="ledger" data-testid="invoice-table">
        <thead>
          <tr>
            <th>Invoice</th>
            {showSupplier && <th>Supplier</th>}
            <th>PO</th>
            <th className="text-right">Amount</th>
            <th>Submitted</th>
            <th className="text-right">Days</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} data-testid={`invoice-row-${inv.invoice_number}`} className={inv.is_overdue ? "is-overdue" : ""}>
              <td>
                <Link to={`/invoices/${inv.id}`} className="num font-semibold text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
                  {inv.invoice_number}
                </Link>
                {inv.is_synthetic && <span className="ml-2 text-xs text-muted italic">synthetic</span>}
              </td>
              {showSupplier && (
                <td className="whitespace-nowrap">
                  {inv.supplier.name}
                  {inv.supplier.supplier_type === "SMME" && <SmmeTag />}
                </td>
              )}
              <td className="num text-ink-2">{inv.po.po_number}</td>
              <td className="num text-right font-medium">{money(inv.amount)}</td>
              <td className="whitespace-nowrap text-ink-2">{date(inv.submitted_at)}</td>
              <td className="text-right">
                <DaysOutstanding invoice={inv} />
              </td>
              <td>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={inv.status} />
                  <OverdueBadge invoice={inv} />
                  {showReview && <ReviewBadge count={inv.open_flag_count} />}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const ACTION_LABEL: Record<string, string> = {
  SUBMITTED: "Submitted",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  PAID: "Paid",
  FLAG_RAISED: "Review check raised",
  FLAG_CLEARED: "Review: cleared, legitimate",
  FLAG_CONFIRMED: "Review: confirmed problem",
};

const DOT: Record<string, string> = {
  SUBMITTED: "bg-stamp-blue",
  APPROVED: "bg-stamp-green",
  PAID: "bg-stamp-green",
  REJECTED: "bg-stamp-red",
  FLAG_RAISED: "bg-stamp-amber",
  FLAG_CLEARED: "bg-stamp-green",
  FLAG_CONFIRMED: "bg-stamp-red",
};

/**
 * Audit trail / status timeline, oldest first. The backend already strips FLAG_* events
 * and notes for supplier users; `hideFlagEvents` is a second guard on the client.
 */
export function Timeline({ events, hideFlagEvents }: { events: AuditEvent[]; hideFlagEvents: boolean }) {
  const shown = events.filter((e) => !(hideFlagEvents && e.action.startsWith("FLAG_")));
  const sorted = [...shown].sort((a, b) => a.at.localeCompare(b.at) || a.id - b.id);
  if (sorted.length === 0) return <p className="px-5 py-6 text-sm text-muted">No events recorded yet.</p>;
  return (
    <ol className="relative px-5 py-4" data-testid="audit-timeline">
      {sorted.map((e, i) => (
        <li key={e.id} data-testid={`audit-event-${e.action}`} className="relative flex gap-4 pb-5 last:pb-0">
          {i < sorted.length - 1 && <span aria-hidden className="absolute top-4 left-[5px] h-full w-px bg-rule-strong" />}
          <span aria-hidden className={`relative mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full ring-2 ring-sheet ${DOT[e.action] ?? "bg-muted"}`} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
              <span className="font-semibold">{ACTION_LABEL[e.action] ?? e.action}</span>
              {e.from_status && e.to_status && e.from_status !== e.to_status && (
                <span className="num text-xs text-muted">
                  {e.from_status} → {e.to_status}
                </span>
              )}
              <span className="ml-auto text-xs whitespace-nowrap text-muted">{dateTime(e.at)}</span>
            </div>
            <p className="text-sm text-ink-2">
              {e.actor.name}
              <span className="text-muted"> · {ROLE_LABEL[e.actor.role] ?? e.actor.role}</span>
            </p>
            {e.note && <p className="mt-1 rounded border-l-2 border-rule-strong bg-sheet-2/70 px-2.5 py-1 text-sm text-ink-2 italic">“{e.note}”</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
