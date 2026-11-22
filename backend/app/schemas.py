"""Request and response bodies, exactly as in the API contract (section 4 and 5).

Money is a ``Decimal`` everywhere in Python and is only turned into a JSON number at
the very edge, when the response is written. Timestamps are written as ISO 8601 UTC
with a ``Z`` suffix (for example ``2026-11-22T10:00:00Z``).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

from app.enums import (
    AuditAction,
    FlagRule,
    FlagStatus,
    InvoiceStatus,
    Role,
    SupplierStatus,
    SupplierType,
)


def _money_to_json(value: Decimal) -> float:
    # The contract sends money as JSON numbers. Values are at most 2 decimals and well
    # inside float's exact range for cents, so this conversion is display-only and safe.
    return float(value)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


Money = Annotated[Decimal, PlainSerializer(_money_to_json, return_type=float, when_used="json")]
UtcTimestamp = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]
Pct = Annotated[Decimal, PlainSerializer(_money_to_json, return_type=float, when_used="json")]

Trimmed = StringConstraints(strip_whitespace=True)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Resources -------------------------------------------------------------


class UserOut(Out):
    id: int
    name: str
    role: Role
    supplier_id: int | None
    supplier_status: SupplierStatus | None


class SupplierOut(Out):
    id: int
    name: str
    province: str
    supplier_type: SupplierType
    bbbee_level: int
    status: SupplierStatus
    is_synthetic: bool


class PurchaseOrderOut(Out):
    id: int
    po_number: str
    supplier_id: int
    supplier_name: str
    category: str
    department: str
    amount: Money
    invoiced_amount: Money
    remaining_amount: Money
    is_synthetic: bool


class InvoiceSupplierRef(Out):
    id: int
    name: str
    supplier_type: SupplierType


class InvoicePoRef(Out):
    id: int
    po_number: str
    amount: Money


class InvoiceOut(Out):
    id: int
    invoice_number: str
    supplier: InvoiceSupplierRef
    po: InvoicePoRef
    amount: Money
    invoice_date: date
    submitted_at: UtcTimestamp
    status: InvoiceStatus
    days_outstanding: int | None
    is_overdue: bool
    is_due_soon: bool
    ageing_bucket: str | None
    # Always null for SUPPLIER users: suppliers never see flags.
    open_flag_count: int | None
    approved_at: UtcTimestamp | None
    paid_at: UtcTimestamp | None
    payment_reference: str | None
    rejection_reason: str | None
    is_synthetic: bool


class PersonRef(Out):
    id: int
    name: str


class FlagOut(Out):
    id: int
    invoice_id: int
    invoice_number: str
    supplier_name: str
    rule: FlagRule
    message: str
    related_invoice_id: int | None
    related_invoice_number: str | None
    status: FlagStatus
    raised_at: UtcTimestamp
    resolved_at: UtcTimestamp | None
    resolved_by: PersonRef | None
    resolution_note: str | None


class ActorOut(Out):
    id: int
    name: str
    role: str  # a Role, or "SYSTEM" for automatic and imported events


class AuditEventOut(Out):
    id: int
    at: UtcTimestamp
    actor: ActorOut
    action: AuditAction
    from_status: InvoiceStatus | None
    to_status: InvoiceStatus | None
    note: str | None


class InvoiceDetailOut(InvoiceOut):
    description: str | None
    flags: list[FlagOut]
    audit: list[AuditEventOut]


# --- Dashboard ---------------------------------------------------------------


class DashboardKpis(Out):
    outstanding_count: int
    outstanding_amount: Money
    overdue_count: int
    overdue_amount: Money
    due_soon_count: int
    avg_payment_turnaround_days: Pct | None
    open_flag_count: int
    smme_spend_share_pct: Pct


class AgeingBucketOut(Out):
    bucket: str
    count: int
    amount: Money


class SupplierSpendOut(Out):
    supplier_id: int
    name: str
    supplier_type: SupplierType
    amount: Money


class DepartmentSpendOut(Out):
    department: str
    amount: Money


class SmmeShareOut(Out):
    smme_amount: Money
    total_amount: Money
    pct: Pct


class DashboardOut(Out):
    as_of: UtcTimestamp
    payment_terms_days: int
    kpis: DashboardKpis
    ageing: list[AgeingBucketOut]
    spend_by_supplier: list[SupplierSpendOut]
    spend_by_department: list[DepartmentSpendOut]
    smme_share: SmmeShareOut
    attention: list[InvoiceOut]


class HealthOut(BaseModel):
    status: str


# --- Requests ----------------------------------------------------------------


class InvoiceCreate(BaseModel):
    # supplier_id is deliberately not a field: it always comes from the logged-in
    # supplier user, so a supplier cannot submit on another supplier's behalf.
    invoice_number: Annotated[str, Trimmed, StringConstraints(min_length=1, max_length=50)]
    po_id: int
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    invoice_date: date
    description: Annotated[str | None, Field(max_length=500)] = None


class ApproveRequest(BaseModel):
    note: Annotated[str | None, Field(max_length=500)] = None


class RejectRequest(BaseModel):
    # At least 5 characters after trimming, so "no" is not accepted as a reason: the
    # supplier is shown this text and needs to know what to fix.
    reason: Annotated[str, Trimmed, StringConstraints(min_length=5, max_length=500)]


class PayRequest(BaseModel):
    payment_reference: Annotated[str, Trimmed, StringConstraints(min_length=1, max_length=100)]


class ResolveFlagRequest(BaseModel):
    outcome: Literal["CLEARED", "CONFIRMED"]
    # The reviewer must say why; the note is the evidence behind the decision.
    note: Annotated[str, Trimmed, StringConstraints(min_length=1, max_length=500)]
