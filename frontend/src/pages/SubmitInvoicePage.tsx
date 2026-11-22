import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError, errorMessage } from "../api/client";
import type { PurchaseOrder } from "../api/types";
import { PageTitle } from "../components/Layout";
import { Button, Card, CardHeader, ErrorState, Field, Input, Loading, Notice, Select, Textarea } from "../components/ui";
import { money, todayIso } from "../lib/format";
import { useSession } from "../lib/session";
import { useToast } from "../lib/toast";
import { useAsync } from "../lib/useAsync";

type FieldName = "po_id" | "invoice_number" | "amount" | "invoice_date" | "description";
type Errors = Partial<Record<FieldName, string>>;

interface FormState {
  po_id: string;
  invoice_number: string;
  amount: string;
  invoice_date: string;
  description: string;
}

/**
 * Client-side checks mirror the hard checks in contract 3.1 so the supplier gets
 * instant feedback. The server is still the authority and re-checks everything.
 */
function validate(f: FormState, po: PurchaseOrder | undefined): Errors {
  const e: Errors = {};
  if (!f.po_id) e.po_id = "Choose the purchase order this invoice is for.";
  const num = f.invoice_number.trim();
  if (!num) e.invoice_number = "Enter your invoice number.";
  else if (num.length > 50) e.invoice_number = "Invoice number can be at most 50 characters.";

  if (!f.amount.trim()) e.amount = "Enter the invoice amount.";
  else {
    const a = Number(f.amount);
    if (!Number.isFinite(a)) e.amount = "Enter the amount as a number, for example 85000.00.";
    else if (a <= 0) e.amount = "Amount must be greater than R0.00.";
    else if (!/^\d+(\.\d{1,2})?$/.test(f.amount.trim())) e.amount = "Use at most 2 decimals (cents).";
    else if (po && a > po.amount) e.amount = `Amount is more than the purchase order value of ${money(po.amount)}.`;
  }

  if (!f.invoice_date) e.invoice_date = "Enter the date on your invoice.";
  else if (f.invoice_date > todayIso()) e.invoice_date = "Invoice date cannot be in the future.";

  if (f.description.length > 500) e.description = "Description can be at most 500 characters.";
  return e;
}

const FIELD_FOR_CODE: Record<string, FieldName> = {
  DUPLICATE_INVOICE_NUMBER: "invoice_number",
  AMOUNT_EXCEEDS_PO: "amount",
  PO_NOT_FOUND: "po_id",
  PO_SUPPLIER_MISMATCH: "po_id",
};

const FIELDS: FieldName[] = ["po_id", "invoice_number", "amount", "invoice_date", "description"];

export function SubmitInvoicePage() {
  const { user } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const pos = useAsync(() => api.purchaseOrders(), "pos");
  // Only an explicit INACTIVE hides the form; a missing/unknown status keeps the old behaviour.
  const knownInactive = user.supplier_status === "INACTIVE";

  const [form, setForm] = useState<FormState>({ po_id: "", invoice_number: "", amount: "", invoice_date: todayIso(), description: "" });
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [inactive, setInactive] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const po = pos.data?.find((p) => String(p.id) === form.po_id);
  const supplierName = pos.data?.[0]?.supplier_name ?? user.name.replace(/\s*\(supplier portal\)\s*$/i, "");

  function set<K extends FieldName>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
    if (errors[k]) setErrors((e) => ({ ...e, [k]: undefined }));
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setFormError(null);
    const e = validate(form, po);
    setErrors(e);
    if (Object.keys(e).length > 0) return;

    setBusy(true);
    try {
      const desc = form.description.trim();
      const created = await api.createInvoice({
        po_id: Number(form.po_id),
        invoice_number: form.invoice_number.trim(),
        amount: Number(form.amount),
        invoice_date: form.invoice_date,
        ...(desc ? { description: desc } : {}),
      });
      toast.show(`Invoice ${created.invoice_number} submitted to MICS finance.`);
      navigate(`/invoices/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "SUPPLIER_INACTIVE") {
          setInactive(err.message);
        } else if (err.code === "VALIDATION_ERROR" && err.details && err.details.length > 0) {
          const fe: Errors = {};
          const unmatched: string[] = [];
          for (const d of err.details) {
            // FastAPI may report "body.amount"; keep the last path segment.
            const name = d.field.split(".").pop() as FieldName;
            if (FIELDS.includes(name)) fe[name] = d.message;
            else unmatched.push(d.message);
          }
          setErrors(fe);
          if (unmatched.length) setFormError(unmatched.join(" "));
        } else if (FIELD_FOR_CODE[err.code]) {
          const field = FIELD_FOR_CODE[err.code] as FieldName;
          setErrors({ [field]: err.message });
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageTitle kicker="Supplier portal" title="Submit an invoice" />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="rise">
          <CardHeader title={`Invoice from ${supplierName}`} subtitle="Every invoice must be linked to one of your MICS purchase orders." />
          {knownInactive ? (
            // Contract 4 (User.supplier_status): tell an inactive supplier up front, before any typing.
            <div className="px-5 py-6">
              <InactiveNotice />
            </div>
          ) : pos.loading && !pos.data ? (
            <Loading label="Loading your purchase orders" />
          ) : pos.error ? (
            <ErrorState message={pos.error} onRetry={pos.reload} />
          ) : !pos.data || pos.data.length === 0 ? (
            // Fallback when supplier_status is unknown (older backend): this message covers both
            // reasons a supplier can have no POs (see frontend/NOTES.md item 1).
            <div className="px-5 py-6" data-testid="no-po-notice">
              <Notice tone="amber" title="You cannot submit an invoice right now">
                <p>There are no MICS purchase orders on your supplier account. Every invoice must be matched to a purchase order, so there is nothing to invoice against yet.</p>
                <p className="mt-1">
                  This can also mean your supplier account is not active on the MICS supplier register. Please contact MICS procurement to check
                  your account status or to request a purchase order.
                </p>
              </Notice>
            </div>
          ) : (
            <form noValidate onSubmit={onSubmit} className="flex flex-col gap-4 px-5 py-5" data-testid="submit-form">
              {inactive && <InactiveNotice serverMessage={inactive} />}
              {formError && (
                <Notice tone="red" title="The invoice was not submitted" testId="form-error">
                  {formError}
                </Notice>
              )}

              <fieldset disabled={!!inactive || busy} className="flex flex-col gap-4 disabled:opacity-60">
                <Field label="Purchase order" htmlFor="po_id" error={errors.po_id} testId="field-po">
                  <Select id="po_id" data-testid="field-po" value={form.po_id} invalid={!!errors.po_id} onChange={(e) => set("po_id", e.target.value)}>
                    <option value="">Choose a purchase order...</option>
                    {pos.data.map((p) => (
                      <option key={p.id} value={p.id} data-testid={`po-option-${p.po_number}`}>
                        {p.po_number} · {p.category} · order {money(p.amount)} · remaining {money(p.remaining_amount)}
                      </option>
                    ))}
                  </Select>
                </Field>
                {po && (
                  <div className="-mt-2 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-rule bg-rule text-sm" data-testid="po-summary">
                    <PoCell label="Order value" value={money(po.amount)} />
                    <PoCell label="Already invoiced" value={money(po.invoiced_amount)} />
                    <PoCell label="Remaining" value={money(po.remaining_amount)} testId="po-remaining" />
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Invoice number" htmlFor="invoice_number" error={errors.invoice_number} hint="As printed on your invoice." testId="field-invoice-number">
                    <Input
                      id="invoice_number"
                      data-testid="field-invoice-number"
                      className="num"
                      maxLength={50}
                      autoComplete="off"
                      placeholder="e.g. UBC-2026-114"
                      value={form.invoice_number}
                      invalid={!!errors.invoice_number}
                      onChange={(e) => set("invoice_number", e.target.value)}
                    />
                  </Field>
                  <Field label="Amount (ZAR)" htmlFor="amount" error={errors.amount} hint={po ? `At most ${money(po.amount)} for this order.` : undefined} testId="field-amount">
                    <div className="relative">
                      <span className="num pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted">R</span>
                      <Input
                        id="amount"
                        data-testid="field-amount"
                        className="num pl-7"
                        inputMode="decimal"
                        placeholder="0.00"
                        value={form.amount}
                        invalid={!!errors.amount}
                        onChange={(e) => set("amount", e.target.value.replace(/[\s,]/g, ""))}
                      />
                    </div>
                  </Field>
                </div>

                <Field label="Invoice date" htmlFor="invoice_date" error={errors.invoice_date} testId="field-invoice-date">
                  <Input
                    id="invoice_date"
                    data-testid="field-invoice-date"
                    type="date"
                    className="num max-w-[14rem]"
                    max={todayIso()}
                    value={form.invoice_date}
                    invalid={!!errors.invoice_date}
                    onChange={(e) => set("invoice_date", e.target.value)}
                  />
                </Field>

                <Field label="Description (optional)" htmlFor="description" error={errors.description} hint={`${form.description.length}/500`} testId="field-description">
                  <Textarea
                    id="description"
                    data-testid="field-description"
                    maxLength={500}
                    placeholder="e.g. Office cleaning - November"
                    value={form.description}
                    invalid={!!errors.description}
                    onChange={(e) => set("description", e.target.value)}
                  />
                </Field>

                <div className="flex items-center gap-3 border-t border-rule pt-4">
                  <Button type="submit" busy={busy} data-testid="btn-submit-invoice">
                    Submit invoice
                  </Button>
                  <Link to="/my-invoices" className="text-sm text-muted underline">
                    Cancel
                  </Link>
                </div>
              </fieldset>
            </form>
          )}
        </Card>

        <aside className="rise flex flex-col gap-3 text-sm text-ink-2">
          <Card className="px-4 py-4">
            <h3 className="font-semibold">What happens next</h3>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5">
              <li>MICS finance checks the invoice against your purchase order.</li>
              <li>Once approved, it is scheduled for payment.</li>
              <li>You can follow every step on the invoice page.</li>
            </ol>
          </Card>
          <Card className="px-4 py-4">
            <h3 className="font-semibold">Payment terms</h3>
            <p className="mt-1">MICS aims to pay within 30 days of submission.</p>
          </Card>
        </aside>
      </div>
    </>
  );
}

/**
 * Shown when the supplier is known to be inactive: up front from User.supplier_status, or after
 * the server refuses with 422 SUPPLIER_INACTIVE (then its message is shown too).
 */
function InactiveNotice({ serverMessage }: { serverMessage?: string }) {
  return (
    <Notice tone="red" title="Your supplier account is inactive" testId="supplier-inactive-notice">
      {serverMessage && <p className="mb-1">{serverMessage}</p>}
      <p>
        Your supplier account is currently inactive on the MICS supplier register, so new invoices cannot be submitted. This is an account
        setting, not a problem with any of your invoices.
      </p>
      <p className="mt-1">
        Please contact the MICS procurement office to reactivate your account. Your existing invoices are still listed under{" "}
        <Link to="/my-invoices" className="underline">
          My invoices
        </Link>
        .
      </p>
    </Notice>
  );
}

function PoCell({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div className="bg-sheet-2 px-3 py-2" data-testid={testId}>
      <p className="text-[0.7rem] tracking-wider text-muted uppercase">{label}</p>
      <p className="num font-medium">{value}</p>
    </div>
  );
}
