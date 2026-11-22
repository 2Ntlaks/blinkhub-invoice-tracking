"""Use cases: load records, call the rules, store the outcome, shape the response.

Rules (``app.rules``) decide; this module only gathers facts for them and writes down
what they decided. Every status change and every flag decision adds an audit event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app import rules
from app.db import is_valid_id
from app.enums import (
    AuditAction,
    ErrorCode,
    FlagStatus,
    InvoiceAction,
    InvoiceStatus,
    Role,
    SupplierType,
)
from app.errors import AppError
from app.models import AuditEvent, Flag, Invoice, PurchaseOrder, Supplier, User
from app.schemas import (
    ActorOut,
    AgeingBucketOut,
    AuditEventOut,
    DashboardKpis,
    DashboardOut,
    DepartmentSpendOut,
    FlagOut,
    InvoiceDetailOut,
    InvoiceOut,
    InvoicePoRef,
    InvoiceSupplierRef,
    PersonRef,
    PurchaseOrderOut,
    SmmeShareOut,
    SupplierSpendOut,
    UserOut,
)

#: Actor names for events no person performed.
SYSTEM_IMPORT = "System import"
AUTOMATIC_CHECK = "Automatic check"

#: Audit actions a supplier never sees (contract: suppliers never see flags).
FLAG_ACTIONS = frozenset({AuditAction.FLAG_RAISED, AuditAction.FLAG_CLEARED, AuditAction.FLAG_CONFIRMED})


def is_supplier(user: User) -> bool:
    return user.role == Role.SUPPLIER


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _invoice_query() -> Select[tuple[Invoice]]:
    return select(Invoice).options(
        selectinload(Invoice.supplier),
        selectinload(Invoice.po),
        selectinload(Invoice.flags).selectinload(Flag.related_invoice),
        selectinload(Invoice.flags).selectinload(Flag.resolved_by),
        selectinload(Invoice.audit_events).selectinload(AuditEvent.actor),
    )


def load_invoices(session: Session, user: User) -> list[Invoice]:
    """All invoices this user may see: a supplier sees only their own."""
    query = _invoice_query().order_by(Invoice.id)
    if is_supplier(user):
        query = query.where(Invoice.supplier_id == user.supplier_id)
    return list(session.scalars(query))


def get_visible_invoice(session: Session, user: User, invoice_id: int) -> Invoice:
    """The invoice, or 404. Another supplier's invoice is also a 404, so its existence is not revealed."""
    if not is_valid_id(invoice_id):
        raise AppError(ErrorCode.NOT_FOUND, f"Invoice {invoice_id} not found.")
    invoice = session.scalars(_invoice_query().where(Invoice.id == invoice_id)).first()
    if invoice is None or (is_supplier(user) and invoice.supplier_id != user.supplier_id):
        raise AppError(ErrorCode.NOT_FOUND, f"Invoice {invoice_id} not found.")
    return invoice


def open_flag_count(invoice: Invoice) -> int:
    return sum(1 for f in invoice.flags if rules.is_open_review_flag(f.status, invoice.status))


# ---------------------------------------------------------------------------
# Shaping responses
# ---------------------------------------------------------------------------


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        role=user.role,
        supplier_id=user.supplier_id,
        supplier_status=user.supplier.status if user.supplier is not None else None,
    )


def invoice_out(invoice: Invoice, viewer: User, now: datetime) -> InvoiceOut:
    return InvoiceOut(**_invoice_fields(invoice, viewer, now))


def _invoice_fields(invoice: Invoice, viewer: User, now: datetime) -> dict[str, object]:
    ageing = rules.compute_ageing(invoice.status, invoice.submitted_at, invoice.paid_at, now)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "supplier": InvoiceSupplierRef.model_validate(invoice.supplier),
        "po": InvoicePoRef.model_validate(invoice.po),
        "amount": invoice.amount,
        "invoice_date": invoice.invoice_date,
        "submitted_at": invoice.submitted_at,
        "status": invoice.status,
        "days_outstanding": ageing.days_outstanding,
        "is_overdue": ageing.is_overdue,
        "is_due_soon": ageing.is_due_soon,
        "ageing_bucket": ageing.ageing_bucket,
        "open_flag_count": None if is_supplier(viewer) else open_flag_count(invoice),
        "approved_at": invoice.approved_at,
        "paid_at": invoice.paid_at,
        "payment_reference": invoice.payment_reference,
        "rejection_reason": invoice.rejection_reason,
        "is_synthetic": invoice.is_synthetic,
    }


def invoice_detail_out(invoice: Invoice, viewer: User, now: datetime) -> InvoiceDetailOut:
    supplier_view = is_supplier(viewer)
    events = [e for e in invoice.audit_events if not (supplier_view and e.action in FLAG_ACTIONS)]
    return InvoiceDetailOut(
        **_invoice_fields(invoice, viewer, now),
        description=invoice.description,
        flags=[] if supplier_view else [flag_out(f) for f in invoice.flags],
        audit=[audit_out(e, supplier_view) for e in events],
    )


def flag_out(flag: Flag) -> FlagOut:
    return FlagOut(
        id=flag.id,
        invoice_id=flag.invoice_id,
        invoice_number=flag.invoice.invoice_number,
        supplier_name=flag.invoice.supplier.name,
        rule=flag.rule,
        message=flag.message,
        related_invoice_id=flag.related_invoice_id,
        related_invoice_number=flag.related_invoice.invoice_number if flag.related_invoice else None,
        status=flag.status,
        raised_at=flag.raised_at,
        resolved_at=flag.resolved_at,
        resolved_by=PersonRef.model_validate(flag.resolved_by) if flag.resolved_by else None,
        resolution_note=flag.resolution_note,
    )


def audit_out(event: AuditEvent, supplier_view: bool) -> AuditEventOut:
    if event.actor is not None:
        actor = ActorOut(id=event.actor.id, name=event.actor.name, role=event.actor.role)
    else:
        actor = ActorOut(id=0, name=event.system_actor or SYSTEM_IMPORT, role="SYSTEM")
    # Suppliers see the rejection reason (it tells them what to fix) but not internal notes.
    note = event.note
    if supplier_view and event.action != AuditAction.REJECTED:
        note = None
    return AuditEventOut(
        id=event.id,
        at=event.at,
        actor=actor,
        action=event.action,
        from_status=event.from_status,
        to_status=event.to_status,
        note=note,
    )


def purchase_order_out(po: PurchaseOrder) -> PurchaseOrderOut:
    invoiced = rules.invoiced_amount(po.invoices)
    return PurchaseOrderOut(
        id=po.id,
        po_number=po.po_number,
        supplier_id=po.supplier_id,
        supplier_name=po.supplier.name,
        category=po.category,
        department=po.department,
        amount=po.amount,
        invoiced_amount=invoiced,
        remaining_amount=po.amount - invoiced,
        is_synthetic=po.is_synthetic,
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvoiceFilters:
    status: InvoiceStatus | None = None
    supplier_id: int | None = None
    overdue: bool = False
    flagged: bool = False
    sort: str = "age_desc"


def list_invoices(session: Session, user: User, now: datetime, filters: InvoiceFilters) -> list[InvoiceOut]:
    items = [invoice_out(i, user, now) for i in load_invoices(session, user)]
    if filters.status is not None:
        items = [i for i in items if i.status == filters.status]
    if filters.supplier_id is not None:
        items = [i for i in items if i.supplier.id == filters.supplier_id]
    if filters.overdue:
        items = [i for i in items if i.is_overdue]
    # Suppliers never see flags, so for them the flagged filter is ignored rather than
    # answered (an answer would reveal which of their invoices are flagged).
    if filters.flagged and not is_supplier(user):
        items = [i for i in items if (i.open_flag_count or 0) > 0]
    return sort_invoices(items, filters.sort)


def sort_invoices(items: list[InvoiceOut], sort: str) -> list[InvoiceOut]:
    if sort == "amount_desc":
        return sorted(items, key=lambda i: (-i.amount, i.invoice_number))
    if sort == "submitted_desc":
        return sorted(items, key=lambda i: (i.submitted_at, i.id), reverse=True)
    return sorted(
        items,
        key=lambda i: rules.attention_sort_key(
            i.days_outstanding, i.supplier.supplier_type, i.invoice_number
        ),
    )


# ---------------------------------------------------------------------------
# Creating an invoice (used by the API and by the seed script)
# ---------------------------------------------------------------------------


def create_invoice(
    session: Session,
    *,
    supplier: Supplier,
    po_id: int,
    invoice_number: str,
    amount: Decimal,
    invoice_date: date,
    description: str | None,
    submitted_at: datetime,
    actor: User | None,
    system_actor: str | None,
    flag_actor: str,
) -> Invoice:
    """Run the hard checks, create the invoice, then raise any review flags.

    Raises :class:`AppError` for a hard-check failure; nothing is written in that case.
    """
    po = session.get(PurchaseOrder, po_id) if is_valid_id(po_id) else None
    supplier_invoices = list(session.scalars(select(Invoice).where(Invoice.supplier_id == supplier.id)))
    rejection = rules.check_submission(
        invoice_number=invoice_number,
        amount=amount,
        invoice_date=invoice_date,
        now=submitted_at,
        supplier=supplier,
        requested_po_id=po_id,
        po=po,
        supplier_invoices=supplier_invoices,
    )
    if rejection is not None:
        raise AppError.from_rejection(rejection)
    assert po is not None  # check_submission returns PO_NOT_FOUND otherwise

    invoice = Invoice(
        invoice_number=invoice_number.strip(),
        supplier_id=supplier.id,
        po_id=po.id,
        amount=amount,
        invoice_date=invoice_date,
        description=description.strip() if description and description.strip() else None,
        status=InvoiceStatus.SUBMITTED,
        submitted_at=submitted_at,
        is_synthetic=False,
    )
    session.add(invoice)
    session.flush()  # assigns invoice.id, needed by the flag rules and audit events
    _add_event(
        session,
        invoice,
        submitted_at,
        actor,
        system_actor,
        AuditAction.SUBMITTED,
        None,
        InvoiceStatus.SUBMITTED,
    )

    po_invoices = list(session.scalars(select(Invoice).where(Invoice.po_id == po.id)))
    for draft in rules.detect_flags(invoice, supplier_invoices, po, po_invoices):
        invoice.flags.append(
            Flag(
                rule=draft.rule,
                message=draft.message,
                related_invoice_id=draft.related_invoice_id,
                status=FlagStatus.OPEN,
                raised_at=submitted_at,
            )
        )
        _add_event(
            session,
            invoice,
            submitted_at,
            None,
            flag_actor,
            AuditAction.FLAG_RAISED,
            None,
            None,
            draft.message,
        )
    session.flush()
    return invoice


def _add_event(
    session: Session,
    invoice: Invoice,
    at: datetime,
    actor: User | None,
    system_actor: str | None,
    action: AuditAction,
    from_status: InvoiceStatus | None,
    to_status: InvoiceStatus | None,
    note: str | None = None,
) -> None:
    # Appended through the relationship so the invoice already in memory shows the new
    # event when the response is built straight after the commit.
    invoice.audit_events.append(
        AuditEvent(
            at=at,
            actor_user_id=actor.id if actor else None,
            system_actor=None if actor else system_actor,
            action=action,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
    )


def submit_invoice(
    session: Session,
    user: User,
    *,
    invoice_number: str,
    po_id: int,
    amount: Decimal,
    invoice_date: date,
    description: str | None,
    now: datetime,
) -> int:
    supplier = session.get(Supplier, user.supplier_id) if user.supplier_id is not None else None
    if supplier is None:  # a SUPPLIER user always has a supplier; guard against bad data
        raise AppError(ErrorCode.FORBIDDEN, "This user is not linked to a supplier.")
    invoice = create_invoice(
        session,
        supplier=supplier,
        po_id=po_id,
        invoice_number=invoice_number,
        amount=amount,
        invoice_date=invoice_date,
        description=description,
        submitted_at=now,
        actor=user,
        system_actor=None,
        flag_actor=AUTOMATIC_CHECK,
    )
    session.commit()
    return invoice.id


# ---------------------------------------------------------------------------
# Finance actions
# ---------------------------------------------------------------------------


def apply_action(
    session: Session,
    user: User,
    invoice_id: int,
    action: InvoiceAction,
    now: datetime,
    *,
    note: str | None = None,
    reason: str | None = None,
    payment_reference: str | None = None,
) -> None:
    """Approve, reject or pay an invoice, after the lifecycle and flag rules agree."""
    invoice = get_visible_invoice(session, user, invoice_id)
    rejection = rules.check_transition(action, invoice.status)
    if rejection is None and action == InvoiceAction.APPROVE:
        rejection = rules.check_approval_gate(f.status for f in invoice.flags)
    if rejection is not None:
        raise AppError.from_rejection(rejection)

    from_status = invoice.status
    invoice.status = rules.target_status(action)
    if action == InvoiceAction.APPROVE:
        invoice.approved_at = now
        event_note = note.strip() if note and note.strip() else None
        audit_action = AuditAction.APPROVED
    elif action == InvoiceAction.REJECT:
        invoice.rejection_reason = reason
        event_note = reason
        audit_action = AuditAction.REJECTED
    else:
        invoice.paid_at = now
        invoice.payment_reference = payment_reference
        event_note = f"Payment reference {payment_reference}"
        audit_action = AuditAction.PAID
    _add_event(session, invoice, now, user, None, audit_action, from_status, invoice.status, event_note)
    session.commit()


def list_flags(session: Session, status: FlagStatus | None) -> list[FlagOut]:
    query = (
        select(Flag)
        .options(
            selectinload(Flag.invoice).selectinload(Invoice.supplier),
            selectinload(Flag.related_invoice),
            selectinload(Flag.resolved_by),
        )
        .order_by(Flag.raised_at, Flag.id)
    )
    if status is not None:
        query = query.where(Flag.status == status)
    # Contract section 3.5: OPEN flags on REJECTED/PAID invoices are history, not open review work.
    flags = [
        f
        for f in session.scalars(query)
        if f.status != FlagStatus.OPEN or rules.is_open_review_flag(f.status, f.invoice.status)
    ]
    return [flag_out(f) for f in flags]


def resolve_flag(
    session: Session, user: User, flag_id: int, outcome: FlagStatus, note: str, now: datetime
) -> FlagOut:
    flag = session.get(Flag, flag_id) if is_valid_id(flag_id) else None
    if flag is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Flag {flag_id} not found.")
    rejection = rules.check_flag_resolvable(flag.status, flag.invoice.status)
    if rejection is not None:
        raise AppError.from_rejection(rejection)
    flag.status = outcome
    flag.resolved_at = now
    flag.resolved_by_id = user.id
    flag.resolution_note = note
    action = AuditAction.FLAG_CLEARED if outcome == FlagStatus.CLEARED else AuditAction.FLAG_CONFIRMED
    _add_event(session, flag.invoice, now, user, None, action, None, None, note)
    session.commit()
    session.refresh(flag)
    return flag_out(flag)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def build_dashboard(session: Session, user: User, now: datetime, payment_terms_days: int) -> DashboardOut:
    invoices = load_invoices(session, user)
    pos = list(session.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier))))
    items = [invoice_out(i, user, now) for i in invoices]

    open_items = [i for i in items if i.status in rules.OPEN_STATUSES]
    overdue = [i for i in open_items if i.is_overdue]
    paid_days = [
        i.days_outstanding for i in items if i.status == InvoiceStatus.PAID and i.days_outstanding is not None
    ]
    # Contract section 3.5: open_flag_count already counts only OPEN flags on SUBMITTED/APPROVED invoices.
    open_flags = sum(open_flag_count(i) for i in invoices)

    # Spend = committed PO value (assumption A6), which is the case study's R4,027,000.
    total_spend = sum((po.amount for po in pos), Decimal("0"))
    smme_spend = sum(
        (po.amount for po in pos if po.supplier.supplier_type == SupplierType.SMME), Decimal("0")
    )
    smme_pct = rules.percentage(smme_spend, total_spend)

    by_supplier = rules.sum_by(pos, key=lambda po: po.supplier_id, amount=lambda po: po.amount)
    suppliers = {po.supplier_id: po.supplier for po in pos}
    spend_by_supplier = sorted(
        (
            SupplierSpendOut(
                supplier_id=sid,
                name=suppliers[sid].name,
                supplier_type=suppliers[sid].supplier_type,
                amount=amount,
            )
            for sid, amount in by_supplier.items()
        ),
        key=lambda s: (-s.amount, s.name),
    )
    by_department = rules.sum_by(pos, key=lambda po: po.department, amount=lambda po: po.amount)
    spend_by_department = sorted(
        (DepartmentSpendOut(department=d, amount=a) for d, a in by_department.items()),
        key=lambda d: (-d.amount, d.department),
    )

    ageing = [
        AgeingBucketOut(bucket=b, count=c, amount=a)
        for b, c, a in rules.ageing_summary((i.ageing_bucket or "0-30", i.amount) for i in open_items)
    ]
    attention = sort_invoices(
        [i for i in items if rules.needs_attention(i.status, i.is_overdue, i.open_flag_count or 0)],
        "age_desc",
    )

    return DashboardOut(
        as_of=now,
        payment_terms_days=payment_terms_days,
        kpis=DashboardKpis(
            outstanding_count=len(open_items),
            outstanding_amount=sum((i.amount for i in open_items), Decimal("0")),
            overdue_count=len(overdue),
            overdue_amount=sum((i.amount for i in overdue), Decimal("0")),
            due_soon_count=sum(1 for i in open_items if i.is_due_soon),
            avg_payment_turnaround_days=rules.average_days(paid_days),
            open_flag_count=open_flags,
            smme_spend_share_pct=smme_pct,
        ),
        ageing=ageing,
        spend_by_supplier=spend_by_supplier,
        spend_by_department=spend_by_department,
        smme_share=SmmeShareOut(smme_amount=smme_spend, total_amount=total_spend, pct=smme_pct),
        attention=attention,
    )
