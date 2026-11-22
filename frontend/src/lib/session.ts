import { createContext, useContext } from "react";
import type { User } from "../api/types";

export interface Session {
  users: User[];
  user: User;
  switchUser: (id: number) => void;
}

export const SessionContext = createContext<Session | null>(null);

/** The demo "logged in" user picked in the role switcher. */
export function useSession(): Session {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useSession must be used inside <SessionProvider>");
  return s;
}

const KEY = "blinkhub.userId";

// localStorage may be unavailable (private window, blocked storage): never let it crash the app.
export function loadUserId(): number | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    const n = raw === null ? NaN : Number(raw);
    return Number.isInteger(n) ? n : null;
  } catch {
    return null;
  }
}

export function saveUserId(id: number): void {
  try {
    window.localStorage.setItem(KEY, String(id));
  } catch {
    /* ignore: the choice just will not persist */
  }
}
