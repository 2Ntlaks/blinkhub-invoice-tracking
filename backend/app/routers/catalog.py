"""Suppliers and purchase orders (read-only reference data)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import any_user, get_session, internal_staff
from app.db import is_valid_id
from app.models import PurchaseOrder, Supplier, User
from app.schemas import PurchaseOrderOut, SupplierOut
from app.services import is_supplier, purchase_order_out

router = APIRouter(tags=["reference data"])


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    _: User = Depends(internal_staff), session: Session = Depends(get_session)
) -> list[SupplierOut]:
    return [SupplierOut.model_validate(s) for s in session.scalars(select(Supplier).order_by(Supplier.id))]


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
def list_purchase_orders(
    supplier_id: int | None = Query(default=None),
    user: User = Depends(any_user),
    session: Session = Depends(get_session),
) -> list[PurchaseOrderOut]:
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.invoices))
        .order_by(PurchaseOrder.id)
    )
    if is_supplier(user):
        # A supplier only ever sees their own POs. Asking for someone else's id just
        # gives an empty list, which reveals nothing.
        query = query.where(PurchaseOrder.supplier_id == user.supplier_id)
    if supplier_id is not None:
        if not is_valid_id(supplier_id):
            return []
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    return [purchase_order_out(po) for po in session.scalars(query)]
