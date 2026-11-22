import { useCallback, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router";
import type { Role } from "./api/types";
import { Layout } from "./components/Layout";
import { SessionProvider } from "./components/SessionProvider";
import { ToastProvider } from "./components/ToastProvider";
import { Card, EmptyState } from "./components/ui";
import { useSession } from "./lib/session";
import { DashboardPage } from "./pages/DashboardPage";
import { InvoiceDetailPage } from "./pages/InvoiceDetailPage";
import { InvoiceQueuePage } from "./pages/InvoiceQueuePage";
import { MyInvoicesPage } from "./pages/MyInvoicesPage";
import { NeedsReviewPage } from "./pages/NeedsReviewPage";
import { SubmitInvoicePage } from "./pages/SubmitInvoicePage";

const HOME: Record<Role, string> = {
  SUPPLIER: "/my-invoices",
  FINANCE: "/invoices",
  MANAGER: "/dashboard",
};

function RoleHome() {
  const { user } = useSession();
  return <Navigate to={HOME[user.role]} replace />;
}

/** Client-side guard only for a clear message; the API enforces roles itself (403/404). */
function Allow({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useSession();
  if (!roles.includes(user.role)) {
    return (
      <Card data-testid="not-allowed">
        <EmptyState title="This page is not part of your role">Use the menu above, or switch user in the top right.</EmptyState>
      </Card>
    );
  }
  return <>{children}</>;
}

function Shell() {
  const navigate = useNavigate();
  // After switching user, go to that role's home page: the current page may not
  // exist for them (for example another supplier's invoice).
  const onSwitch = useCallback(() => navigate("/", { replace: true }), [navigate]);
  return (
    <SessionProvider onSwitch={onSwitch}>
      <KeyedRoutes />
    </SessionProvider>
  );
}

/** Keying on the user id re-mounts every page, so all data is re-fetched for the new user. */
function KeyedRoutes() {
  const { user } = useSession();
  const internal: Role[] = ["FINANCE", "MANAGER"];
  return (
    <Routes key={user.id}>
      <Route element={<Layout />}>
        <Route index element={<RoleHome />} />
        <Route path="my-invoices" element={<Allow roles={["SUPPLIER"]}><MyInvoicesPage /></Allow>} />
        <Route path="submit" element={<Allow roles={["SUPPLIER"]}><SubmitInvoicePage /></Allow>} />
        <Route path="invoices" element={<Allow roles={internal}><InvoiceQueuePage /></Allow>} />
        <Route path="invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="review" element={<Allow roles={internal}><NeedsReviewPage /></Allow>} />
        <Route path="dashboard" element={<Allow roles={internal}><DashboardPage /></Allow>} />
        <Route
          path="*"
          element={
            <Card>
              <EmptyState title="Page not found" />
            </Card>
          }
        />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </BrowserRouter>
  );
}
