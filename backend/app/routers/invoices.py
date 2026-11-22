"""Invoices: list, detail, submit (supplier) and approve / reject / pay (finance)."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import services
from app.auth import any_user, finance_only, get_now, get_session, supplier_only
from app.enums import InvoiceAction, InvoiceStatus
from app.models import User
from app.schemas import (
    ApproveRequest,
    InvoiceCreate,
    InvoiceDetailOut,
    InvoiceOut,
    PayRequest,
    RejectRequest,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _detail(session: Session, user: User, invoice_id: int, now: datetime) -> InvoiceDetailOut:
    # Start from fresh rows so the response shows exactly what was committed.
    session.expire_all()
    return services.invoice_detail_out(services.get_visible_invoice(session, user, invoice_id), user, now)


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status: InvoiceStatus | None = Query(default=None),
    supplier_id: int | None = Query(default=None),
    overdue: bool = Query(default=False, description="true: only invoices past payment terms"),
    flagged: bool = Query(default=False, description="true: only invoices with an OPEN flag (staff only)"),
    sort: Literal["age_desc", "amount_desc", "submitted_desc"] = Query(default="age_desc"),
    user: User = Depends(any_user),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> list[InvoiceOut]:
    filters = services.InvoiceFilters(
        status=status, supplier_id=supplier_id, overdue=overdue, flagged=flagged, sort=sort
    )
    return services.list_invoices(session, user, now, filters)


@router.post("", response_model=InvoiceDetailOut, status_code=201)
def submit_invoice(
    body: InvoiceCreate,
    user: User = Depends(supplier_only),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvoiceDetailOut:
    invoice_id = services.submit_invoice(
        session,
        user,
        invoice_number=body.invoice_number,
        po_id=body.po_id,
        amount=body.amount,
        invoice_date=body.invoice_date,
        description=body.description,
        now=now,
    )
    return _detail(session, user, invoice_id, now)


@router.get("/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(
    invoice_id: int,
    user: User = Depends(any_user),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvoiceDetailOut:
    return services.invoice_detail_out(services.get_visible_invoice(session, user, invoice_id), user, now)


@router.post("/{invoice_id}/approve", response_model=InvoiceDetailOut)
def approve_invoice(
    invoice_id: int,
    body: ApproveRequest | None = None,
    user: User = Depends(finance_only),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvoiceDetailOut:
    note = body.note if body else None
    services.apply_action(session, user, invoice_id, InvoiceAction.APPROVE, now, note=note)
    return _detail(session, user, invoice_id, now)


@router.post("/{invoice_id}/reject", response_model=InvoiceDetailOut)
def reject_invoice(
    invoice_id: int,
    body: RejectRequest,
    user: User = Depends(finance_only),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvoiceDetailOut:
    services.apply_action(session, user, invoice_id, InvoiceAction.REJECT, now, reason=body.reason)
    return _detail(session, user, invoice_id, now)


@router.post("/{invoice_id}/pay", response_model=InvoiceDetailOut)
def pay_invoice(
    invoice_id: int,
    body: PayRequest,
    user: User = Depends(finance_only),
    session: Session = Depends(get_session),
    now: datetime = Depends(get_now),
) -> InvoiceDetailOut:
    services.apply_action(
        session, user, invoice_id, InvoiceAction.PAY, now, payment_reference=body.payment_reference
    )
    return _detail(session, user, invoice_id, now)
