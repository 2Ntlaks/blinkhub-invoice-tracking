import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router";
import type { Role, User } from "../api/types";
import { ROLE_LABEL } from "../lib/format";
import { useSession } from "../lib/session";

interface NavItem {
  to: string;
  label: string;
  testId: string;
}

// Navigation adapts to the role. Suppliers never get a link to anything review-related.
const NAV: Record<Role, NavItem[]> = {
  SUPPLIER: [
    { to: "/my-invoices", label: "My invoices", testId: "nav-my-invoices" },
    { to: "/submit", label: "Submit invoice", testId: "nav-submit" },
  ],
  FINANCE: [
    { to: "/invoices", label: "Invoice queue", testId: "nav-invoices" },
    { to: "/review", label: "Needs review", testId: "nav-review" },
    { to: "/dashboard", label: "Dashboard", testId: "nav-dashboard" },
  ],
  MANAGER: [
    { to: "/dashboard", label: "Dashboard", testId: "nav-dashboard" },
    { to: "/invoices", label: "Invoices", testId: "nav-invoices" },
    { to: "/review", label: "Needs review", testId: "nav-review" },
  ],
};

const GROUPS: { role: Role; label: string }[] = [
  { role: "FINANCE", label: "Finance" },
  { role: "MANAGER", label: "Management" },
  { role: "SUPPLIER", label: "Supplier portal" },
];

/** Seeded supplier users are called "<Supplier> (supplier portal)"; the group label already says that. */
function shortName(u: User): string {
  return u.name.replace(/\s*\(supplier portal\)\s*$/i, "");
}

function RoleSwitcher() {
  const { users, user, switchUser } = useSession();
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden text-sheet/70 lg:inline">Viewing as</span>
      <select
        data-testid="role-switcher"
        aria-label="Switch demo user"
        value={user.id}
        onChange={(e) => switchUser(Number(e.target.value))}
        className="max-w-[16rem] rounded-md border border-sheet/30 bg-ink-2/60 px-2.5 py-1.5 text-sm text-sheet focus:bg-ink"
      >
        {GROUPS.map((g) => {
          const list = users.filter((u) => u.role === g.role);
          if (list.length === 0) return null;
          return (
            <optgroup key={g.role} label={g.label} className="bg-sheet text-ink">
              {list.map((u) => (
                <option key={u.id} value={u.id} data-testid={`role-option-${u.id}`} className="bg-sheet text-ink">
                  {shortName(u)}
                </option>
              ))}
            </optgroup>
          );
        })}
      </select>
    </label>
  );
}

export function Layout() {
  const { user } = useSession();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-ink text-sheet shadow-[0_2px_0_0_var(--color-margin)]">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-6 px-5">
          <NavLink to="/" className="flex items-baseline gap-2" data-testid="brand">
            <span className="font-display text-xl font-semibold tracking-tight">BlinkHub</span>
            <span className="hidden text-xs tracking-[0.18em] text-sheet/60 uppercase md:inline">Invoices &amp; payments</span>
          </NavLink>
          <nav className="flex items-center gap-1" aria-label="Main">
            {NAV[user.role].map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                data-testid={n.testId}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${isActive ? "bg-sheet text-ink" : "text-sheet/80 hover:bg-sheet/10 hover:text-sheet"}`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span data-testid="current-role" className="hidden rounded-sm border border-sheet/30 px-2 py-0.5 font-mono text-[0.68rem] tracking-widest text-sheet/80 uppercase sm:inline">
              {ROLE_LABEL[user.role]}
              {user.role === "MANAGER" && " · read-only"}
            </span>
            <RoleSwitcher />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1320px] flex-1 px-5 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-[1320px] px-5 pb-5 text-xs text-muted">
        Demo prototype for the ProcureSense BlinkHub challenge. Users are fictional; no real sign-in.
      </footer>
    </div>
  );
}

export function PageTitle({ title, kicker, right }: { title: string; kicker?: string; right?: ReactNode }) {
  return (
    <div className="rise mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        {kicker && <p className="font-mono text-xs tracking-[0.16em] text-margin uppercase">{kicker}</p>}
        <h1 className="text-[1.9rem] leading-tight font-semibold">{title}</h1>
      </div>
      {right}
    </div>
  );
}
