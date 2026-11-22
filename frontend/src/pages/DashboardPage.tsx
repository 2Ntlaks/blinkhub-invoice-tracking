import type { ReactNode } from "react";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { DaysOutstanding, OverdueBadge, ReviewBadge, SmmeTag, StatusBadge } from "../components/invoice";
import { PageTitle } from "../components/Layout";
import { Card, CardHeader, EmptyState, ErrorState, Loading } from "../components/ui";
import { dateTime, money, moneyShort } from "../lib/format";
import { useAsync } from "../lib/useAsync";

// Chart colours: validated for colour-blind separation against the sheet surface.
const SMME = "#b5582a";
const LARGE = "#3a63a8";
const INK = "#4a514b";
const MUTED = "#6f6a5c";
const GRID = "#e4dccb";
// Ageing: one hue, light to dark as invoices get older (sequential = magnitude of lateness).
const AGEING_FILL: Record<string, string> = { "0-30": "#7f9acb", "31-60": "#6b8cc4", "61-90": "#3a63a8", "90+": "#1f3f78" };

export function DashboardPage() {
  const q = useAsync(() => api.dashboard(), "dashboard");

  if (q.loading && !q.data) {
    return (
      <>
        <PageTitle kicker="BlinkHub finance" title="Payments dashboard" />
        <Card>
          <Loading label="Adding up the ledger" />
        </Card>
      </>
    );
  }
  if (q.error || !q.data) {
    return (
      <>
        <PageTitle kicker="BlinkHub finance" title="Payments dashboard" />
        <Card>
          <ErrorState message={q.error ?? "No data."} onRetry={q.reload} />
        </Card>
      </>
    );
  }
  const d = q.data;
  const k = d.kpis;

  return (
    <div data-testid="dashboard">
      <PageTitle
        kicker="BlinkHub finance"
        title="Payments dashboard"
        right={
          <p className="text-sm text-muted" data-testid="dashboard-as-of">
            As of <span className="num text-ink">{dateTime(d.as_of)}</span> · payment terms {d.payment_terms_days} days
          </p>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Kpi testId="kpi-outstanding-count" label="Outstanding invoices" value={String(k.outstanding_count)} sub="awaiting payment" />
        <Kpi testId="kpi-outstanding-amount" label="Outstanding value" value={moneyShort(k.outstanding_amount)} full={money(k.outstanding_amount)} />
        <Kpi testId="kpi-overdue-count" label="Overdue invoices" value={String(k.overdue_count)} sub={`over ${d.payment_terms_days} days`} alert={k.overdue_count > 0} />
        <Kpi testId="kpi-overdue-amount" label="Overdue value" value={moneyShort(k.overdue_amount)} full={money(k.overdue_amount)} alert={k.overdue_amount > 0} />
        <Kpi
          testId="kpi-avg-turnaround"
          label="Avg turnaround"
          value={k.avg_payment_turnaround_days === null ? "-" : k.avg_payment_turnaround_days.toFixed(1)}
          unit="days"
          sub="submission to payment"
        />
        <Kpi testId="kpi-open-flags" label="Needs review" value={String(k.open_flag_count)} sub="open checks" amber={k.open_flag_count > 0} to="/review" />
        <Kpi testId="kpi-smme-share" label="SMME share of spend" value={k.smme_spend_share_pct.toFixed(1)} unit="%" sub={`${moneyShort(d.smme_share.smme_amount)} of ${moneyShort(d.smme_share.total_amount)}`} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <AttentionList d={d} />
        <Card className="rise">
          <CardHeader title="Ageing of open invoices" subtitle="Value by days since submission. Bars past 30 days are overdue." />
          <AgeingChart d={d} />
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="rise">
          <CardHeader
            title="Spend by supplier"
            subtitle="Committed purchase order value."
            right={
              <div className="flex gap-3 text-xs text-ink-2" data-testid="supplier-legend">
                <Legend color={SMME} label="SMME" />
                <Legend color={LARGE} label="Large" />
              </div>
            }
          />
          <SupplierChart d={d} />
        </Card>
        <div className="flex flex-col gap-5">
          <Card className="rise">
            <CardHeader title="SMME share" subtitle="Share of committed spend going to small, medium and micro enterprises." />
            <SmmeShare d={d} />
          </Card>
          <Card className="rise">
            <CardHeader title="Spend by department" subtitle="Committed purchase order value." />
            <DepartmentChart d={d} />
          </Card>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  unit,
  sub,
  full,
  alert,
  amber,
  testId,
  to,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  full?: string;
  alert?: boolean;
  amber?: boolean;
  testId: string;
  to?: string;
}) {
  const accent = alert ? "border-t-stamp-red" : amber ? "border-t-stamp-amber" : "border-t-ink";
  const body = (
    <>
      <p className="text-[0.68rem] leading-tight font-semibold tracking-wider text-muted uppercase">{label}</p>
      <p className={`num mt-1.5 text-[1.55rem] leading-none font-semibold ${alert ? "text-stamp-red" : amber ? "text-stamp-amber" : "text-ink"}`} data-testid={`${testId}-value`}>
        {value}
        {unit && <span className="ml-1 font-sans text-sm font-medium text-muted">{unit}</span>}
      </p>
      {full ? <p className="num mt-1 truncate text-[0.72rem] text-muted">{full}</p> : sub ? <p className="mt-1 truncate text-[0.75rem] text-muted">{sub}</p> : null}
    </>
  );
  const cls = `sheet rise block border-t-4 px-3.5 py-3 ${accent}`;
  return to ? (
    <Link to={to} className={`${cls} transition-transform hover:-translate-y-0.5`} data-testid={testId} title={full}>
      {body}
    </Link>
  ) : (
    <div className={cls} data-testid={testId} title={full}>
      {body}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}

/** Tooltip in our own markup: text stays ink, the swatch carries identity. */
function Tip({ active, payload, render }: { active?: boolean; payload?: { payload: unknown }[]; render: (p: never) => ReactNode }) {
  if (!active || !payload?.[0]) return null;
  return <div className="rounded-md border border-rule-strong bg-sheet px-3 py-2 text-sm shadow-md">{render(payload[0].payload as never)}</div>;
}

const AXIS = { fill: MUTED, fontSize: 12, fontFamily: "Instrument Sans" };
const AXIS_MONO = { fill: MUTED, fontSize: 11, fontFamily: "JetBrains Mono" };

function AgeingChart({ d }: { d: Dashboard }) {
  const empty = d.ageing.every((a) => a.count === 0);
  if (empty) return <EmptyState title="No open invoices">Everything has been paid or rejected.</EmptyState>;
  return (
    <div className="h-64 px-2 pt-4 pb-2" data-testid="chart-ageing">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={d.ageing} margin={{ top: 22, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="bucket" tick={AXIS} tickLine={false} axisLine={{ stroke: "#c7baa0" }} tickFormatter={(b: string) => `${b} d`} />
          <YAxis tick={AXIS_MONO} tickLine={false} axisLine={false} tickFormatter={(v: number) => moneyShort(v)} width={56} />
          <Tooltip
            cursor={{ fill: "rgb(31 42 36 / 0.05)" }}
            content={
              <Tip
                render={(p: { bucket: string; count: number; amount: number }) => (
                  <>
                    <p className="font-semibold">{p.bucket} days</p>
                    <p className="num">{money(p.amount)}</p>
                    <p className="text-muted">
                      {p.count} invoice{p.count === 1 ? "" : "s"}
                    </p>
                  </>
                )}
              />
            }
          />
          <Bar dataKey="amount" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
            {d.ageing.map((a) => (
              <Cell key={a.bucket} fill={AGEING_FILL[a.bucket] ?? LARGE} />
            ))}
            <LabelList dataKey="count" position="top" formatter={(c: number) => (c ? `${c} inv` : "")} style={{ fill: INK, fontSize: 12, fontFamily: "Instrument Sans" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SupplierChart({ d }: { d: Dashboard }) {
  if (d.spend_by_supplier.length === 0) return <EmptyState title="No purchase orders yet" />;
  const data = [...d.spend_by_supplier].sort((a, b) => b.amount - a.amount);
  return (
    <div className="px-2 pt-3 pb-2" style={{ height: Math.max(220, data.length * 34 + 30) }} data-testid="chart-spend-supplier">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, left: 8, bottom: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" tick={AXIS_MONO} tickLine={false} axisLine={false} tickFormatter={(v: number) => moneyShort(v)} />
          <YAxis type="category" dataKey="name" tick={AXIS} tickLine={false} axisLine={false} width={150} />
          <Tooltip
            cursor={{ fill: "rgb(31 42 36 / 0.05)" }}
            content={
              <Tip
                render={(p: { name: string; supplier_type: string; amount: number }) => (
                  <>
                    <p className="font-semibold">{p.name}</p>
                    <p className="text-muted">{p.supplier_type === "SMME" ? "SMME" : "Large supplier"}</p>
                    <p className="num">{money(p.amount)}</p>
                  </>
                )}
              />
            }
          />
          <Bar dataKey="amount" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
            {data.map((s) => (
              <Cell key={s.supplier_id} fill={s.supplier_type === "SMME" ? SMME : LARGE} />
            ))}
            <LabelList dataKey="amount" position="right" formatter={(v: number) => moneyShort(v)} style={{ fill: INK, fontSize: 11, fontFamily: "JetBrains Mono" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DepartmentChart({ d }: { d: Dashboard }) {
  if (d.spend_by_department.length === 0) return <EmptyState title="No purchase orders yet" />;
  const data = [...d.spend_by_department].sort((a, b) => b.amount - a.amount);
  return (
    <div className="px-2 pt-3 pb-2" style={{ height: Math.max(140, data.length * 34 + 30) }} data-testid="chart-spend-department">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 64, left: 8, bottom: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" tick={AXIS_MONO} tickLine={false} axisLine={false} tickFormatter={(v: number) => moneyShort(v)} />
          <YAxis type="category" dataKey="department" tick={AXIS} tickLine={false} axisLine={false} width={100} />
          <Tooltip
            cursor={{ fill: "rgb(31 42 36 / 0.05)" }}
            content={
              <Tip
                render={(p: { department: string; amount: number }) => (
                  <>
                    <p className="font-semibold">{p.department}</p>
                    <p className="num">{money(p.amount)}</p>
                  </>
                )}
              />
            }
          />
          <Bar dataKey="amount" fill={INK} radius={[0, 4, 4, 0]} maxBarSize={20} isAnimationActive={false}>
            <LabelList dataKey="amount" position="right" formatter={(v: number) => moneyShort(v)} style={{ fill: INK, fontSize: 11, fontFamily: "JetBrains Mono" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SmmeShare({ d }: { d: Dashboard }) {
  const s = d.smme_share;
  const pct = Math.max(0, Math.min(100, s.pct));
  return (
    <div className="px-5 py-4" data-testid="smme-share">
      <div className="flex items-baseline justify-between">
        <p className="num text-3xl font-semibold" title={`${money(s.smme_amount)} of ${money(s.total_amount)}`}>
          {s.pct.toFixed(1)}%
        </p>
        <p className="num text-sm text-muted">
          {money(s.smme_amount)} / {money(s.total_amount)}
        </p>
      </div>
      <div className="mt-3 flex h-4 gap-[2px] overflow-hidden rounded" role="img" aria-label={`SMME ${s.pct.toFixed(1)} percent of committed spend`}>
        <div style={{ width: `${pct}%`, background: SMME }} className="rounded-l" />
        <div style={{ width: `${100 - pct}%`, background: LARGE }} className="rounded-r" />
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink-2">
        <Legend color={SMME} label="SMME" />
        <Legend color={LARGE} label="Large suppliers" />
      </div>
    </div>
  );
}

function AttentionList({ d }: { d: Dashboard }) {
  return (
    <Card className="rise">
      <CardHeader title="Needs attention" subtitle="Open invoices that are overdue or waiting for a review check. Oldest first, SMMEs first on ties." />
      {d.attention.length === 0 ? (
        <EmptyState title="Nothing needs attention">No overdue or unreviewed invoices.</EmptyState>
      ) : (
        <ul className="divide-y divide-rule" data-testid="attention-list">
          {d.attention.map((inv) => (
            <li key={inv.id}>
              <Link
                to={`/invoices/${inv.id}`}
                data-testid={`attention-row-${inv.invoice_number}`}
                className={`flex items-center gap-3 px-5 py-2.5 transition-colors hover:bg-sheet-2 ${inv.is_overdue ? "shadow-[inset_4px_0_0_var(--color-stamp-red)]" : ""}`}
              >
                <span className="num w-[4.5rem] shrink-0 font-semibold">{inv.invoice_number}</span>
                <span className="min-w-0 flex-1 truncate text-sm">
                  {inv.supplier.name}
                  {inv.supplier.supplier_type === "SMME" && <SmmeTag />}
                </span>
                <span className="num w-28 shrink-0 text-right text-sm">{money(inv.amount)}</span>
                <span className="w-12 shrink-0 text-right">
                  <DaysOutstanding invoice={inv} />
                </span>
                {/* Every row here is open (SUBMITTED or APPROVED), so only APPROVED needs a stamp:
                    it tells finance the invoice is just waiting for payment. Fixed width keeps columns aligned. */}
                <span className="flex w-[13.5rem] shrink-0 justify-end gap-1">
                  {inv.status === "APPROVED" && <StatusBadge status={inv.status} />}
                  <OverdueBadge invoice={inv} termsDays={d.payment_terms_days} />
                  <ReviewBadge count={inv.open_flag_count} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
