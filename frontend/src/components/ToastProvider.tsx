import { useCallback, useMemo, useState, type ReactNode } from "react";
import { ToastContext, type ToastTone } from "../lib/toast";

interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((message: string, tone: ToastTone = "success") => {
    const id = nextId++;
    setToasts((t) => [...t, { id, message, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            data-testid="toast"
            data-tone={t.tone}
            className={`rise pointer-events-auto max-w-sm rounded-md border-l-4 bg-ink px-4 py-3 text-sm text-sheet shadow-lg ${
              t.tone === "success" ? "border-[#7fbf8a]" : t.tone === "error" ? "border-[#ff8f84]" : "border-[#9db8e6]"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
