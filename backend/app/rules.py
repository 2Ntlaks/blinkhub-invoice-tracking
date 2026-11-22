"""BlinkHub business rules.

Every rule the system enforces lives in this one module, as a pure function: no
database, no web framework, no clock. Callers pass in the facts (and the current
time as ``now``), and get back a decision. That makes each rule easy to read, easy
to test, and easy to defend: the same function decides for the live API and for the
seed script, so the demo data is flagged by exactly the rules a real submission meets.

Inputs are described with small ``Protocol`` types. Anything with the right
attributes works: the database models in production, tiny dataclasses in the tests.

Language rule: a flag is a *question for a finance officer*, never an accusation.
Messages say what was noticed and ask for review. They never say "fraud" or similar.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from app.enums import (
    ErrorCode,
    FlagRule,
    FlagStatus,
    InvoiceAction,
    InvoiceStatus,
    SupplierStatus,
    SupplierType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Invoices must be paid within this many days of submission (assumption A5:
#: the case study asks about "invoices exceeding 30 days").
PAYMENT_TERMS_DAYS = 30

#: An invoice is "due soon" in the last 10 days before it becomes overdue, so
#: finance can act before the supplier is let down rather than after.
DUE_SOON_FROM_DAYS = 21

#: Two invoices from the same supplier for the same amount count as a possible
#: duplicate only if submitted within this window. Regular monthly invoices of the
#: same amount are normal; 90 days keeps the check focused on recent repeats while
#: still catching a re-bill of last quarter's work.
DUPLICATE_WINDOW = timedelta(days=90)

#: South Africa has one time zone and no daylight saving, so a fixed UTC+2 offset is
#: exact. Used only to decide what "today" means for an invoice date, so a supplier
#: submitting just after midnight SAST is not told their invoice is "in the future".
BUSINESS_TZ_OFFSET = timedelta(hours=2)

#: Statuses that still count against a PO or for duplicate checks. A rejected
#: invoice is void: it is ignored by every rule.
LIVE_STATUSES = frozenset({InvoiceStatus.SUBMITTED, InvoiceStatus.APPROVED, InvoiceStatus.PAID})

#: Statuses where the supplier is still waiting for money.
OPEN_STATUSES = frozenset({InvoiceStatus.SUBMITTED, InvoiceStatus.APPROVED})

#: Ageing buckets for open invoices: (label, lowest day, highest day or None).
AGEING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("0-30", 0, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
)

#: The lifecycle in one table: action -> (statuses it is allowed from, status it leads to).
#:   SUBMITTED --approve--> APPROVED --pay--> PAID
#:   SUBMITTED/APPROVED --reject--> REJECTED (terminal)
#: Paying needs an approval first (two steps, so one person's mistake is caught).
#: A paid invoice cannot be rejected: the money has left, so it needs a credit note,
#: which is outside this prototype.
TRANSITIONS: dict[InvoiceAction, tuple[frozenset[InvoiceStatus], InvoiceStatus]] = {
    InvoiceAction.APPROVE: (frozenset({InvoiceStatus.SUBMITTED}), InvoiceStatus.APPROVED),
    InvoiceAction.REJECT: (
        frozenset({InvoiceStatus.SUBMITTED, InvoiceStatus.APPROVED}),
        InvoiceStatus.REJECTED,
    ),
    InvoiceAction.PAY: (frozenset({InvoiceStatus.APPROVED}), InvoiceStatus.PAID),
}

#: Flag statuses that block approval. OPEN = nobody has looked yet. CONFIRMED = a
#: person looked and agreed there is a real problem, so the invoice should be rejected,
#: not approved. Only CLEARED ("reviewed, legitimate") lets approval go ahead.
BLOCKING_FLAG_STATUSES = frozenset({FlagStatus.OPEN, FlagStatus.CONFIRMED})


# ---------------------------------------------------------------------------
# Input shapes
# ---------------------------------------------------------------------------


class SupplierLike(Protocol):
    id: int
    name: str
    status: SupplierStatus


class PurchaseOrderLike(Protocol):
    id: int
    po_number: str
    supplier_id: int
    amount: Decimal


class InvoiceLike(Protocol):
    id: int
    invoice_number: str
    supplier_id: int
    po_id: int
    amount: Decimal
    status: InvoiceStatus
    submitted_at: datetime


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rejection:
    """Why a request was refused, using the contract's error codes."""

    code: ErrorCode
    message: str
    details: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class FlagDraft:
    """A flag the caller should store. The rule decides; the caller persists."""

    rule: FlagRule
    message: str
    related_invoice_id: int | None = None
    related_invoice_number: str | None = None


@dataclass(frozen=True)
class Ageing:
    days_outstanding: int | None
    is_overdue: bool
    is_due_soon: bool
    ageing_bucket: str | None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def format_rand(amount: Decimal) -> str:
    """Format money the way South African finance staff read it: ``R85,000.00``."""
    return f"R{amount:,.2f}"


def business_today(now: datetime) -> date:
    """Today's date in South Africa (UTC+2), used to judge invoice dates."""
    return (now.astimezone(UTC) + BUSINESS_TZ_OFFSET).date()


def normalise_invoice_number(invoice_number: str) -> str:
    """Trim spaces and upper-case, so ``" inv-001 "`` and ``"INV-001"`` are the same number.

    Suppliers type invoice numbers by hand. Without this, a stray space or a lower-case
    letter would let the same invoice through twice.
    """
    return invoice_number.strip().upper()


def _field_error(field: str, message: str) -> Rejection:
    return Rejection(
        code=ErrorCode.VALIDATION_ERROR,
        message=f"{field}: {message}",
        details=[{"field": field, "message": message}],
    )


# ---------------------------------------------------------------------------
# 3.1 Hard checks on submit (the invoice is NOT created)
# ---------------------------------------------------------------------------


def find_exact_duplicate(invoice_number: str, supplier_invoices: Iterable[InvoiceLike]) -> InvoiceLike | None:
    """Return the supplier's existing live invoice with the same number, if any.

    The same supplier must never have two live invoices with one number: that is the
    clearest sign of a double bill, so it is refused outright. Rejected invoices are
    ignored on purpose: if finance rejected an invoice (say, a wrong amount), the
    supplier must be able to send a corrected one under the same number.
    """
    wanted = normalise_invoice_number(invoice_number)
    for invoice in supplier_invoices:
        if invoice.status in LIVE_STATUSES and normalise_invoice_number(invoice.invoice_number) == wanted:
            return invoice
    return None


def check_submission(
    *,
    invoice_number: str,
    amount: Decimal,
    invoice_date: date,
    now: datetime,
    supplier: SupplierLike,
    requested_po_id: int,
    po: PurchaseOrderLike | None,
    supplier_invoices: Iterable[InvoiceLike],
) -> Rejection | None:
    """Run the hard checks in order. Return the first problem, or ``None`` if all pass.

    These are things that are simply wrong, so the invoice is not created at all:

    1. Basic field sense: amount above zero, a number to identify the invoice, and
       an invoice date that is not in the future.
    2. The supplier must be active. Checked before the PO on purpose: an inactive
       supplier should get the one answer that explains the real problem, and we do
       not tell them anything about POs they ask for.
    3. The PO must exist, and 4. belong to this supplier: you can only bill against
       work you were contracted for.
    5. One invoice may not be larger than the whole PO. (Several invoices that add up
       to more than the PO are allowed but flagged: see :func:`detect_flags`.)
    6. No second live invoice with the same number (see :func:`find_exact_duplicate`).
    """
    # 1. Field checks. The API schema also checks these; repeating them here keeps the
    #    rule complete for any caller (for example the seed script).
    if amount <= 0:
        return _field_error("amount", "must be greater than 0")
    if not invoice_number.strip():
        return _field_error("invoice_number", "must not be empty")
    if invoice_date > business_today(now):
        return _field_error("invoice_date", "must not be in the future")

    # 2. Supplier active.
    if supplier.status != SupplierStatus.ACTIVE:
        return Rejection(
            ErrorCode.SUPPLIER_INACTIVE,
            f"{supplier.name} is not an active supplier, so new invoices cannot be submitted. "
            "Please contact the procurement office.",
        )

    # 3. PO exists.
    if po is None:
        return Rejection(ErrorCode.PO_NOT_FOUND, f"Purchase order {requested_po_id} does not exist.")

    # 4. PO belongs to this supplier. The message deliberately does not name the PO's
    #    real owner: one supplier should not learn who another supplier's POs are with.
    if po.supplier_id != supplier.id:
        return Rejection(
            ErrorCode.PO_SUPPLIER_MISMATCH,
            f"{po.po_number} does not belong to {supplier.name}.",
        )

    # 5. A single invoice may equal the PO amount, but not exceed it.
    if amount > po.amount:
        return Rejection(
            ErrorCode.AMOUNT_EXCEEDS_PO,
            f"Invoice amount {format_rand(amount)} is more than the {po.po_number} amount "
            f"of {format_rand(po.amount)}.",
        )

    # 6. Exact duplicate number.
    existing = find_exact_duplicate(invoice_number, supplier_invoices)
    if existing is not None:
        return Rejection(
            ErrorCode.DUPLICATE_INVOICE_NUMBER,
            f"Invoice number {normalise_invoice_number(invoice_number)} has already been submitted "
            f"by {supplier.name} (status {existing.status}).",
        )
    return None


# ---------------------------------------------------------------------------
# 3.2 Soft checks on submit (the invoice IS created, a flag asks for review)
# ---------------------------------------------------------------------------


def find_possible_duplicates(
    new_invoice: InvoiceLike, supplier_invoices: Iterable[InvoiceLike]
) -> list[InvoiceLike]:
    """Other live invoices from the same supplier, same amount, within 90 days.

    Different invoice numbers with the same amount close together *may* be the same
    work billed twice (as with INV001 and INV006 in the case study). It may also be
    a normal repeat order, which is why this only raises a flag for a person to check.
    The window is measured either side of the new invoice's submission time, so the
    seed script gets the same answer whatever order it loads history in.
    """
    return [
        other
        for other in supplier_invoices
        if other.id != new_invoice.id
        and other.supplier_id == new_invoice.supplier_id
        and other.status in LIVE_STATUSES
        and other.amount == new_invoice.amount
        and abs(new_invoice.submitted_at - other.submitted_at) <= DUPLICATE_WINDOW
    ]


def _duplicate_priority(new_invoice: InvoiceLike) -> Callable[[InvoiceLike], tuple[int, timedelta, int]]:
    # Point the flag at the match that matters most: an already PAID one first (paying
    # twice is the costly mistake), then the one closest in time, then the oldest id.
    def key(other: InvoiceLike) -> tuple[int, timedelta, int]:
        return (
            0 if other.status == InvoiceStatus.PAID else 1,
            abs(new_invoice.submitted_at - other.submitted_at),
            other.id,
        )

    return key


def detect_flags(
    new_invoice: InvoiceLike,
    supplier_invoices: Iterable[InvoiceLike],
    po: PurchaseOrderLike,
    po_invoices: Iterable[InvoiceLike],
) -> list[FlagDraft]:
    """Decide which review flags a newly created invoice needs.

    ``supplier_invoices`` and ``po_invoices`` may include ``new_invoice`` itself; it is
    handled correctly either way. At most one flag per rule is raised, pointing at the
    most important related invoice, so finance sees one clear question per concern.

    * ``POSSIBLE_DUPLICATE``: see :func:`find_possible_duplicates`.
    * ``PO_OVER_INVOICED``: all live invoices on the PO, including this one, add up to
      more than the PO. Each invoice alone passed the hard check, but together they
      bill more than was ordered. Rejected invoices do not count.
    """
    flags: list[FlagDraft] = []

    matches = sorted(
        find_possible_duplicates(new_invoice, supplier_invoices), key=_duplicate_priority(new_invoice)
    )
    if matches:
        best = matches[0]
        if best.status == InvoiceStatus.PAID:
            state = "which is already PAID"
        else:
            state = f"which is {best.status} and not yet paid"
        message = (
            f"Same supplier and amount ({format_rand(new_invoice.amount)}) as {best.invoice_number}, {state}."
        )
        if len(matches) > 1:
            others = ", ".join(m.invoice_number for m in matches[1:])
            message += f" Also matches: {others}."
        flags.append(FlagDraft(FlagRule.POSSIBLE_DUPLICATE, message, best.id, best.invoice_number))

    others_on_po = [i for i in po_invoices if i.id != new_invoice.id]
    total = invoiced_amount([*others_on_po, new_invoice])
    if total > po.amount:
        flags.append(
            FlagDraft(
                FlagRule.PO_OVER_INVOICED,
                f"Invoices on {po.po_number} now total {format_rand(total)}, which is "
                f"{format_rand(total - po.amount)} more than the PO amount of {format_rand(po.amount)}.",
            )
        )
    return flags


def invoiced_amount(po_invoices: Iterable[InvoiceLike]) -> Decimal:
    """Sum of live (non-rejected) invoices on a PO."""
    return sum((i.amount for i in po_invoices if i.status in LIVE_STATUSES), Decimal("0"))


# ---------------------------------------------------------------------------
# 3.3 Status lifecycle
# ---------------------------------------------------------------------------


def check_transition(action: InvoiceAction, current: InvoiceStatus) -> Rejection | None:
    """Refuse an action that the lifecycle table does not allow from ``current``."""
    allowed_from, target = TRANSITIONS[action]
    if current in allowed_from:
        return None
    allowed = " or ".join(sorted(allowed_from))
    return Rejection(
        ErrorCode.INVALID_STATUS_TRANSITION,
        f"Cannot {action.lower()} an invoice that is {current}; it must be {allowed}.",
    )


def target_status(action: InvoiceAction) -> InvoiceStatus:
    return TRANSITIONS[action][1]


def check_approval_gate(flag_statuses: Iterable[FlagStatus]) -> Rejection | None:
    """Approval waits until every flag on the invoice has been reviewed and cleared.

    This is a pause, not a penalty: as soon as a finance officer clears the flag the
    invoice can be approved. A CONFIRMED flag keeps blocking, because the reviewer has
    agreed there is a real problem; the next step for that invoice is rejection.
    """
    blocking = [s for s in flag_statuses if s in BLOCKING_FLAG_STATUSES]
    if not blocking:
        return None
    open_count = sum(1 for s in blocking if s == FlagStatus.OPEN)
    confirmed_count = len(blocking) - open_count
    parts = []
    if open_count:
        parts.append(f"{open_count} flag(s) still need review")
    if confirmed_count:
        parts.append(f"{confirmed_count} flag(s) were confirmed as a problem (reject instead)")
    return Rejection(ErrorCode.FLAGS_UNRESOLVED, "Cannot approve yet: " + "; ".join(parts) + ".")


def check_flag_resolvable(status: FlagStatus) -> Rejection | None:
    """A flag is reviewed once. Re-deciding would silently rewrite the review history."""
    if status == FlagStatus.OPEN:
        return None
    return Rejection(ErrorCode.FLAG_ALREADY_RESOLVED, f"This flag was already reviewed ({status}).")


# ---------------------------------------------------------------------------
# 3.4 Ageing and overdue (computed on read, never stored)
# ---------------------------------------------------------------------------


def whole_days(start: datetime, end: datetime) -> int:
    """Completed 24-hour days between two moments (never negative)."""
    return max(0, (end - start).days)


def ageing_bucket(days: int) -> str:
    for label, low, high in AGEING_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    raise ValueError(f"no bucket for {days} days")  # unreachable for days >= 0


def compute_ageing(
    status: InvoiceStatus,
    submitted_at: datetime,
    paid_at: datetime | None,
    now: datetime,
    payment_terms_days: int = PAYMENT_TERMS_DAYS,
) -> Ageing:
    """How long the supplier has waited, and whether that breaks payment terms.

    Computed every time, never stored, so it is always true for "now" and never goes
    stale. For an open invoice the clock is still running; for a paid invoice the
    number is the payment turnaround (submitted to paid); a rejected invoice has no
    age because nobody owes anything on it.
    """
    if status in OPEN_STATUSES:
        days = whole_days(submitted_at, now)
        return Ageing(
            days_outstanding=days,
            is_overdue=days > payment_terms_days,
            is_due_soon=DUE_SOON_FROM_DAYS <= days <= payment_terms_days,
            ageing_bucket=ageing_bucket(days),
        )
    if status == InvoiceStatus.PAID and paid_at is not None:
        return Ageing(whole_days(submitted_at, paid_at), False, False, None)
    return Ageing(None, False, False, None)


# ---------------------------------------------------------------------------
# Attention list and dashboard
# ---------------------------------------------------------------------------


def needs_attention(status: InvoiceStatus, is_overdue: bool, open_flag_count: int) -> bool:
    """Open invoices that are overdue or waiting on a flag review.

    Flagged invoices are listed even when not yet overdue, so a flag can never quietly
    freeze a payment: someone has to look at it.
    """
    return status in OPEN_STATUSES and (is_overdue or open_flag_count > 0)


def attention_sort_key(
    days_outstanding: int | None, supplier_type: SupplierType, invoice_number: str
) -> tuple[int, int, str]:
    """Longest wait first; on a tie, SMMEs first; then by invoice number for a stable order.

    SMMEs come first on ties because late payment hurts a small business's cash flow
    most, which is the problem the case study is about.
    """
    days = days_outstanding if days_outstanding is not None else -1
    return (-days, 0 if supplier_type == SupplierType.SMME else 1, invoice_number)


def round_1dp(value: Decimal) -> Decimal:
    """Round half up to one decimal place (11.65 -> 11.7), as people expect on a report."""
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def percentage(part: Decimal, total: Decimal) -> Decimal:
    """``part`` as a percentage of ``total``, one decimal place. 0 when there is no total."""
    if total == 0:
        return Decimal("0.0")
    return round_1dp(part * 100 / total)


def average_days(days: Sequence[int]) -> Decimal | None:
    """Mean of whole-day values, one decimal place; ``None`` when there is nothing to average."""
    if not days:
        return None
    return round_1dp(Decimal(sum(days)) / Decimal(len(days)))


def sum_by[K: Hashable](
    items: Iterable[Any], key: Callable[[Any], K], amount: Callable[[Any], Decimal]
) -> dict[K, Decimal]:
    """Group and add up money, keeping first-seen order of keys."""
    totals: dict[K, Decimal] = {}
    for item in items:
        k = key(item)
        totals[k] = totals.get(k, Decimal("0")) + amount(item)
    return totals


def ageing_summary(open_items: Iterable[tuple[str, Decimal]]) -> list[tuple[str, int, Decimal]]:
    """Count and amount per ageing bucket, always listing all four buckets in order.

    ``open_items`` is ``(bucket, amount)`` for each open invoice. Empty buckets are
    kept (count 0) so the chart always shows the same four bars.
    """
    counts = {label: 0 for label, _, _ in AGEING_BUCKETS}
    amounts = {label: Decimal("0") for label, _, _ in AGEING_BUCKETS}
    for bucket, amount in open_items:
        counts[bucket] += 1
        amounts[bucket] += amount
    return [(label, counts[label], amounts[label]) for label, _, _ in AGEING_BUCKETS]
