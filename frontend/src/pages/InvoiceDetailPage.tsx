import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api, ApiError, errorMessage } from "../api/client";
import type { Flag, InvoiceDetail } from "../api/types";
import { DaysOutstanding, OverdueBadge, ReviewBadge, SmmeTag, StatusBadge, Timeline } from "../components/invoice";
import { Badge, Button, Card, CardHeader, Dialog, EmptyState, ErrorState, Field, Input, Loading, Notice, Textarea } from "../components/ui";
import { date, dateTime, money, RULE_EXPLAIN, RULE_LABEL } from "../lib/format";
import { useSession } from "../lib/session";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

type ActionKind = "approve" | "reject" | "pay";

export function InvoiceDetailPage() {
  const { id } = useParams();
  const invoiceId = Number(id);
  const { user } = useSession();
  const isSupplier = user.role === "SUPPLIER";
  const isFinance = user.role === "FINANCE";

  const q = useAsync(() => api.invoice(invoiceId), `invoice-${invoiceId}`);
  const [action, setAction] = useState<ActionKind | null>(null);
  const [resolving, setResolving] = useState<Flag | null>(null);

  if (!Number.isInteger(invoiceId)) {
    return (
      <Card>
        <EmptyState title="Invoice not found" />
      </Card>
    );
  }
  if (q.loading && !q.data) return <Card><Loading label="Loading invoice" /></Card>;
  if (q.error || !q.data) {
    return (
      <Card>
        <ErrorState message={q.error ?? "Invoice not found."} onRetry={q.reload} />
        <p className="px-5 pb-4 text-sm">
          <Link to="/" className="underline">
            Back to the list
          </Link>
        </p>
      </Card>
    );
  }

  const inv = q.data;
  // Suppliers never see flags. The API already returns [] for them; this is a second guard.
  const flags = isSupplier ? [] : inv.flags;
  const blocking = flags.filter((f) => f.status === "OPEN" || f.status === "CONFIRMED");
  const backTo = isSupplier ? "/my-invoices" : "/invoices";
  const closed = inv.status === "REJECTED" || inv.status === "PAID";

  return (
    <div data-testid="invoice-detail" data-invoice-number={inv.invoice_number}>
      <Link to={backTo} className="text-sm text-muted hover:text-ink" data-testid="back-link">
        ← {isSupplier ? "My invoices" : user.role === "MANAGER" ? "All invoices" : "Invoice queue"}
      </Link>

      <div className="rise mt-2 mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs tracking-[0.16em] text-margin uppercase">Invoice</p>
          <h1 className="num text-[1.9rem] leading-tight font-semibold" data-testid="invoice-number">
            {inv.invoice_number}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge status={inv.status} />
            <OverdueBadge invoice={inv} />
            {!isSupplier && <ReviewBadge count={inv.open_flag_count} />}
            {inv.is_synthetic && <Badge tone="ink">Synthetic</Badge>}
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs tracking-wider text-muted uppercase">Amount</p>
          <p className="num text-3xl font-semibold" data-testid="invoice-amount">
            {money(inv.amount)}
          </p>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card className="rise">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 px-5 py-4 text-sm sm:grid-cols-3">
              <Item label="Supplier">
                {inv.supplier.name}
                {inv.supplier.supplier_type === "SMME" && <SmmeTag />}
              </Item>
              <Item label="Purchase order">
                <span className="num">{inv.po.po_number}</span> <span className="text-muted">({money(inv.po.amount)})</span>
              </Item>
              <Item label="Invoice date">{date(inv.invoice_date)}</Item>
              <Item label="Submitted">{dateTime(inv.submitted_at)}</Item>
              <Item label={inv.status === "PAID" ? "Payment turnaround" : "Days outstanding"}>
                <DaysOutstanding invoice={inv} />
              </Item>
              {inv.approved_at && <Item label="Approved">{dateTime(inv.approved_at)}</Item>}
              {inv.paid_at && <Item label="Paid">{dateTime(inv.paid_at)}</Item>}
              {inv.payment_reference && (
                <Item label="Payment reference">
                  <span className="num" data-testid="payment-reference">
                    {inv.payment_reference}
                  </span>
                </Item>
              )}
              <div className="col-span-full">
                <Item label="Description">{inv.description || <span className="text-muted">No description</span>}</Item>
              </div>
            </dl>
            {inv.status === "REJECTED" && inv.rejection_reason && (
              <div className="px-5 pb-4">
                <Notice tone="red" title="Rejected" testId="rejection-reason">
                  {inv.rejection_reason}
                </Notice>
              </div>
            )}
          </Card>

          {!isSupplier && (
            <FlagsPanel
              flags={flags}
              // Contract 3.5: a REJECTED or PAID invoice has no payment decision left for a review
              // to inform, so its flags are history and cannot be resolved (the API returns 409).
              canResolve={isFinance && !closed}
              isHistory={closed}
              onResolve={setResolving}
            />
          )}

          <Card className="rise">
            <CardHeader title={isSupplier ? "Status timeline" : "Audit trail"} subtitle={isSupplier ? undefined : "Every change is recorded and cannot be edited or deleted."} />
            <Timeline events={inv.audit} hideFlagEvents={isSupplier} />
          </Card>
        </div>

        <aside className="flex flex-col gap-5">
          {isFinance && <ActionsPanel inv={inv} blocking={blocking} onAction={setAction} />}
          {user.role === "MANAGER" && (
            <Card className="rise px-4 py-4 text-sm text-ink-2" data-testid="readonly-note">
              <p className="font-semibold text-ink">Read-only view</p>
              <p className="mt-1">Management can see every invoice and its history. Approvals and payments are done by finance.</p>
            </Card>
          )}
          {isSupplier && <SupplierStatusNote inv={inv} />}
        </aside>
      </div>

      {isFinance && (
        <>
          <ActionDialog kind={action} inv={inv} onClose={() => setAction(null)} onDone={(d) => q.setData(d)} onFlagsChanged={q.reload} />
          <ResolveDialog flag={resolving} onClose={() => setResolving(null)} onDone={q.reload} />
        </>
      )}
    </div>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[0.7rem] tracking-wider text-muted uppercase">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function SupplierStatusNote({ inv }: { inv: InvoiceDetail }) {
  const text: Record<string, string> = {
    SUBMITTED: "BlinkHub finance has received your invoice and is checking it.",
    APPROVED: "Your invoice is approved and scheduled for payment.",
    PAID: "This invoice has been paid.",
    REJECTED: "This invoice was rejected. You can submit a corrected invoice, using the same invoice number if needed.",
  };
  return (
    <Card className="rise px-4 py-4 text-sm" data-testid="supplier-status-note">
      <p className="font-semibold">Where is my payment?</p>
      <p className="mt-1 text-ink-2">{text[inv.status]}</p>
    </Card>
  );
}

const FLAG_STATUS: Record<Flag["status"], { tone: "amber" | "green" | "red"; label: string }> = {
  OPEN: { tone: "amber", label: "Needs review" },
  CLEARED: { tone: "green", label: "Cleared" },
  CONFIRMED: { tone: "red", label: "Confirmed problem" },
};

export function FlagsPanel({
  flags,
  canResolve,
  isHistory = false,
  onResolve,
}: {
  flags: Flag[];
  canResolve: boolean;
  /** The invoice is REJECTED or PAID: show the checks as a record only (contract 3.5). */
  isHistory?: boolean;
  onResolve: (f: Flag) => void;
}) {
  const open = flags.filter((f) => f.status === "OPEN").length;
  return (
    <Card className="rise" data-testid="flags-panel">
      <CardHeader
        title="Review checks"
        subtitle={
          flags.length === 0
            ? "No checks were raised for this invoice."
            : isHistory
              ? "History: these checks were raised when the invoice was submitted. The invoice is closed, so no review outcome is needed any more."
              : "Automatic checks raised when the invoice was submitted. A check is a prompt to look closer, not an accusation."
        }
        right={open > 0 && !isHistory ? <Badge tone="amber">Needs review · {open}</Badge> : isHistory && flags.length > 0 ? <Badge tone="ink">History</Badge> : undefined}
      />
      {flags.length > 0 && (
        <ul className="divide-y divide-rule">
          {flags.map((f) => (
            <li key={f.id} className="px-5 py-4" data-testid={`flag-${f.id}`} data-rule={f.rule} data-status={f.status}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold">{RULE_LABEL[f.rule] ?? f.rule}</p>
                <Badge tone={isHistory && f.status === "OPEN" ? "ink" : FLAG_STATUS[f.status].tone} testId="flag-status">
                  {isHistory && f.status === "OPEN" ? "Not reviewed (invoice closed)" : FLAG_STATUS[f.status].label}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-ink-2">{f.message}</p>
              <p className="mt-1 text-xs text-muted">{RULE_EXPLAIN[f.rule]}</p>
              {f.related_invoice_id && (
                <p className="mt-2 text-sm">
                  Compare with{" "}
                  <Link to={`/invoices/${f.related_invoice_id}`} className="num font-semibold underline" data-testid="flag-related-link">
                    {f.related_invoice_number ?? `invoice ${f.related_invoice_id}`}
                  </Link>
                </p>
              )}
              {f.status !== "OPEN" && (
                <p className="mt-2 rounded border-l-2 border-rule-strong bg-sheet-2/70 px-2.5 py-1 text-sm text-ink-2">
                  {f.resolved_by?.name ?? "Reviewed"} · {dateTime(f.resolved_at)}
                  {f.resolution_note && <span className="italic"> · “{f.resolution_note}”</span>}
                </p>
              )}
              {canResolve && f.status === "OPEN" && (
                <div className="mt-3">
                  <Button variant="secondary" onClick={() => onResolve(f)} data-testid={`btn-resolve-flag-${f.id}`}>
                    Record review outcome
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ActionsPanel({ inv, blocking, onAction }: { inv: InvoiceDetail; blocking: Flag[]; onAction: (k: ActionKind) => void }) {
  const openCount = blocking.filter((f) => f.status === "OPEN").length;
  const confirmedCount = blocking.filter((f) => f.status === "CONFIRMED").length;
  const terminal = inv.status === "PAID" || inv.status === "REJECTED";
  return (
    <Card className="rise" data-testid="actions-panel">
      <CardHeader title="Finance actions" />
      <div className="flex flex-col gap-3 px-4 py-4">
        {terminal && <p className="text-sm text-muted">This invoice is {inv.status === "PAID" ? "paid" : "rejected"}. No further actions.</p>}

        {inv.status === "SUBMITTED" && (
          <>
            <Button variant="success" disabled={blocking.length > 0} onClick={() => onAction("approve")} data-testid="btn-approve">
              Approve for payment
            </Button>
            {blocking.length > 0 && (
              <Notice tone="amber" testId="approve-blocked">
                {openCount > 0 && (
                  <>
                    Approval is on hold until {openCount === 1 ? "the review check is" : `all ${openCount} review checks are`} recorded.{" "}
                  </>
                )}
                {confirmedCount > 0 && <>A check was confirmed as a problem, so this invoice should be rejected.</>}
              </Notice>
            )}
          </>
        )}
        {inv.status === "APPROVED" && (
          <Button variant="success" onClick={() => onAction("pay")} data-testid="btn-pay">
            Mark as paid
          </Button>
        )}
        {(inv.status === "SUBMITTED" || inv.status === "APPROVED") && (
          <Button variant="danger" onClick={() => onAction("reject")} data-testid="btn-reject">
            Reject invoice
          </Button>
        )}
      </div>
    </Card>
  );
}

const ACTION_COPY: Record<ActionKind, { title: string; field: string; label: string; required: boolean; min: number; button: string; ok: string }> = {
  approve: { title: "Approve invoice", field: "note", label: "Note (optional)", required: false, min: 0, button: "Approve", ok: "approved" },
  reject: { title: "Reject invoice", field: "reason", label: "Reason for rejection (the supplier will see this)", required: true, min: 5, button: "Reject", ok: "rejected" },
  pay: { title: "Mark invoice as paid", field: "payment_reference", label: "Payment reference", required: true, min: 1, button: "Mark paid", ok: "marked as paid" },
};

function ActionDialog({
  kind,
  inv,
  onClose,
  onDone,
  onFlagsChanged,
}: {
  kind: ActionKind | null;
  inv: InvoiceDetail;
  onClose: () => void;
  onDone: (d: InvoiceDetail) => void;
  onFlagsChanged: () => void;
}) {
  const toast = useToast();
  const [value, setValue] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const copy = kind ? ACTION_COPY[kind] : null;

  function close() {
    setValue("");
    setFieldError(null);
    setFormError(null);
    onClose();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!kind || !copy) return;
    const v = value.trim();
    if (copy.required && v.length === 0) return setFieldError(kind === "pay" ? "Enter the payment reference." : "Enter a reason.");
    if (v.length > 0 && v.length < copy.min) return setFieldError(`Please write at least ${copy.min} characters.`);
    setBusy(true);
    setFieldError(null);
    setFormError(null);
    try {
      const d = kind === "approve" ? await api.approve(inv.id, v || undefined) : kind === "reject" ? await api.reject(inv.id, v) : await api.pay(inv.id, v);
      onDone(d);
      toast.show(`${inv.invoice_number} ${copy.ok}.`);
      close();
    } catch (err) {
      if (err instanceof ApiError) {
        const fm = err.fieldMessage(copy.field) ?? err.details?.find((x) => x.field.endsWith(copy.field))?.message;
        if (fm) setFieldError(fm);
        else setFormError(err.message);
        // Someone else may have raised or resolved something: refresh behind the dialog.
        if (err.code === "FLAGS_UNRESOLVED" || err.code === "INVALID_STATUS_TRANSITION") onFlagsChanged();
      } else setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!kind} onClose={close} title={copy?.title ?? ""} testId="action-dialog">
      {copy && (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <p className="text-sm text-ink-2">
            <span className="num font-semibold">{inv.invoice_number}</span> · {inv.supplier.name} · <span className="num">{money(inv.amount)}</span>
          </p>
          {formError && (
            <Notice tone="red" testId="action-error">
              {formError}
            </Notice>
          )}
          <Field label={copy.label} htmlFor="action-value" error={fieldError ?? undefined} testId="field-action">
            {kind === "pay" ? (
              <Input id="action-value" data-testid="field-action" className="num" autoFocus value={value} invalid={!!fieldError} onChange={(e) => setValue(e.target.value)} placeholder="e.g. EFT-20261122-0042" />
            ) : (
              <Textarea id="action-value" data-testid="field-action" autoFocus value={value} invalid={!!fieldError} onChange={(e) => setValue(e.target.value)} placeholder={kind === "approve" ? "e.g. Checked against delivery note" : "e.g. Duplicate of INV001, already paid"} />
            )}
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" variant={kind === "reject" ? "danger" : "success"} busy={busy} data-testid="btn-confirm-action">
              {copy.button}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

function ResolveDialog({ flag, onClose, onDone }: { flag: Flag | null; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [outcome, setOutcome] = useState<"CLEARED" | "CONFIRMED" | null>(null);
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<{ outcome?: string; note?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);

  function close() {
    setOutcome(null);
    setNote("");
    setErrors({});
    onClose();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!flag) return;
    const n = note.trim();
    const errs: typeof errors = {};
    if (!outcome) errs.outcome = "Choose the outcome of your review.";
    if (!n) errs.note = "Write a short note explaining your decision.";
    setErrors(errs);
    if (errs.outcome || errs.note || !outcome) return;
    setBusy(true);
    try {
      await api.resolveFlag(flag.id, outcome, n);
      toast.show(outcome === "CLEARED" ? "Check cleared as legitimate." : "Check confirmed as a problem.");
      onDone();
      close();
    } catch (err) {
      if (err instanceof ApiError) {
        const fm = err.fieldMessage("note");
        setErrors(fm ? { note: fm } : { form: err.message });
        // 409 INVALID_STATUS_TRANSITION (contract 3.5): the invoice was rejected or paid meanwhile.
        // Its message is shown above; refresh behind the dialog so the buttons disappear.
        if (err.code === "FLAG_ALREADY_RESOLVED" || err.code === "INVALID_STATUS_TRANSITION") onDone();
      } else setErrors({ form: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={!!flag} onClose={close} title="Record review outcome" testId="resolve-dialog">
      {flag && (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <div className="rounded-md bg-sheet-2 px-3 py-2 text-sm">
            <p className="font-semibold">{RULE_LABEL[flag.rule] ?? flag.rule}</p>
            <p className="text-ink-2">{flag.message}</p>
          </div>
          {errors.form && <Notice tone="red">{errors.form}</Notice>}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-semibold text-ink-2">Outcome</legend>
            <OutcomeOption
              checked={outcome === "CLEARED"}
              onChange={() => setOutcome("CLEARED")}
              testId="outcome-cleared"
              title="Cleared, legitimate"
              text="I checked it and the invoice is fine (for example a recurring monthly charge)."
            />
            <OutcomeOption
              checked={outcome === "CONFIRMED"}
              onChange={() => setOutcome("CONFIRMED")}
              testId="outcome-confirmed"
              title="Confirmed problem"
              text="The concern is real. The invoice should then be rejected."
            />
            {errors.outcome && (
              <p className="text-sm font-medium text-stamp-red" role="alert" data-testid="outcome-error">
                {errors.outcome}
              </p>
            )}
          </fieldset>
          <Field label="Review note (required)" htmlFor="resolve-note" error={errors.note} testId="field-resolve-note">
            <Textarea id="resolve-note" data-testid="field-resolve-note" value={note} invalid={!!errors.note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Confirmed with supplier: November service, different month from INV001" />
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button type="submit" busy={busy} data-testid="btn-confirm-resolve">
              Save outcome
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

function OutcomeOption({ checked, onChange, title, text, testId }: { checked: boolean; onChange: () => void; title: string; text: string; testId: string }) {
  return (
    <label className={`flex cursor-pointer gap-3 rounded-md border px-3 py-2.5 text-sm ${checked ? "border-ink bg-sheet-2" : "border-rule-strong"}`}>
      <input type="radio" name="outcome" checked={checked} onChange={onChange} data-testid={testId} className="mt-1 accent-ink" />
      <span>
        <span className="block font-semibold">{title}</span>
        <span className="text-ink-2">{text}</span>
      </span>
    </label>
  );
}
