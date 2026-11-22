"""Database tables (SQLAlchemy 2 typed models).

Portability notes (SQLite by default, PostgreSQL in Docker):
* Money is ``Numeric(14, 2)`` and handled as ``Decimal`` in Python, never float.
* Timestamps go through :class:`UTCDateTime`, which always stores UTC and always gives
  back a timezone-aware UTC datetime. SQLite has no timezone support of its own.
* Enums are stored as short strings (no native database enum types), so a new value
  needs no database migration and both databases behave the same.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    TypeDecorator,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.enums import (
    AuditAction,
    FlagRule,
    FlagStatus,
    InvoiceStatus,
    Role,
    SupplierStatus,
    SupplierType,
)


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp that is always UTC and always timezone-aware in Python."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime given; use timezone-aware UTC datetimes")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        # SQLite returns naive values (stored as UTC above); PostgreSQL returns aware ones.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _enum(enum_cls: type[StrEnum]) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )


Money = Numeric(14, 2, asdecimal=True)


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    province: Mapped[str] = mapped_column(String(3))
    supplier_type: Mapped[SupplierType] = mapped_column(_enum(SupplierType))
    bbbee_level: Mapped[int] = mapped_column(Integer)
    status: Mapped[SupplierStatus] = mapped_column(_enum(SupplierStatus))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(_enum(Role))
    # Set only for SUPPLIER users: the one supplier this login acts for.
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)

    supplier: Mapped[Supplier | None] = relationship()


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(20), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    category: Mapped[str] = mapped_column(String(60))
    department: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Money)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    supplier: Mapped[Supplier] = relationship()
    invoices: Mapped[list[Invoice]] = relationship(back_populates="po", order_by="Invoice.id")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stored trimmed, as the supplier typed it. Duplicate checks compare a normalised
    # copy (trimmed + upper-case) in rules.py. There is no unique index because a
    # number may be reused after rejection, and partial unique indexes are not portable.
    invoice_number: Mapped[str] = mapped_column(String(50))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    invoice_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus))
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    supplier: Mapped[Supplier] = relationship()
    po: Mapped[PurchaseOrder] = relationship(back_populates="invoices")
    flags: Mapped[list[Flag]] = relationship(
        back_populates="invoice", order_by="Flag.id", foreign_keys="Flag.invoice_id"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(order_by="AuditEvent.id")


class Flag(Base):
    """A review flag: something unusual a finance officer should look at. Never an accusation."""

    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    rule: Mapped[FlagRule] = mapped_column(_enum(FlagRule))
    message: Mapped[str] = mapped_column(String(500))
    related_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    status: Mapped[FlagStatus] = mapped_column(_enum(FlagStatus))
    raised_at: Mapped[datetime] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="flags", foreign_keys=[invoice_id])
    related_invoice: Mapped[Invoice | None] = relationship(foreign_keys=[related_invoice_id])
    resolved_by: Mapped[User | None] = relationship()


class AuditEvent(Base):
    """One line of an invoice's history. Insert-only: see the guard below."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    at: Mapped[datetime] = mapped_column(UTCDateTime)
    # A person did it (actor_user_id), or the system did (system_actor names which part,
    # e.g. "System import" for seeded history, "Automatic check" for flags).
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    system_actor: Mapped[str | None] = mapped_column(String(60), nullable=True)
    action: Mapped[AuditAction] = mapped_column(_enum(AuditAction))
    from_status: Mapped[InvoiceStatus | None] = mapped_column(_enum(InvoiceStatus), nullable=True)
    to_status: Mapped[InvoiceStatus | None] = mapped_column(_enum(InvoiceStatus), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    actor: Mapped[User | None] = relationship()


@event.listens_for(Session, "before_flush")
def _audit_is_insert_only(session: Session, flush_context: object, instances: object) -> None:
    """Refuse any change or deletion of an audit event, whatever code path tries it.

    The audit trail is evidence of who did what. If it could be edited it would prove
    nothing, so the application can only ever add to it.
    """
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, AuditEvent) and (obj in session.deleted or session.is_modified(obj)):
            raise PermissionError("Audit events are insert-only and cannot be changed or deleted.")
