import type {
  Dashboard,
  ErrorBody,
  Flag,
  FlagStatus,
  Invoice,
  InvoiceCreate,
  InvoiceDetail,
  InvoiceQuery,
  PurchaseOrder,
  Supplier,
  User,
} from "./types";

export interface FieldError {
  field: string;
  message: string;
}

/** An error returned by the API in the contract's `{ error: { code, message, details } }` shape. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: FieldError[] | null;

  constructor(status: number, code: string, message: string, details: FieldError[] | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Message for one form field from a VALIDATION_ERROR, if any. */
  fieldMessage(field: string): string | undefined {
    return this.details?.find((d) => d.field === field)?.message;
  }
}

// The user picked in the role switcher. Kept in a module variable so every
// request sends it without threading it through every call site.
let currentUserId: number | null = null;
export function setCurrentUserId(id: number | null): void {
  currentUserId = id;
}

function isErrorBody(x: unknown): x is ErrorBody {
  if (typeof x !== "object" || x === null || !("error" in x)) return false;
  const e = (x as { error: unknown }).error;
  return typeof e === "object" && e !== null && typeof (e as { message?: unknown }).message === "string";
}

function toFieldErrors(details: unknown): FieldError[] | null {
  if (!Array.isArray(details)) return null;
  const out: FieldError[] = [];
  for (const d of details) {
    if (d && typeof d === "object" && typeof d.field === "string" && typeof d.message === "string") {
      out.push({ field: d.field, message: d.message });
    }
  }
  return out;
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (currentUserId !== null) headers["X-User-Id"] = String(currentUserId);
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the BlinkHub server. Is the backend running on port 8000?", null);
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    if (isErrorBody(data)) {
      const e = data.error;
      throw new ApiError(res.status, String(e.code), e.message, toFieldErrors(e.details));
    }
    // Vite proxy returns a bare 500/502/504 when the backend is down.
    if (res.status >= 500 && !text.trim().startsWith("{")) {
      throw new ApiError(res.status, "NETWORK", "Cannot reach the BlinkHub server. Is the backend running on port 8000?", null);
    }
    throw new ApiError(res.status, `HTTP_${res.status}`, `The server returned an unexpected error (${res.status}).`, null);
  }
  return data as T;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === false || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  users: () => request<User[]>("GET", "/users"),
  me: () => request<User>("GET", "/me"),
  suppliers: () => request<Supplier[]>("GET", "/suppliers"),
  purchaseOrders: (supplierId?: number) =>
    request<PurchaseOrder[]>("GET", `/purchase-orders${qs({ supplier_id: supplierId })}`),
  invoices: (q: InvoiceQuery = {}) => request<Invoice[]>("GET", `/invoices${qs({ ...q })}`),
  invoice: (id: number) => request<InvoiceDetail>("GET", `/invoices/${id}`),
  createInvoice: (body: InvoiceCreate) => request<InvoiceDetail>("POST", "/invoices", body),
  approve: (id: number, note?: string) =>
    request<InvoiceDetail>("POST", `/invoices/${id}/approve`, note ? { note } : {}),
  reject: (id: number, reason: string) => request<InvoiceDetail>("POST", `/invoices/${id}/reject`, { reason }),
  pay: (id: number, payment_reference: string) =>
    request<InvoiceDetail>("POST", `/invoices/${id}/pay`, { payment_reference }),
  flags: (status?: FlagStatus) => request<Flag[]>("GET", `/flags${qs({ status })}`),
  resolveFlag: (id: number, outcome: "CLEARED" | "CONFIRMED", note: string) =>
    request<Flag>("POST", `/flags/${id}/resolve`, { outcome, note }),
  dashboard: () => request<Dashboard>("GET", "/dashboard"),
};

/** Human message for any thrown value. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong.";
}
