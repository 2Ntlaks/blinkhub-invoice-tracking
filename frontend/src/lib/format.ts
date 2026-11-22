// Formatting helpers. Money arrives as JSON numbers (contract, top of file) and is
// only ever displayed here. The frontend does no money arithmetic beyond display.

const moneyFmt = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** R85,000.00 style. Negative values keep the sign before the R: -R85,000.00. */
export function money(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return `${n < 0 ? "-" : ""}R${moneyFmt.format(Math.abs(n))}`;
}

/** R4.03m / R955k style for dashboards; always pair with the full value in a tooltip. */
export function moneyShort(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1_000_000) return `${sign}R${(a / 1_000_000).toFixed(2)}m`;
  if (a >= 1_000) return `${sign}R${Math.round(a / 1_000)}k`;
  return `${sign}R${a.toFixed(0)}`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-22" or an ISO timestamp -> "22 Nov 2026". Date-only strings are not timezone shifted. */
export function date(s: string | null | undefined): string {
  if (!s) return "-";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (m) return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** "22 Nov 2026, 10:00" in the viewer's local time. */
export function dateTime(s: string | null | undefined): string {
  if (!s) return "-";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${date(s)}, ${hh}:${mm}`;
}

/** Today as YYYY-MM-DD in local time (the max allowed invoice date). */
export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Plain-words names for flag rules. UI wording rule: flags "need review", they never accuse. */
export const RULE_LABEL: Record<string, string> = {
  POSSIBLE_DUPLICATE: "Possible duplicate",
  PO_OVER_INVOICED: "Purchase order over-invoiced",
};

export const RULE_EXPLAIN: Record<string, string> = {
  POSSIBLE_DUPLICATE:
    "Another invoice from this supplier has the same amount within 90 days. It may be a repeat, or a legitimate recurring charge.",
  PO_OVER_INVOICED: "All invoices on this purchase order together come to more than the order value.",
};

export const ROLE_LABEL: Record<string, string> = {
  FINANCE: "Finance",
  MANAGER: "Management",
  SUPPLIER: "Supplier portal",
  SYSTEM: "System",
};

export const STATUS_LABEL: Record<string, string> = {
  SUBMITTED: "Submitted",
  APPROVED: "Approved",
  PAID: "Paid",
  REJECTED: "Rejected",
};
