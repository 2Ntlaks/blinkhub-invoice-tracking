"""Unit tests for app/rules.py. No database, no web server: plain facts in, decisions out."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app import rules
from app.enums import (
    ErrorCode,
    FlagRule,
    FlagStatus,
    InvoiceAction,
    InvoiceStatus,
    SupplierStatus,
    SupplierType,
)

NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
TODAY = date(2026, 11, 22)


@dataclass
class FakeSupplier:
    id: int = 1
    name: str = "Ubuntu Cleaning"
    status: SupplierStatus = SupplierStatus.ACTIVE


@dataclass
class FakePO:
    id: int = 1
    po_number: str = "PO001"
    supplier_id: int = 1
    amount: Decimal = Decimal("85000.00")


@dataclass
class FakeInvoice:
    id: int
    invoice_number: str = "INV001"
    supplier_id: int = 1
    po_id: int = 1
    amount: Decimal = Decimal("85000.00")
    status: InvoiceStatus = InvoiceStatus.SUBMITTED
    submitted_at: datetime = field(default=NOW)


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def submit(**overrides):
    """Run the hard checks with valid defaults, overriding just what a test cares about."""
    args = dict(
        invoice_number="UBC-114",
        amount=Decimal("85000.00"),
        invoice_date=TODAY,
        now=NOW,
        supplier=FakeSupplier(),
        requested_po_id=1,
        po=FakePO(),
        supplier_invoices=[],
    )
    args.update(overrides)
    return rules.check_submission(**args)


# ---------------------------------------------------------------------------
# Invoice-number normalisation and exact duplicates
# ---------------------------------------------------------------------------


class TestInvoiceNumbers:
    def test_normalise_trims_and_upper_cases(self):
        assert rules.normalise_invoice_number("  ubc-114 \t") == "UBC-114"

    def test_duplicate_caught_despite_case_and_spaces(self):
        existing = [FakeInvoice(id=1, invoice_number="UBC-114")]
        rejection = submit(invoice_number=" ubc-114 ", supplier_invoices=existing)
        assert rejection is not None
        assert rejection.code == ErrorCode.DUPLICATE_INVOICE_NUMBER

    def test_duplicate_of_paid_invoice_is_caught(self):
        existing = [FakeInvoice(id=1, invoice_number="UBC-114", status=InvoiceStatus.PAID)]
        assert submit(invoice_number="UBC-114", supplier_invoices=existing).code == (
            ErrorCode.DUPLICATE_INVOICE_NUMBER
        )

    def test_number_can_be_reused_after_rejection(self):
        existing = [FakeInvoice(id=1, invoice_number="UBC-114", status=InvoiceStatus.REJECTED)]
        assert submit(invoice_number="UBC-114", supplier_invoices=existing) is None

    def test_different_number_is_fine(self):
        existing = [FakeInvoice(id=1, invoice_number="UBC-113")]
        assert submit(invoice_number="UBC-114", supplier_invoices=existing) is None


# ---------------------------------------------------------------------------
# Hard checks on submit
# ---------------------------------------------------------------------------


class TestHardChecks:
    def test_valid_submission_passes(self):
        assert submit() is None

    @pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1.00")])
    def test_amount_must_be_positive(self, amount):
        rejection = submit(amount=amount)
        assert rejection.code == ErrorCode.VALIDATION_ERROR
        assert rejection.details == [{"field": "amount", "message": "must be greater than 0"}]

    def test_blank_invoice_number_rejected(self):
        rejection = submit(invoice_number="   ")
        assert rejection.code == ErrorCode.VALIDATION_ERROR
        assert rejection.details[0]["field"] == "invoice_number"

    def test_future_invoice_date_rejected(self):
        rejection = submit(invoice_date=TODAY + timedelta(days=1))
        assert rejection.code == ErrorCode.VALIDATION_ERROR
        assert rejection.details[0]["field"] == "invoice_date"

    def test_today_in_south_africa_is_not_the_future(self):
        # 23:30 UTC on the 22nd is already 01:30 on the 23rd in South Africa.
        late_evening_utc = datetime(2026, 11, 22, 23, 30, tzinfo=UTC)
        assert submit(invoice_date=date(2026, 11, 23), now=late_evening_utc) is None

    def test_inactive_supplier_rejected(self):
        rejection = submit(supplier=FakeSupplier(status=SupplierStatus.INACTIVE))
        assert rejection.code == ErrorCode.SUPPLIER_INACTIVE

    def test_inactive_supplier_checked_before_po(self):
        # An inactive supplier gets the real reason, even with a PO that is not theirs.
        rejection = submit(
            supplier=FakeSupplier(id=8, status=SupplierStatus.INACTIVE), po=FakePO(supplier_id=1)
        )
        assert rejection.code == ErrorCode.SUPPLIER_INACTIVE

    def test_missing_po_rejected(self):
        rejection = submit(po=None, requested_po_id=999)
        assert rejection.code == ErrorCode.PO_NOT_FOUND
        assert "999" in rejection.message

    def test_po_of_another_supplier_rejected_without_naming_its_owner(self):
        rejection = submit(po=FakePO(id=5, po_number="PO005", supplier_id=5))
        assert rejection.code == ErrorCode.PO_SUPPLIER_MISMATCH
        assert rejection.message == "PO005 does not belong to Ubuntu Cleaning."

    def test_amount_exactly_equal_to_po_allowed(self):
        assert submit(amount=Decimal("85000.00")) is None

    def test_one_cent_over_po_rejected(self):
        rejection = submit(amount=Decimal("85000.01"))
        assert rejection.code == ErrorCode.AMOUNT_EXCEEDS_PO
        assert "R85,000.01" in rejection.message


# ---------------------------------------------------------------------------
# Soft checks: review flags
# ---------------------------------------------------------------------------


class TestPossibleDuplicate:
    def flags_for(self, new, others, po=None):
        po = po or FakePO(amount=Decimal("1000000"))  # big PO so only the duplicate rule can fire
        return rules.detect_flags(new, others, po, [])

    def test_same_amount_within_window_flagged_and_mentions_paid(self):
        paid = FakeInvoice(
            id=1, invoice_number="INV001", status=InvoiceStatus.PAID, submitted_at=days_ago(80)
        )
        new = FakeInvoice(id=6, invoice_number="INV006", submitted_at=days_ago(47))
        [flag] = self.flags_for(new, [paid])
        assert flag.rule == FlagRule.POSSIBLE_DUPLICATE
        assert flag.related_invoice_id == 1
        assert flag.message == "Same supplier and amount (R85,000.00) as INV001, which is already PAID."

    def test_message_says_when_other_is_not_yet_paid(self):
        other = FakeInvoice(id=2, invoice_number="INV002")
        [flag] = self.flags_for(FakeInvoice(id=8, invoice_number="INV008"), [other])
        assert "INV002, which is SUBMITTED and not yet paid" in flag.message

    def test_exactly_90_days_apart_is_inside_window(self):
        other = FakeInvoice(id=1, submitted_at=days_ago(90))
        assert len(self.flags_for(FakeInvoice(id=2, invoice_number="X"), [other])) == 1

    def test_just_over_90_days_apart_is_outside_window(self):
        other = FakeInvoice(id=1, submitted_at=days_ago(90) - timedelta(seconds=1))
        assert self.flags_for(FakeInvoice(id=2, invoice_number="X"), [other]) == []

    def test_rejected_invoice_is_ignored(self):
        other = FakeInvoice(id=1, status=InvoiceStatus.REJECTED)
        assert self.flags_for(FakeInvoice(id=2, invoice_number="X"), [other]) == []

    def test_different_amount_not_flagged(self):
        other = FakeInvoice(id=1, amount=Decimal("85000.01"))
        assert self.flags_for(FakeInvoice(id=2, invoice_number="X"), [other]) == []

    def test_other_supplier_not_flagged(self):
        other = FakeInvoice(id=1, supplier_id=2)
        assert self.flags_for(FakeInvoice(id=2, invoice_number="X"), [other]) == []

    def test_invoice_never_matches_itself(self):
        new = FakeInvoice(id=2)
        assert self.flags_for(new, [new]) == []

    def test_one_flag_points_at_paid_match_first_and_lists_the_rest(self):
        recent = FakeInvoice(id=3, invoice_number="INV003", submitted_at=days_ago(1))
        paid = FakeInvoice(
            id=1, invoice_number="INV001", status=InvoiceStatus.PAID, submitted_at=days_ago(60)
        )
        [flag] = self.flags_for(FakeInvoice(id=9, invoice_number="INV009"), [recent, paid])
        assert flag.related_invoice_number == "INV001"
        assert "Also matches: INV003." in flag.message


class TestPoOverInvoiced:
    def test_second_full_invoice_on_po_flagged(self):
        po = FakePO(amount=Decimal("85000"))
        first = FakeInvoice(id=1, amount=Decimal("85000"))
        new = FakeInvoice(id=6, invoice_number="INV006", amount=Decimal("85000"))
        flags = rules.detect_flags(new, [], po, [first, new])
        assert [f.rule for f in flags] == [FlagRule.PO_OVER_INVOICED]
        assert "R170,000.00" in flags[0].message
        assert "R85,000.00 more than" in flags[0].message

    def test_total_exactly_equal_to_po_not_flagged(self):
        po = FakePO(amount=Decimal("100000"))
        first = FakeInvoice(id=1, amount=Decimal("60000"))
        new = FakeInvoice(id=2, invoice_number="X", amount=Decimal("40000"))
        assert rules.detect_flags(new, [], po, [first]) == []

    def test_rejected_invoices_do_not_count_towards_po(self):
        po = FakePO(amount=Decimal("85000"))
        rejected = FakeInvoice(id=1, amount=Decimal("85000"), status=InvoiceStatus.REJECTED)
        new = FakeInvoice(id=2, invoice_number="X", amount=Decimal("85000"))
        assert rules.detect_flags(new, [], po, [rejected]) == []

    def test_both_rules_can_fire_together(self):
        po = FakePO(amount=Decimal("85000"))
        first = FakeInvoice(id=1, status=InvoiceStatus.PAID, submitted_at=days_ago(80))
        new = FakeInvoice(id=6, invoice_number="INV006", submitted_at=days_ago(47))
        rules_raised = [f.rule for f in rules.detect_flags(new, [first], po, [first])]
        assert rules_raised == [FlagRule.POSSIBLE_DUPLICATE, FlagRule.PO_OVER_INVOICED]

    def test_invoiced_amount_ignores_rejected(self):
        invoices = [
            FakeInvoice(id=1, amount=Decimal("10.50")),
            FakeInvoice(id=2, amount=Decimal("5.25"), status=InvoiceStatus.PAID),
            FakeInvoice(id=3, amount=Decimal("100"), status=InvoiceStatus.REJECTED),
        ]
        assert rules.invoiced_amount(invoices) == Decimal("15.75")


# ---------------------------------------------------------------------------
# Lifecycle and approval gate
# ---------------------------------------------------------------------------


class TestTransitions:
    @pytest.mark.parametrize(
        ("action", "current"),
        [
            (InvoiceAction.APPROVE, InvoiceStatus.SUBMITTED),
            (InvoiceAction.REJECT, InvoiceStatus.SUBMITTED),
            (InvoiceAction.REJECT, InvoiceStatus.APPROVED),
            (InvoiceAction.PAY, InvoiceStatus.APPROVED),
        ],
    )
    def test_allowed(self, action, current):
        assert rules.check_transition(action, current) is None

    @pytest.mark.parametrize(
        ("action", "current"),
        [
            (InvoiceAction.PAY, InvoiceStatus.SUBMITTED),  # must be approved first
            (InvoiceAction.REJECT, InvoiceStatus.PAID),  # money has already gone
            (InvoiceAction.APPROVE, InvoiceStatus.APPROVED),  # no double approval
            (InvoiceAction.APPROVE, InvoiceStatus.REJECTED),  # rejected is terminal
            (InvoiceAction.PAY, InvoiceStatus.PAID),  # no double payment
            (InvoiceAction.REJECT, InvoiceStatus.REJECTED),
        ],
    )
    def test_refused(self, action, current):
        rejection = rules.check_transition(action, current)
        assert rejection.code == ErrorCode.INVALID_STATUS_TRANSITION

    def test_targets(self):
        assert rules.target_status(InvoiceAction.APPROVE) == InvoiceStatus.APPROVED
        assert rules.target_status(InvoiceAction.REJECT) == InvoiceStatus.REJECTED
        assert rules.target_status(InvoiceAction.PAY) == InvoiceStatus.PAID


class TestApprovalGate:
    def test_no_flags_allows_approval(self):
        assert rules.check_approval_gate([]) is None

    def test_all_cleared_allows_approval(self):
        assert rules.check_approval_gate([FlagStatus.CLEARED, FlagStatus.CLEARED]) is None

    def test_open_flag_blocks(self):
        rejection = rules.check_approval_gate([FlagStatus.CLEARED, FlagStatus.OPEN])
        assert rejection.code == ErrorCode.FLAGS_UNRESOLVED
        assert "1 flag(s) still need review" in rejection.message

    def test_confirmed_flag_blocks(self):
        rejection = rules.check_approval_gate([FlagStatus.CONFIRMED])
        assert rejection.code == ErrorCode.FLAGS_UNRESOLVED
        assert "reject instead" in rejection.message

    def test_flag_can_be_resolved_only_once(self):
        assert rules.check_flag_resolvable(FlagStatus.OPEN) is None
        for done in (FlagStatus.CLEARED, FlagStatus.CONFIRMED):
            assert rules.check_flag_resolvable(done).code == ErrorCode.FLAG_ALREADY_RESOLVED


# ---------------------------------------------------------------------------
# Ageing
# ---------------------------------------------------------------------------


class TestAgeing:
    def age(self, days, status=InvoiceStatus.SUBMITTED, paid_after=None):
        submitted = days_ago(days)
        paid_at = submitted + timedelta(days=paid_after) if paid_after is not None else None
        return rules.compute_ageing(status, submitted, paid_at, NOW)

    def test_30_days_is_not_overdue_but_due_soon(self):
        a = self.age(30)
        assert (a.days_outstanding, a.is_overdue, a.is_due_soon, a.ageing_bucket) == (30, False, True, "0-30")

    def test_31_days_is_overdue(self):
        a = self.age(31)
        assert (a.is_overdue, a.is_due_soon, a.ageing_bucket) == (True, False, "31-60")

    def test_20_days_is_not_due_soon(self):
        assert self.age(20).is_due_soon is False

    def test_21_days_is_due_soon(self):
        assert self.age(21).is_due_soon is True

    def test_partial_days_round_down(self):
        assert self.age(30.99).days_outstanding == 30

    def test_approved_invoice_still_ages(self):
        assert self.age(40, status=InvoiceStatus.APPROVED).is_overdue is True

    def test_paid_invoice_days_are_the_turnaround(self):
        a = self.age(80, status=InvoiceStatus.PAID, paid_after=15)
        assert (a.days_outstanding, a.is_overdue, a.is_due_soon, a.ageing_bucket) == (15, False, False, None)

    def test_rejected_invoice_has_no_age(self):
        a = self.age(50, status=InvoiceStatus.REJECTED)
        assert (a.days_outstanding, a.is_overdue, a.ageing_bucket) == (None, False, None)

    @pytest.mark.parametrize(
        ("days", "bucket"),
        [(0, "0-30"), (30, "0-30"), (31, "31-60"), (60, "31-60"), (61, "61-90"), (90, "61-90"), (91, "90+")],
    )
    def test_bucket_edges(self, days, bucket):
        assert rules.ageing_bucket(days) == bucket


# ---------------------------------------------------------------------------
# Attention list and dashboard helpers
# ---------------------------------------------------------------------------


class TestAttentionAndDashboard:
    def test_needs_attention(self):
        assert rules.needs_attention(InvoiceStatus.SUBMITTED, is_overdue=True, open_flag_count=0)
        assert rules.needs_attention(InvoiceStatus.SUBMITTED, is_overdue=False, open_flag_count=1)
        assert not rules.needs_attention(InvoiceStatus.SUBMITTED, is_overdue=False, open_flag_count=0)
        assert not rules.needs_attention(InvoiceStatus.PAID, is_overdue=False, open_flag_count=1)

    def test_sort_oldest_first_then_smme_first_on_ties(self):
        rows = [
            (42, SupplierType.LARGE, "INV010"),
            (65, SupplierType.LARGE, "INV003"),
            (42, SupplierType.SMME, "INV008"),
            (42, SupplierType.SMME, "INV002"),
            (None, SupplierType.SMME, "INV099"),
        ]
        ordered = sorted(rows, key=lambda r: rules.attention_sort_key(*r))
        assert [r[2] for r in ordered] == ["INV003", "INV002", "INV008", "INV010", "INV099"]

    def test_smme_share_matches_case_study(self):
        assert rules.percentage(Decimal("657000"), Decimal("4027000")) == Decimal("16.3")

    def test_percentage_of_nothing_is_zero(self):
        assert rules.percentage(Decimal("0"), Decimal("0")) == Decimal("0.0")

    def test_average_turnaround_matches_case_study(self):
        assert rules.average_days([15, 12, 8]) == Decimal("11.7")

    def test_average_rounds_half_up(self):
        assert rules.average_days([11, 12]) == Decimal("11.5")
        assert rules.round_1dp(Decimal("11.65")) == Decimal("11.7")

    def test_average_of_nothing_is_none(self):
        assert rules.average_days([]) is None

    def test_ageing_summary_always_lists_four_buckets(self):
        summary = rules.ageing_summary([("31-60", Decimal("35000")), ("31-60", Decimal("180000"))])
        assert summary == [
            ("0-30", 0, Decimal("0")),
            ("31-60", 2, Decimal("215000")),
            ("61-90", 0, Decimal("0")),
            ("90+", 0, Decimal("0")),
        ]

    def test_sum_by_groups_money(self):
        rows = [("Ops", Decimal("1.10")), ("Admin", Decimal("2")), ("Ops", Decimal("0.20"))]
        assert rules.sum_by(rows, key=lambda r: r[0], amount=lambda r: r[1]) == {
            "Ops": Decimal("1.30"),
            "Admin": Decimal("2"),
        }

    def test_format_rand(self):
        assert rules.format_rand(Decimal("1200000")) == "R1,200,000.00"


def test_messages_never_use_accusatory_words():
    """Flags are questions for review, never accusations (UI wording rule)."""
    po = FakePO(amount=Decimal("85000"))
    first = FakeInvoice(id=1, status=InvoiceStatus.PAID, submitted_at=days_ago(80))
    new = FakeInvoice(id=6, invoice_number="INV006", submitted_at=days_ago(47))
    texts = [f.message for f in rules.detect_flags(new, [first], po, [first])]
    texts.append(rules.check_approval_gate([FlagStatus.OPEN, FlagStatus.CONFIRMED]).message)
    for text in texts:
        for word in ("fraud", "suspicious"):
            assert word not in text.lower()
