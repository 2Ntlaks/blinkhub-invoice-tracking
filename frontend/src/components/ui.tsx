// Small hand-built components in the spirit of shadcn/ui: unstyled-by-default
// primitives with our ledger look baked in. No UI kit dependency.
import { useEffect, useId, useRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "success" | "ghost";

const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-sheet border-ink hover:bg-ink-2",
  secondary: "bg-sheet text-ink border-rule-strong hover:bg-sheet-2",
  danger: "bg-stamp-red text-white border-stamp-red hover:brightness-110",
  success: "bg-stamp-green text-white border-stamp-green hover:brightness-110",
  ghost: "bg-transparent text-ink border-transparent hover:bg-sheet-2",
};

export function Button({
  variant = "primary",
  className = "",
  busy = false,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-2 rounded-md border px-3.5 py-2 text-sm font-semibold transition-[background-color,filter] disabled:cursor-not-allowed disabled:opacity-45 ${VARIANT[variant]} ${className}`}
    >
      {busy && <Spinner small />}
      {children}
    </button>
  );
}

export function Card({ children, className = "", ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section {...rest} className={`sheet ${className}`}>
      {children}
    </section>
  );
}

export function CardHeader({ title, subtitle, right }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-rule px-5 py-3.5">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Badge({ tone, children, title, testId }: { tone: "blue" | "green" | "red" | "amber" | "ink"; children: ReactNode; title?: string; testId?: string }) {
  const color = {
    blue: "text-stamp-blue",
    green: "text-stamp-green",
    red: "text-stamp-red",
    amber: "text-stamp-amber",
    ink: "text-ink-2",
  }[tone];
  return (
    <span className={`stamp ${color}`} title={title} data-testid={testId}>
      {children}
    </span>
  );
}

export function Spinner({ small = false }: { small?: boolean }) {
  const size = small ? "h-3.5 w-3.5" : "h-6 w-6";
  return (
    <span
      aria-hidden
      className={`inline-block ${size} rounded-full border-2 border-current border-t-transparent`}
      style={{ animation: "spin 0.8s linear infinite" }}
    />
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div data-testid="state-loading" role="status" className="flex items-center gap-3 px-5 py-10 text-muted">
      <Spinner />
      <span>{label}...</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div data-testid="state-error" role="alert" className="m-4 flex items-start justify-between gap-4 rounded-md border border-stamp-red/40 bg-red-wash px-4 py-3 text-stamp-red">
      <div>
        <p className="font-semibold">Could not load this</p>
        <p className="text-sm">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div data-testid="state-empty" className="px-5 py-12 text-center">
      <p className="font-display text-lg text-ink-2">{title}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  );
}

/** Label + control + hint/error. The error is announced and linked via aria-describedby. */
export function Field({ label, error, hint, children, htmlFor, testId }: { label: string; error?: string; hint?: ReactNode; children: ReactNode; htmlFor: string; testId?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-semibold text-ink-2">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} data-testid={testId ? `${testId}-error` : undefined} className="text-sm font-medium text-stamp-red" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

const CONTROL =
  "w-full rounded-md border bg-white/70 px-3 py-2 text-[0.95rem] text-ink placeholder:text-muted/70 focus:bg-white aria-[invalid=true]:border-stamp-red aria-[invalid=true]:bg-red-wash/40 border-rule-strong";

export function Input({ className = "", invalid, ...rest }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return <input {...rest} aria-invalid={invalid || undefined} aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined} className={`${CONTROL} ${className}`} />;
}

export function Textarea({ className = "", invalid, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return <textarea {...rest} aria-invalid={invalid || undefined} aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined} className={`${CONTROL} min-h-20 ${className}`} />;
}

export function Select({ className = "", invalid, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select {...rest} aria-invalid={invalid || undefined} aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined} className={`${CONTROL} pr-8 ${className}`}>
      {children}
    </select>
  );
}

/** Modal dialog on the native <dialog> element: focus trap and Esc come for free. */
export function Dialog({ open, onClose, title, children, testId }: { open: boolean; onClose: () => void; title: string; children: ReactNode; testId?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      data-testid={testId}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      className="sheet m-auto w-[min(32rem,calc(100vw-2rem))] p-0 text-ink backdrop:bg-ink/40 backdrop:backdrop-blur-[1px]"
    >
      {open && (
        <div className="rise">
          <div className="flex items-center justify-between border-b border-rule px-5 py-3">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded px-2 text-xl leading-none text-muted hover:text-ink">
              ×
            </button>
          </div>
          <div className="px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

export function Notice({ tone, title, children, testId }: { tone: "amber" | "red" | "blue" | "green"; title?: string; children: ReactNode; testId?: string }) {
  const cls = {
    amber: "border-stamp-amber/45 bg-amber-wash text-[#6b3f05]",
    red: "border-stamp-red/40 bg-red-wash text-[#7a1f1b]",
    blue: "border-stamp-blue/35 bg-blue-wash text-[#1d3d70]",
    green: "border-stamp-green/35 bg-green-wash text-[#1f4a27]",
  }[tone];
  return (
    <div data-testid={testId} role={tone === "red" ? "alert" : "note"} className={`rounded-md border px-4 py-3 text-sm ${cls}`}>
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      <div>{children}</div>
    </div>
  );
}
