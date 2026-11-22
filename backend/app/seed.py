"""Load the case-study sample data (docs/data-assumptions.md).

Run from ``backend/``::

    python -m app.seed --reset     # drop all tables, recreate, seed (do this before the demo)
    python -m app.seed             # seed only if the database has no suppliers yet

Invoices go through :func:`app.services.create_invoice`, the same code path as a real
submission, in invoice-number order. So the four review flags in the demo are raised by
the real rules, not typed in by hand.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import make_engine, make_session_factory, utc_now
from app.enums import AuditAction, InvoiceStatus, Role, SupplierStatus, SupplierType
from app.models import AuditEvent, Base, Invoice, PurchaseOrder, Supplier, User
from app.rules import business_today
from app.services import SYSTEM_IMPORT, create_invoice

logger = logging.getLogger("blinkhub.seed")

# Supplier register, in case-study order (ids 1..8). Provinces use assumption A7 codes.
SUPPLIERS = [
    ("Ubuntu Cleaning", "GP", SupplierType.SMME, 1, SupplierStatus.ACTIVE),
    ("Prime Facilities", "GP", SupplierType.LARGE, 2, SupplierStatus.ACTIVE),
    ("Thuto Supplies", "LP", SupplierType.SMME, 1, SupplierStatus.ACTIVE),
    ("Metro Logistics", "GP", SupplierType.LARGE, 4, SupplierStatus.ACTIVE),
    ("Khula Electrical", "MP", SupplierType.SMME, 2, SupplierStatus.ACTIVE),
    ("Rapid Transport", "KZN", SupplierType.SMME, 1, SupplierStatus.ACTIVE),
    ("Apex Infrastructure", "GP", SupplierType.LARGE, 3, SupplierStatus.ACTIVE),
    ("Sisonke Trading", "LP", SupplierType.SMME, 1, SupplierStatus.INACTIVE),
]

# Purchase orders PO001..PO012 (ids 1..12): (supplier id, category, department, amount).
PURCHASE_ORDERS = [
    (1, "Cleaning", "Facilities", "85000"),
    (2, "Cleaning", "Facilities", "450000"),
    (3, "Stationery", "Administration", "35000"),
    (4, "Transport", "Operations", "620000"),
    (5, "Maintenance", "Infrastructure", "95000"),
    (6, "Transport", "Operations", "180000"),
    (7, "Construction", "Infrastructure", "1200000"),
    (1, "Cleaning", "Facilities", "95000"),
    (2, "Cleaning", "Operations", "390000"),
    (3, "Stationery", "Administration", "42000"),
    (4, "Transport", "Operations", "710000"),
    (5, "Maintenance", "Infrastructure", "125000"),
]

# Invoices INV001..INV008 (ids 1..8): (supplier id, amount, case-study days, paid?, days ago submitted).
# Open invoices: submitted "days outstanding" ago (A3). Paid invoices: submitted on the
# assumed day (A4) and paid "days" later, so days = payment turnaround.
INVOICES = [
    (1, "85000", 15, True, 80),
    (3, "35000", 42, False, 42),
    (4, "620000", 65, False, 65),
    (5, "95000", 12, True, 70),
    (6, "180000", 38, False, 38),
    (1, "85000", 47, False, 47),
    (2, "450000", 8, True, 60),
    (3, "35000", 42, False, 42),
]

FINANCE_USER = "Thandi Nkosi"
MANAGER_USER = "Sipho Mokoena"


def _po_for(supplier_id: int, amount: Decimal, pos: list[PurchaseOrder]) -> PurchaseOrder:
    """Assumption A1: link each invoice to the supplier's first PO with exactly the same amount."""
    for po in pos:
        if po.supplier_id == supplier_id and po.amount == amount:
            return po
    raise ValueError(f"no PO for supplier {supplier_id} with amount {amount}")


def _expect_ids(rows: list, label: str) -> None:
    # The frontend and docs rely on stable ids (contract section 6). They come out right
    # on empty tables because rows are inserted in order; check rather than assume.
    ids = [r.id for r in rows]
    if ids != list(range(1, len(rows) + 1)):
        raise RuntimeError(f"{label} ids are {ids}; run `python -m app.seed --reset` for a clean database")


def seed(session: Session, now: datetime) -> None:
    """Insert the case-study data. Expects empty tables."""
    suppliers = []
    for name, province, kind, level, status in SUPPLIERS:
        s = Supplier(name=name, province=province, supplier_type=kind, bbbee_level=level, status=status)
        session.add(s)
        session.flush()
        suppliers.append(s)
    _expect_ids(suppliers, "Supplier")

    users = [User(name=FINANCE_USER, role=Role.FINANCE), User(name=MANAGER_USER, role=Role.MANAGER)]
    users += [
        User(name=f"{s.name} (supplier portal)", role=Role.SUPPLIER, supplier_id=s.id) for s in suppliers
    ]
    for u in users:
        session.add(u)
        session.flush()
    _expect_ids(users, "User")

    pos = []
    for number, (supplier_id, category, department, amount) in enumerate(PURCHASE_ORDERS, start=1):
        po = PurchaseOrder(
            po_number=f"PO{number:03d}",
            supplier_id=supplier_id,
            category=category,
            department=department,
            amount=Decimal(amount),
        )
        session.add(po)
        session.flush()
        pos.append(po)
    _expect_ids(pos, "PurchaseOrder")

    invoices = []
    for number, (supplier_id, amount, days, paid, submitted_days_ago) in enumerate(INVOICES, start=1):
        supplier = suppliers[supplier_id - 1]
        submitted_at = now - timedelta(days=submitted_days_ago)
        invoice = create_invoice(
            session,
            supplier=supplier,
            po_id=_po_for(supplier_id, Decimal(amount), pos).id,
            invoice_number=f"INV{number:03d}",
            amount=Decimal(amount),
            invoice_date=business_today(submitted_at),
            description="Imported from the case-study sample invoice records.",
            submitted_at=submitted_at,
            actor=None,
            system_actor=SYSTEM_IMPORT,
            flag_actor=SYSTEM_IMPORT,
        )
        if paid:
            _mark_imported_as_paid(invoice, submitted_at + timedelta(days=days))
        invoices.append(invoice)
    _expect_ids(invoices, "Invoice")
    session.flush()


def _mark_imported_as_paid(invoice: Invoice, paid_at: datetime) -> None:
    """Record a historical payment. The case study gives no approval date or payment
    reference, so none is invented: ``approved_at`` and ``payment_reference`` stay empty."""
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = paid_at
    invoice.audit_events.append(
        AuditEvent(
            at=paid_at,
            system_actor=SYSTEM_IMPORT,
            action=AuditAction.PAID,
            from_status=InvoiceStatus.SUBMITTED,
            to_status=InvoiceStatus.PAID,
            note="Imported as paid from the case-study records (approval date not recorded).",
        )
    )


def reset_database(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_if_empty(engine: Engine, now: datetime) -> bool:
    """Create missing tables and seed when there are no suppliers. Returns True if it seeded."""
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        if session.scalar(select(func.count()).select_from(Supplier)):
            return False
        seed(session, now)
        session.commit()
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Seed the BlinkHub database with the case-study data.")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = parser.parse_args()

    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    if args.reset:
        reset_database(engine)
        logger.info("Dropped and recreated all tables.")
    if seed_if_empty(engine, utc_now()):
        logger.info("Seeded case-study data into %s", engine.url.render_as_string(hide_password=True))
    else:
        logger.info("Database already has suppliers; nothing seeded (use --reset to start over).")
    engine.dispose()


if __name__ == "__main__":
    main()
