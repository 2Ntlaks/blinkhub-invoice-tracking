"""API tests: the whole stack (HTTP -> rules -> SQLite) on freshly seeded case-study data."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from conftest import FINANCE, FROZEN_NOW, MANAGER, PRIME, SISONKE, THUTO, UBUNTU
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.enums import InvoiceStatus
from app.main import create_app
from app.models import AuditEvent, Invoice

NEW_INVOICE = {
    "invoice_number": "UBC-2026-114",
    "po_id": 8,  # PO008, Ubuntu Cleaning, R95,000, nothing invoiced yet
    "amount": 95000.0,
    "invoice_date": "2026-11-20",
    "description": "Office cleaning - November",
}


def error_code(response) -> str:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]["code"]


def submit(client, headers=UBUNTU, **overrides):
    return client.post("/api/invoices", json={**NEW_INVOICE, **overrides}, headers=headers)


def flags_of(client, invoice_number):
    return [
        f for f in client.get("/api/flags", headers=FINANCE).json() if f["invoice_number"] == invoice_number
    ]


def resolve(client, flag_id, outcome, note="Checked with the supplier and the delivery notes."):
    return client.post(
        f"/api/flags/{flag_id}/resolve", json={"outcome": outcome, "note": note}, headers=FINANCE
    )


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


class TestSeed:
    def test_health_needs_no_user(self, client):
        assert client.get("/api/health").json() == {"status": "ok"}

    def test_users_have_stable_ids(self, client):
        users = client.get("/api/users").json()
        assert [u["id"] for u in users] == list(range(1, 11))
        assert users[0] == {
            "id": 1,
            "name": "Thandi Nkosi",
            "role": "FINANCE",
            "supplier_id": None,
            "supplier_status": None,
        }
        assert users[1]["role"] == "MANAGER"
        assert users[1]["supplier_status"] is None
        assert users[2] == {
            "id": 3,
            "name": "Ubuntu Cleaning (supplier portal)",
            "role": "SUPPLIER",
            "supplier_id": 1,
            "supplier_status": "ACTIVE",
        }
        assert users[9] == {
            "id": 10,
            "name": "Sisonke Trading (supplier portal)",
            "role": "SUPPLIER",
            "supplier_id": 8,
            "supplier_status": "INACTIVE",
        }

    def test_suppliers_in_case_study_order(self, client):
        suppliers = client.get("/api/suppliers", headers=FINANCE).json()
        assert [s["name"] for s in suppliers][:2] == ["Ubuntu Cleaning", "Prime Facilities"]
        assert suppliers[7]["name"] == "Sisonke Trading"
        assert suppliers[7]["status"] == "INACTIVE"

    def test_four_open_flags_raised_by_the_rules(self, client):
        flags = client.get("/api/flags", headers=FINANCE).json()
        summary = [(f["invoice_number"], f["rule"], f["related_invoice_number"], f["status"]) for f in flags]
        assert summary == [
            ("INV006", "POSSIBLE_DUPLICATE", "INV001", "OPEN"),
            ("INV006", "PO_OVER_INVOICED", None, "OPEN"),
            ("INV008", "POSSIBLE_DUPLICATE", "INV002", "OPEN"),
            ("INV008", "PO_OVER_INVOICED", None, "OPEN"),
        ]
        assert (
            flags[0]["message"] == "Same supplier and amount (R85,000.00) as INV001, which is already PAID."
        )

    def test_over_invoiced_po_shows_negative_remaining(self, client):
        po1 = client.get("/api/purchase-orders", headers=FINANCE).json()[0]
        assert (po1["po_number"], po1["amount"], po1["invoiced_amount"], po1["remaining_amount"]) == (
            "PO001",
            85000.0,
            170000.0,
            -85000.0,
        )

    def test_seeded_invoice_ages_match_case_study(self, client):
        invoices = {i["invoice_number"]: i for i in client.get("/api/invoices", headers=FINANCE).json()}
        ages = {n: i["days_outstanding"] for n, i in invoices.items()}
        assert ages == {
            "INV001": 15,
            "INV002": 42,
            "INV003": 65,
            "INV004": 12,
            "INV005": 38,
            "INV006": 47,
            "INV007": 8,
            "INV008": 42,
        }
        assert invoices["INV006"]["po"]["po_number"] == "PO001"
        assert invoices["INV001"]["status"] == "PAID"

    def test_seeded_history_is_by_system_import(self, client):
        audit = client.get("/api/invoices/6", headers=FINANCE).json()["audit"]
        assert [e["action"] for e in audit] == ["SUBMITTED", "FLAG_RAISED", "FLAG_RAISED"]
        assert audit[0]["actor"] == {"id": 0, "name": "System import", "role": "SYSTEM"}


# ---------------------------------------------------------------------------
# Dashboard: must reproduce the case-study findings exactly
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_reproduces_case_study_numbers(self, client):
        d = client.get("/api/dashboard", headers=MANAGER).json()
        assert d["as_of"] == "2026-11-22T10:00:00Z"
        assert d["payment_terms_days"] == 30
        assert d["kpis"] == {
            "outstanding_count": 5,
            "outstanding_amount": 955000.0,
            "overdue_count": 5,
            "overdue_amount": 955000.0,
            "due_soon_count": 0,
            "avg_payment_turnaround_days": 11.7,
            "open_flag_count": 4,
            "smme_spend_share_pct": 16.3,
        }
        assert d["smme_share"] == {"smme_amount": 657000.0, "total_amount": 4027000.0, "pct": 16.3}
        assert d["ageing"] == [
            {"bucket": "0-30", "count": 0, "amount": 0.0},
            {"bucket": "31-60", "count": 4, "amount": 335000.0},
            {"bucket": "61-90", "count": 1, "amount": 620000.0},
            {"bucket": "90+", "count": 0, "amount": 0.0},
        ]

    def test_attention_list_oldest_first_smmes_first_on_ties(self, client):
        attention = client.get("/api/dashboard", headers=FINANCE).json()["attention"]
        assert [i["invoice_number"] for i in attention] == ["INV003", "INV006", "INV002", "INV008", "INV005"]
        assert attention[0]["supplier"]["name"] == "Metro Logistics"
        assert attention[0]["amount"] == 620000.0

    def test_spend_breakdowns(self, client):
        d = client.get("/api/dashboard", headers=FINANCE).json()
        top = d["spend_by_supplier"][0]
        assert (top["name"], top["amount"]) == ("Metro Logistics", 1330000.0)
        assert sum(s["amount"] for s in d["spend_by_supplier"]) == 4027000.0
        assert d["spend_by_department"][0] == {"department": "Operations", "amount": 1900000.0}

    def test_ages_keep_growing_after_seeding(self, client, clock):
        clock.now += timedelta(days=1)
        attention = client.get("/api/dashboard", headers=FINANCE).json()["attention"]
        assert attention[0]["days_outstanding"] == 66

    def test_custom_payment_terms_days_forwarded(self, tmp_path, clock):
        settings = Settings(
            database_url=f"sqlite:///{(tmp_path / 'terms.db').as_posix()}",
            seed_on_startup=True,
            payment_terms_days=45,
        )
        with TestClient(create_app(settings, clock=clock)) as custom_client:
            # At 45-day terms, only INV003 (65d) and INV006 (47d) are overdue.
            dash = custom_client.get("/api/dashboard", headers=FINANCE).json()
            assert dash["payment_terms_days"] == 45
            assert dash["kpis"]["overdue_count"] == 2
            overdue_list = custom_client.get("/api/invoices?overdue=true", headers=FINANCE).json()
            assert [i["invoice_number"] for i in overdue_list] == ["INV003", "INV006"]


# ---------------------------------------------------------------------------
# Identity and permissions (contract section 1)
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.mark.parametrize(
        "headers",
        [
            {},
            {"X-User-Id": ""},
            {"X-User-Id": "   "},
            {"X-User-Id": "abc"},
            {"X-User-Id": "--1"},
            {"X-User-Id": "0"},
            {"X-User-Id": "-5"},
            {"X-User-Id": "999"},
            {"X-User-Id": "9" * 30},
        ],
    )
    def test_missing_bad_or_unknown_user_is_401(self, client, headers):
        response = client.get("/api/invoices", headers=headers)
        assert response.status_code == 401
        assert error_code(response) == "UNAUTHENTICATED"

    def test_out_of_range_ids_do_not_500(self, client):
        huge = 10**30 - 1  # 30 nines
        for bad_id in (0, -5, huge):
            inv = client.get(f"/api/invoices/{bad_id}", headers=FINANCE)
            assert (inv.status_code, error_code(inv)) == (404, "NOT_FOUND")

            flg = resolve(client, bad_id, "CLEARED")
            assert (flg.status_code, error_code(flg)) == (404, "NOT_FOUND")

            po_sub = submit(client, po_id=bad_id)
            assert (po_sub.status_code, error_code(po_sub)) == (422, "PO_NOT_FOUND")

            pos = client.get(f"/api/purchase-orders?supplier_id={bad_id}", headers=FINANCE)
            assert pos.status_code == 200 and pos.json() == []

            invs = client.get(f"/api/invoices?supplier_id={bad_id}", headers=FINANCE)
            assert invs.status_code == 200 and invs.json() == []

    def test_me(self, client):
        finance = client.get("/api/me", headers=FINANCE).json()
        assert finance["supplier_id"] is None
        assert finance["supplier_status"] is None

        ubuntu = client.get("/api/me", headers=UBUNTU).json()
        assert ubuntu["supplier_id"] == 1
        assert ubuntu["supplier_status"] == "ACTIVE"

        sisonke = client.get("/api/me", headers=SISONKE).json()
        assert sisonke["supplier_id"] == 8
        assert sisonke["supplier_status"] == "INACTIVE"

    @pytest.mark.parametrize(
        ("method", "path", "headers"),
        [
            ("get", "/api/suppliers", UBUNTU),
            ("get", "/api/dashboard", UBUNTU),
            ("get", "/api/flags", UBUNTU),
            ("post", "/api/flags/1/resolve", UBUNTU),
            ("post", "/api/flags/1/resolve", MANAGER),
            ("post", "/api/invoices/3/approve", MANAGER),
            ("post", "/api/invoices/3/approve", UBUNTU),
            ("post", "/api/invoices/3/reject", MANAGER),
            ("post", "/api/invoices/3/reject", UBUNTU),
            ("post", "/api/invoices/3/pay", MANAGER),
            ("post", "/api/invoices/3/pay", UBUNTU),
            ("post", "/api/invoices", FINANCE),
            ("post", "/api/invoices", MANAGER),
        ],
    )
    def test_wrong_role_is_403(self, client, method, path, headers):
        body = {} if method == "post" else None
        response = client.request(method.upper(), path, headers=headers, json=body)
        assert response.status_code == 403
        assert error_code(response) == "FORBIDDEN"

    def test_supplier_cannot_see_another_suppliers_invoice(self, client):
        response = client.get("/api/invoices/8", headers=UBUNTU)  # INV008 is Thuto's
        assert response.status_code == 404
        assert error_code(response) == "NOT_FOUND"

    def test_missing_invoice_is_404(self, client):
        assert client.get("/api/invoices/999", headers=FINANCE).status_code == 404

    def test_supplier_lists_only_their_own_records(self, client):
        invoices = client.get("/api/invoices", headers=THUTO).json()
        assert {i["invoice_number"] for i in invoices} == {"INV002", "INV008"}
        pos = client.get("/api/purchase-orders", headers=THUTO).json()
        assert [p["po_number"] for p in pos] == ["PO003", "PO010"]
        assert client.get("/api/purchase-orders?supplier_id=1", headers=THUTO).json() == []
        assert client.get("/api/invoices?supplier_id=1", headers=THUTO).json() == []

    def test_manager_reads_everything(self, client):
        assert len(client.get("/api/invoices", headers=MANAGER).json()) == 8
        assert len(client.get("/api/flags", headers=MANAGER).json()) == 4


# ---------------------------------------------------------------------------
# Suppliers never see flags
# ---------------------------------------------------------------------------


class TestSupplierView:
    def test_detail_has_no_flags_or_flag_events(self, client):
        detail = client.get("/api/invoices/6", headers=UBUNTU).json()
        assert detail["open_flag_count"] is None
        assert detail["flags"] == []
        assert [e["action"] for e in detail["audit"]] == ["SUBMITTED"]
        assert all(e["note"] is None for e in detail["audit"])

    def test_list_has_no_flag_counts_and_ignores_flagged_filter(self, client):
        invoices = client.get("/api/invoices?flagged=true", headers=UBUNTU).json()
        assert {i["invoice_number"] for i in invoices} == {"INV001", "INV006"}
        assert all(i["open_flag_count"] is None for i in invoices)

    def test_staff_do_see_flags(self, client):
        detail = client.get("/api/invoices/6", headers=FINANCE).json()
        assert detail["open_flag_count"] == 2
        assert len(detail["flags"]) == 2

    def test_supplier_sees_rejection_reason_but_not_other_notes(self, client):
        client.post(
            "/api/invoices/6/reject", json={"reason": "Same work as INV001, already paid."}, headers=FINANCE
        )
        audit = client.get("/api/invoices/6", headers=UBUNTU).json()["audit"]
        assert [(e["action"], e["note"]) for e in audit] == [
            ("SUBMITTED", None),
            ("REJECTED", "Same work as INV001, already paid."),
        ]

    def test_supplier_notes_masked_on_approved_and_paid(self, client):
        invoice_id = submit(client).json()["id"]
        assert (
            client.post(
                f"/api/invoices/{invoice_id}/approve",
                json={"note": "Internal delivery note verification."},
                headers=FINANCE,
            ).status_code
            == 200
        )
        supplier_approved = client.get(f"/api/invoices/{invoice_id}", headers=UBUNTU).json()
        assert [(e["action"], e["note"]) for e in supplier_approved["audit"]] == [
            ("SUBMITTED", None),
            ("APPROVED", None),
        ]

        assert (
            client.post(
                f"/api/invoices/{invoice_id}/pay",
                json={"payment_reference": "EFT-777"},
                headers=FINANCE,
            ).status_code
            == 200
        )
        supplier_paid = client.get(f"/api/invoices/{invoice_id}", headers=UBUNTU).json()
        assert supplier_paid["payment_reference"] == "EFT-777"
        assert [(e["action"], e["note"]) for e in supplier_paid["audit"]] == [
            ("SUBMITTED", None),
            ("APPROVED", None),
            ("PAID", None),
        ]
        finance_paid = client.get(f"/api/invoices/{invoice_id}", headers=FINANCE).json()
        assert [(e["action"], e["note"]) for e in finance_paid["audit"]] == [
            ("SUBMITTED", None),
            ("APPROVED", "Internal delivery note verification."),
            ("PAID", "Payment reference EFT-777"),
        ]

    def test_new_submission_flags_hidden_from_supplier_visible_to_finance(self, client):
        # Same amount as INV001 (paid) and INV006, on Ubuntu's other PO.
        response = submit(client, invoice_number="UBC-200", amount=85000.0)
        assert response.status_code == 201
        body = response.json()
        assert body["flags"] == [] and body["open_flag_count"] is None
        assert [e["action"] for e in body["audit"]] == ["SUBMITTED"]

        staff = client.get(f"/api/invoices/{body['id']}", headers=FINANCE).json()
        assert [(f["rule"], f["related_invoice_number"]) for f in staff["flags"]] == [
            ("POSSIBLE_DUPLICATE", "INV001")
        ]
        flag_event = staff["audit"][1]
        assert flag_event["action"] == "FLAG_RAISED"
        assert flag_event["actor"] == {"id": 0, "name": "Automatic check", "role": "SYSTEM"}


# ---------------------------------------------------------------------------
# Submitting invoices: every hard-check error code
# ---------------------------------------------------------------------------


class TestSubmit:
    def test_valid_submission_created(self, client):
        response = submit(client)
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == 9
        assert body["status"] == "SUBMITTED"
        assert body["supplier"]["id"] == 1
        assert body["submitted_at"] == "2026-11-22T10:00:00Z"
        assert (body["days_outstanding"], body["is_overdue"], body["ageing_bucket"]) == (0, False, "0-30")
        assert body["description"] == "Office cleaning - November"
        assert body["audit"][0]["actor"]["name"] == "Ubuntu Cleaning (supplier portal)"

    @pytest.mark.parametrize(
        ("overrides", "field"),
        [
            ({"amount": 0}, "amount"),
            ({"amount": -5}, "amount"),
            ({"amount": 10.001}, "amount"),
            ({"invoice_number": "   "}, "invoice_number"),
            ({"invoice_number": "X" * 51}, "invoice_number"),
            ({"invoice_date": "2026-11-25"}, "invoice_date"),
            ({"invoice_date": "not-a-date"}, "invoice_date"),
            ({"description": "x" * 501}, "description"),
        ],
    )
    def test_bad_fields_are_validation_errors(self, client, overrides, field):
        response = submit(client, **overrides)
        assert response.status_code == 422
        assert error_code(response) == "VALIDATION_ERROR"
        assert field in [d["field"] for d in response.json()["error"]["details"]]

    def test_missing_field_is_validation_error(self, client):
        response = client.post("/api/invoices", json={"po_id": 8}, headers=UBUNTU)
        assert response.status_code == 422
        fields = {d["field"] for d in response.json()["error"]["details"]}
        assert {"invoice_number", "amount", "invoice_date"} <= fields

    def test_unknown_po(self, client):
        response = submit(client, po_id=999)
        assert (response.status_code, error_code(response)) == (422, "PO_NOT_FOUND")

    def test_po_of_another_supplier(self, client):
        response = submit(client, po_id=5, amount=1000.0)  # PO005 is Khula Electrical's
        assert (response.status_code, error_code(response)) == (422, "PO_SUPPLIER_MISMATCH")
        assert "Khula" not in response.json()["error"]["message"]

    def test_inactive_supplier(self, client):
        response = submit(client, headers=SISONKE, po_id=1)
        assert (response.status_code, error_code(response)) == (422, "SUPPLIER_INACTIVE")

    def test_amount_exceeds_po(self, client):
        response = submit(client, amount=95000.01)
        assert (response.status_code, error_code(response)) == (422, "AMOUNT_EXCEEDS_PO")

    def test_amount_equal_to_po_allowed(self, client):
        assert submit(client, amount=95000.0).status_code == 201

    def test_duplicate_number_any_case_or_spacing(self, client):
        response = submit(client, invoice_number="  inv006 ", amount=1000.0)
        assert (response.status_code, error_code(response)) == (409, "DUPLICATE_INVOICE_NUMBER")

    def test_same_number_from_another_supplier_is_fine(self, client):
        response = submit(client, headers=PRIME, invoice_number="INV006", po_id=9, amount=1000.0)
        assert response.status_code == 201

    def test_number_reusable_after_rejection(self, client):
        first = submit(client).json()
        client.post(
            f"/api/invoices/{first['id']}/reject", json={"reason": "Wrong VAT number."}, headers=FINANCE
        )
        again = submit(client)
        assert again.status_code == 201
        assert again.json()["id"] != first["id"]

    def test_spoofed_supplier_id_in_body_is_ignored(self, client):
        # Sending another supplier's id in the JSON body must never reassign ownership.
        created = client.post("/api/invoices", json={**NEW_INVOICE, "supplier_id": 2}, headers=UBUNTU)
        assert created.status_code == 201
        assert created.json()["supplier"]["id"] == 1

        # And it cannot be used to bill against another supplier's PO (PO009 belongs to Prime).
        mismatched = client.post(
            "/api/invoices",
            json={**NEW_INVOICE, "invoice_number": "UBC-SPOOF-2", "po_id": 9, "supplier_id": 2},
            headers=UBUNTU,
        )
        assert (mismatched.status_code, error_code(mismatched)) == (422, "PO_SUPPLIER_MISMATCH")

    def test_live_po_over_invoiced_flag_raised_on_submit(self, client):
        # PO008 is R95,000. Two different-amount invoices totalling R110,000 trigger PO_OVER_INVOICED.
        first = submit(client, invoice_number="UBC-PART-1", amount=60000.0)
        assert first.status_code == 201
        second = submit(client, invoice_number="UBC-PART-2", amount=50000.0)
        assert second.status_code == 201
        assert second.json()["flags"] == []  # hidden from supplier

        staff = client.get(f"/api/invoices/{second.json()['id']}", headers=FINANCE).json()
        assert [f["rule"] for f in staff["flags"]] == ["PO_OVER_INVOICED"]
        assert "R110,000.00" in staff["flags"][0]["message"]
        assert "R15,000.00 more than" in staff["flags"][0]["message"]


# ---------------------------------------------------------------------------
# Lifecycle, flags and audit trail
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_happy_path_submit_approve_pay(self, client, clock):
        invoice_id = submit(client).json()["id"]

        clock.now += timedelta(days=3)
        approved = client.post(
            f"/api/invoices/{invoice_id}/approve", json={"note": "Matches delivery note."}, headers=FINANCE
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["approved_at"] == "2026-11-25T10:00:00Z"

        clock.now += timedelta(days=2)
        paid = client.post(
            f"/api/invoices/{invoice_id}/pay", json={"payment_reference": "EFT-0091"}, headers=FINANCE
        )
        assert paid.status_code == 200
        body = paid.json()
        assert (body["status"], body["payment_reference"], body["days_outstanding"]) == (
            "PAID",
            "EFT-0091",
            5,
        )
        assert [(e["action"], e["from_status"], e["to_status"], e["actor"]["id"]) for e in body["audit"]] == [
            ("SUBMITTED", None, "SUBMITTED", 3),
            ("APPROVED", "SUBMITTED", "APPROVED", 1),
            ("PAID", "APPROVED", "PAID", 1),
        ]
        assert body["audit"][1]["note"] == "Matches delivery note."

        # Turnaround now includes this 5-day payment: (15 + 12 + 8 + 5) / 4 = 10.0.
        kpis = client.get("/api/dashboard", headers=FINANCE).json()["kpis"]
        assert kpis["avg_payment_turnaround_days"] == 10.0

    def test_approve_without_body(self, client):
        response = client.post("/api/invoices/3/approve", headers=FINANCE)  # INV003 has no flags
        assert response.status_code == 200
        assert response.json()["audit"][-1]["note"] is None

    def test_reject_from_approved_via_http(self, client):
        assert client.post("/api/invoices/3/approve", headers=FINANCE).status_code == 200
        rejected = client.post(
            "/api/invoices/3/reject",
            json={"reason": "Delivery shortfall reported before payment run."},
            headers=FINANCE,
        )
        assert rejected.status_code == 200
        body = rejected.json()
        assert body["status"] == "REJECTED"
        assert body["rejection_reason"] == "Delivery shortfall reported before payment run."
        assert body["audit"][-1]["from_status"] == "APPROVED"
        assert body["audit"][-1]["to_status"] == "REJECTED"

    def test_pay_before_approval_refused(self, client):
        response = client.post("/api/invoices/3/pay", json={"payment_reference": "EFT-1"}, headers=FINANCE)
        assert (response.status_code, error_code(response)) == (409, "INVALID_STATUS_TRANSITION")

    def test_paid_invoice_cannot_be_rejected(self, client):
        response = client.post(
            "/api/invoices/1/reject", json={"reason": "Changed our mind."}, headers=FINANCE
        )
        assert (response.status_code, error_code(response)) == (409, "INVALID_STATUS_TRANSITION")

    def test_reject_needs_a_real_reason(self, client):
        response = client.post("/api/invoices/3/reject", json={"reason": "  no  "}, headers=FINANCE)
        assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")
        assert response.json()["error"]["details"][0]["field"] == "reason"

    def test_pay_needs_a_reference(self, client):
        client.post("/api/invoices/3/approve", headers=FINANCE)
        response = client.post("/api/invoices/3/pay", json={"payment_reference": " "}, headers=FINANCE)
        assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")

    def test_flagged_invoice_cannot_be_approved(self, client):
        response = client.post("/api/invoices/6/approve", headers=FINANCE)
        assert (response.status_code, error_code(response)) == (409, "FLAGS_UNRESOLVED")
        assert client.get("/api/invoices/6", headers=FINANCE).json()["status"] == "SUBMITTED"

    def test_clearing_all_flags_unblocks_approval(self, client):
        first, second = flags_of(client, "INV006")
        cleared = resolve(client, first["id"], "CLEARED")
        assert cleared.status_code == 200
        assert cleared.json()["status"] == "CLEARED"
        assert cleared.json()["resolved_by"] == {"id": 1, "name": "Thandi Nkosi"}
        assert cleared.json()["resolved_at"] == "2026-11-22T10:00:00Z"

        # One cleared, one still open: still blocked.
        assert client.post("/api/invoices/6/approve", headers=FINANCE).status_code == 409
        resolve(client, second["id"], "CLEARED")
        approved = client.post("/api/invoices/6/approve", headers=FINANCE)
        assert approved.status_code == 200
        actions = [e["action"] for e in approved.json()["audit"]]
        assert actions == [
            "SUBMITTED",
            "FLAG_RAISED",
            "FLAG_RAISED",
            "FLAG_CLEARED",
            "FLAG_CLEARED",
            "APPROVED",
        ]

    def test_confirmed_flag_keeps_blocking_and_reject_works(self, client):
        first, second = flags_of(client, "INV006")
        resolve(client, first["id"], "CONFIRMED", "Same cleaning month as INV001.")
        resolve(client, second["id"], "CLEARED")
        response = client.post("/api/invoices/6/approve", headers=FINANCE)
        assert (response.status_code, error_code(response)) == (409, "FLAGS_UNRESOLVED")

        rejected = client.post(
            "/api/invoices/6/reject", json={"reason": "Duplicate of INV001, already paid."}, headers=FINANCE
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"
        assert rejected.json()["rejection_reason"] == "Duplicate of INV001, already paid."
        assert rejected.json()["days_outstanding"] is None

    def test_flag_resolved_only_once(self, client):
        flag_id = flags_of(client, "INV008")[0]["id"]
        resolve(client, flag_id, "CLEARED")
        response = resolve(client, flag_id, "CONFIRMED")
        assert (response.status_code, error_code(response)) == (409, "FLAG_ALREADY_RESOLVED")

    def test_resolve_validation_and_missing_flag(self, client):
        bad = client.post("/api/flags/1/resolve", json={"outcome": "OPEN", "note": "x"}, headers=FINANCE)
        assert (bad.status_code, error_code(bad)) == (422, "VALIDATION_ERROR")
        no_note = client.post(
            "/api/flags/1/resolve", json={"outcome": "CLEARED", "note": " "}, headers=FINANCE
        )
        assert no_note.status_code == 422
        assert resolve(client, 999, "CLEARED").status_code == 404

    def test_rejecting_frees_the_po_and_drops_out_of_dashboard(self, client):
        inv6_flags = flags_of(client, "INV006")
        assert len(inv6_flags) == 2

        client.post("/api/invoices/6/reject", json={"reason": "Duplicate of INV001."}, headers=FINANCE)
        po1 = client.get("/api/purchase-orders", headers=FINANCE).json()[0]
        assert (po1["invoiced_amount"], po1["remaining_amount"]) == (85000.0, 0.0)

        # Contract 3.5: all four open-review views agree once INV006 is rejected.
        kpis = client.get("/api/dashboard", headers=FINANCE).json()["kpis"]
        assert (kpis["outstanding_count"], kpis["outstanding_amount"], kpis["open_flag_count"]) == (
            4,
            870000.0,
            2,
        )
        all_flags = client.get("/api/flags", headers=FINANCE).json()
        open_flags = client.get("/api/flags?status=OPEN", headers=FINANCE).json()
        assert len(all_flags) == 2 and {f["invoice_number"] for f in all_flags} == {"INV008"}
        assert len(open_flags) == 2 and {f["invoice_number"] for f in open_flags} == {"INV008"}

        flagged_numbers = [
            i["invoice_number"] for i in client.get("/api/invoices?flagged=true", headers=FINANCE).json()
        ]
        assert flagged_numbers == ["INV008"]

        inv6 = client.get("/api/invoices/6", headers=FINANCE).json()
        assert inv6["open_flag_count"] == 0
        # Flags stay visible as history in invoice detail, untouched.
        assert len(inv6["flags"]) == 2
        assert all(f["status"] == "OPEN" for f in inv6["flags"])

        # Resolving a flag on a REJECTED invoice is refused with 409 INVALID_STATUS_TRANSITION.
        res = resolve(client, inv6_flags[0]["id"], "CLEARED")
        assert (res.status_code, error_code(res)) == (409, "INVALID_STATUS_TRANSITION")

    def test_resolving_flag_on_paid_invoice_returns_409_invalid_transition(self, client):
        first, second = flags_of(client, "INV006")
        resolve(client, first["id"], "CLEARED")
        resolve(client, second["id"], "CLEARED")
        assert client.post("/api/invoices/6/approve", headers=FINANCE).status_code == 200
        assert (
            client.post(
                "/api/invoices/6/pay", json={"payment_reference": "EFT-6"}, headers=FINANCE
            ).status_code
            == 200
        )
        res = resolve(client, first["id"], "CONFIRMED")
        assert (res.status_code, error_code(res)) == (409, "INVALID_STATUS_TRANSITION")

    def test_audit_events_are_insert_only(self, client):
        session = client.app.state.session_factory()
        try:
            event = session.get(AuditEvent, 1)
            event.note = "rewritten history"
            with pytest.raises(PermissionError):
                session.flush()
            session.rollback()
            session.delete(session.get(AuditEvent, 1))
            with pytest.raises(PermissionError):
                session.flush()
        finally:
            session.close()

    def test_sqlite_foreign_keys_enforced(self, client):
        session = client.app.state.session_factory()
        try:
            session.add(
                Invoice(
                    invoice_number="ORPHAN-1",
                    supplier_id=9999,
                    po_id=1,
                    amount=Decimal("100.00"),
                    invoice_date=date(2026, 11, 20),
                    status=InvoiceStatus.SUBMITTED,
                    submitted_at=FROZEN_NOW,
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
        finally:
            session.rollback()
            session.close()


# ---------------------------------------------------------------------------
# Listing, filters and framework errors
# ---------------------------------------------------------------------------


class TestListing:
    def test_default_sort_is_oldest_first(self, client):
        numbers = [i["invoice_number"] for i in client.get("/api/invoices", headers=FINANCE).json()]
        assert numbers[:5] == ["INV003", "INV006", "INV002", "INV008", "INV005"]

    def test_filters(self, client):
        def numbers(query):
            return [i["invoice_number"] for i in client.get(f"/api/invoices?{query}", headers=FINANCE).json()]

        assert sorted(numbers("status=PAID")) == ["INV001", "INV004", "INV007"]
        assert numbers("flagged=true") == ["INV006", "INV008"]
        assert len(numbers("overdue=true")) == 5
        assert numbers("supplier_id=3&flagged=true") == ["INV008"]
        assert numbers("sort=amount_desc")[0] == "INV003"
        assert numbers("status=PAID&sort=submitted_desc") == ["INV007", "INV004", "INV001"]

    def test_flags_filter_by_status(self, client):
        resolve(client, 1, "CLEARED")
        assert [f["id"] for f in client.get("/api/flags?status=OPEN", headers=FINANCE).json()] == [2, 3, 4]
        assert [f["id"] for f in client.get("/api/flags?status=CLEARED", headers=FINANCE).json()] == [1]

    def test_bad_query_value_is_validation_error(self, client):
        response = client.get("/api/invoices?status=LOST", headers=FINANCE)
        assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")
        assert response.json()["error"]["details"][0]["field"] == "status"

    def test_malformed_json_reports_body_field(self, client):
        response = client.post(
            "/api/invoices",
            content=b"{bad json",
            headers={**UBUNTU, "Content-Type": "application/json"},
        )
        assert (response.status_code, error_code(response)) == (422, "VALIDATION_ERROR")
        assert response.json()["error"]["details"][0]["field"] == "body"

    def test_unknown_route_and_wrong_method_use_error_shape(self, client):
        missing = client.get("/api/nothing-here")
        assert (missing.status_code, error_code(missing)) == (404, "NOT_FOUND")
        wrong = client.delete("/api/invoices/1", headers=FINANCE)
        assert (wrong.status_code, error_code(wrong)) == (405, "METHOD_NOT_ALLOWED")

    def test_cors_allows_the_frontend(self, client):
        response = client.options(
            "/api/invoices",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
