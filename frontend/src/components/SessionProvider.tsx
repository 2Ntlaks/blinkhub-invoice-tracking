import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorMessage, setCurrentUserId } from "../api/client";
import type { User } from "../api/types";
import { loadUserId, saveUserId, SessionContext } from "../lib/session";
import { Button, Spinner } from "./ui";

/**
 * Loads the demo users from GET /api/users and keeps the picked user.
 * Default is the finance officer (the main demo persona) when nothing is stored.
 */
export function SessionProvider({ children, onSwitch }: { children: ReactNode; onSwitch?: () => void }) {
  const [users, setUsers] = useState<User[] | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    setError(null);
    api
      .users()
      .then((list) => {
        if (!live) return;
        const stored = loadUserId();
        const pick = list.find((u) => u.id === stored) ?? list.find((u) => u.role === "FINANCE") ?? list[0];
        // Set the header before any child mounts and fires a request.
        setCurrentUserId(pick?.id ?? null);
        setUsers(list);
        setUserId(pick?.id ?? null);
      })
      .catch((e: unknown) => live && setError(errorMessage(e)));
    return () => {
      live = false;
    };
  }, [tick]);

  const switchUser = useCallback(
    (id: number) => {
      setCurrentUserId(id);
      saveUserId(id);
      setUserId(id);
      onSwitch?.();
    },
    [onSwitch],
  );

  const user = users?.find((u) => u.id === userId);
  const value = useMemo(() => (users && user ? { users, user, switchUser } : null), [users, user, switchUser]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6" data-testid="boot-error">
        <div className="sheet max-w-md p-6">
          <h1 className="text-2xl font-semibold">BlinkHub is not reachable</h1>
          <p className="mt-2 text-ink-2">{error}</p>
          <p className="mt-2 text-sm text-muted">
            Start the backend from <code className="num">backend/</code> with{" "}
            <code className="num">.venv/Scripts/python -m uvicorn app.main:app --port 8000</code>.
          </p>
          <Button className="mt-4" onClick={() => setTick((t) => t + 1)}>
            Try again
          </Button>
        </div>
      </div>
    );
  }
  if (!value) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 text-muted" data-testid="boot-loading">
        <Spinner /> Opening the ledger...
      </div>
    );
  }
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
