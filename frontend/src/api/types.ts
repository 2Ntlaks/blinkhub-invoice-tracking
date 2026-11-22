// Mirrors docs/api-contract.md section 4 exactly. Change the contract first.

export type Role = "SUPPLIER" | "FINANCE" | "MANAGER";
export type InvoiceStatus = "SUBMITTED" | "APPROVED" | "PAID" | "REJECTED";
export type FlagStatus = "OPEN" | "CLEARED" | "CONFIRMED";
export type FlagRule = "POSSIBLE_DUPLICATE" | "PO_OVER_INVOICED";
export type AgeingBucket = "0-30" | "31-60" | "61-90" | "90+";
export type SupplierType = "SMME" | "LARGE";
export type AuditAction =
  | "SUBMITTED"
  | "APPROVED"
  | "REJECTED"
  | "PAID"
  | "FLAG_RAISED"
  | "FLAG_CLEARED"
  | "FLAG_CONFIRMED";

export interface User {
  id: number;
  name: string;
  role: Role;
  supplier_id: number | null;
}

export interface Supplier {
  id: number;
  name: string;
  province: "GP" | "LP" | "KZN" | "MP";
  supplier_type: SupplierType;
  bbbee_level: number;
  status: "ACTIVE" | "INACTIVE";
  is_synthetic: boolean;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string;
  category: string;
  department: string;
  amount: number;
  invoiced_amount: number;
  remaining_amount: number;
  is_synthetic: boolean;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  supplier: { id: number; name: string; supplier_type: SupplierType };
  po: { id: number; po_number: string; amount: number };
  amount: number;
  invoice_date: string;
  submitted_at: string;
  status: InvoiceStatus;
  days_outstanding: number | null;
  is_overdue: boolean;
  is_due_soon: boolean;
  ageing_bucket: AgeingBucket | null;
  /** Always null for SUPPLIER users. */
  open_flag_count: number | null;
  approved_at: string | null;
  paid_at: string | null;
  payment_reference: string | null;
  rejection_reason: string | null;
  is_synthetic: boolean;
}

export interface Flag {
  id: number;
  invoice_id: number;
  invoice_number: string;
  supplier_name: string;
  rule: FlagRule;
  message: string;
  related_invoice_id: number | null;
  related_invoice_number: string | null;
  status: FlagStatus;
  raised_at: string;
  resolved_at: string | null;
  resolved_by: { id: number; name: string } | null;
  resolution_note: string | null;
}

export interface AuditEvent {
  id: number;
  at: string;
  actor: { id: number; name: string; role: Role | "SYSTEM" };
  action: AuditAction;
  from_status: InvoiceStatus | null;
  to_status: InvoiceStatus | null;
  note: string | null;
}

export interface InvoiceDetail extends Invoice {
  description: string | null;
  flags: Flag[];
  audit: AuditEvent[];
}

export interface InvoiceCreate {
  invoice_number: string;
  po_id: number;
  amount: number;
  invoice_date: string;
  description?: string;
}

export interface InvoiceQuery {
  status?: InvoiceStatus;
  supplier_id?: number;
  overdue?: boolean;
  flagged?: boolean;
  sort?: "age_desc" | "amount_desc" | "submitted_desc";
}

export interface Dashboard {
  as_of: string;
  payment_terms_days: number;
  kpis: {
    outstanding_count: number;
    outstanding_amount: number;
    overdue_count: number;
    overdue_amount: number;
    due_soon_count: number;
    avg_payment_turnaround_days: number | null;
    open_flag_count: number;
    smme_spend_share_pct: number;
  };
  ageing: { bucket: AgeingBucket; count: number; amount: number }[];
  spend_by_supplier: { supplier_id: number; name: string; supplier_type: SupplierType; amount: number }[];
  spend_by_department: { department: string; amount: number }[];
  smme_share: { smme_amount: number; total_amount: number; pct: number };
  attention: Invoice[];
}

export interface ErrorBody {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
}
