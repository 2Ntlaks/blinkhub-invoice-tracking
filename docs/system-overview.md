# BlinkHub Invoice and Payment Tracking: System Overview

This prototype, built for the ProcureSense BlinkHub Procurement Innovation Challenge, shows how Mzansi Infrastructure and Community Services (MICS), the fictional South African client in the case study, can replace emails and spreadsheets with one clear invoice workflow.

## 1. The problem

The motivating story is **Problem 4: The Invoice That Never Gets Paid**. A local cleaning company finished its work and waited 75 days without pay, struggling to pay staff and buy supplies.

MICS's internal review exposed the causes. Suppliers email **invoices** (formal bills requesting payment after delivery) to different addresses. Some invoices are duplicated, and others omit their **purchase order** (PO) reference, the approved order stating what MICS agreed to buy and at what price. Finance cannot always tell who must approve a bill, staff chase updates manually, suppliers cannot track payment progress, and management has no clear view of late invoices.

Alongside Problem 4, the prototype touches **Problem 6** (catching duplicates before payment) and **Problem 3** (giving management live spend visibility, including spend with **SMMEs**, or small, medium, and micro enterprises).

## 2. What the system does

Suppliers, finance officers, and managers share one portal. Suppliers submit invoices against real purchase orders, automatic rules check every bill on entry, finance reviews and pays with clear accountability, and management sees live payment health and spend.

Every invoice moves through four statuses:

1. **Submitted**: a supplier submits an invoice against one of their purchase orders.
2. **Approved**: finance reviews the invoice, resolves any **flags** (internal warning markers asking finance to double-check an unusual bill), and approves it.
3. **Paid**: finance records payment with a payment reference.
4. **Rejected**: before payment, finance rejects the invoice with a written reason visible to the supplier.

Every step writes to an **audit trail**: a permanent, uneditable log recording who acted, when, and why.

## 3. Three roles

Access uses a **role**, a job-based permission level controlling what each user can see and do. This prototype uses a demo role switcher instead of real logins so reviewers can test every view immediately.

| Role | Can see | Can do |
|---|---|---|
| **Supplier** | Only their own POs, own invoices, and status timeline (including rejection reasons). | Submit invoices for their own business. |
| **Finance officer** | All suppliers, POs, invoices, open flags, and the dashboard. | Review flags; approve, reject, or pay invoices. |
| **Manager** | Read-only view of all records, flags, audit trails, and the dashboard. | Monitor backlogs, turnaround times, and spend. |

Suppliers **never see review flags**. Flags are internal prompts for finance, not accusations, so hiding them avoids unfair blame when a bill has an innocent explanation.

## 4. Hard blocks vs soft flags

Two rule layers protect MICS. **Hard checks** refuse invalid invoices immediately. **Soft checks** accept the invoice but mark it "Needs review" with a flag.

| Type | Rule | Trigger |
|---|---|---|
| Hard block (refused) | Missing PO | The purchase order does not exist. |
| Hard block (refused) | Wrong supplier | The PO belongs to another supplier. |
| Hard block (refused) | Inactive supplier | The supplier is Inactive. |
| Hard block (refused) | Single invoice over PO | One invoice exceeds the PO value. |
| Hard block (refused) | Exact duplicate number | Same supplier already has a non-rejected invoice with that number. |
| Soft flag (needs review) | Possible duplicate | Same supplier and amount as another non-rejected invoice within 90 days. |
| Soft flag (needs review) | Over-invoiced PO | Non-rejected invoices on that PO exceed the PO value. |

Approval is blocked until finance marks each flag **Cleared** (legitimate) or **Confirmed** (real problem, so finance should reject the invoice). Open invoices waiting more than **30 days** are overdue and sorted oldest first, with SMMEs first on ties. Above all, **a flag is a question, not an accusation**.

## 5. What it shows with the MICS sample data

These figures come from loading the case study's fictional sample data (8 suppliers, 12 POs, 8 invoices). They show what the prototype surfaces from test records, not real MICS performance:

* **Listed spend**: R4,027,000 across 12 POs. Three large companies receive **83.7%** (led by Metro Logistics at **R1,330,000**); SMMEs receive **16.3%** (**R657,000**).
* **Overdue invoices**: All **5 open invoices** (**R955,000**) are overdue past 30 days. The worst is **INV003** (Metro Logistics, **R620,000**, **65 days**) with **no flag**: nothing about it looks unusual, it is simply waiting.
* **Four open flags**: **INV006** (Ubuntu Cleaning, R85,000, 47 days) matches paid **INV001**, and **INV008** (Thuto Supplies, R35,000, 42 days) matches same-day **INV002**. Each carries two flags (possible duplicate and over-invoiced PO), giving **4 open flags**. (The 75-day cleaning company is the motivating story, not a sample row.)
* **Paid turnaround**: The 3 paid invoices averaged **11.7 days** to payment.
* **Inactive supplier**: **Sisonke Trading** is Inactive, so its invoices are refused.

## 6. Assumptions we had to make

Six assumptions fill gaps in the sample tables:

1. **PO matching (A1)**: Sample invoices lacked PO numbers, so each was linked to the same supplier's PO with the exact same amount. This is transparent and repeatable, and it puts INV006 and INV008 onto already-invoiced POs where rules flag them.
2. **Open status (A2)**: "Outstanding" invoices load as Submitted (awaiting review).
3. **Open dates (A3)**: Submission dates count backward from "days outstanding".
4. **Paid turnaround (A4)**: Paid "days outstanding" is read as payment turnaround, placing INV001 before INV006.
5. **Payment terms (A5)**: Overdue means open more than 30 days.
6. **Spend (A6)**: Spend equals committed PO value (R4,027,000).

## 7. What it does not do yet, and what comes next

Moving this prototype into production at MICS would require:

* **Real login** replacing the demo role switcher.
* **Document uploads** for invoice PDFs and delivery notes.
* **Email or SMS reminders** for status changes and 30-day deadlines.
* **Payment-system integration** to sync payment references automatically.
* **Separation of duties** so the approver cannot also mark an invoice paid.
* **Cloud deployment** for shared access across MICS.
* **More Problem 6 rules**, such as flagging payments just below approval thresholds and bank detail changes before payment.

Technical readers looking for architecture details and setup instructions should see `docs/architecture.md` and `README.md`.
