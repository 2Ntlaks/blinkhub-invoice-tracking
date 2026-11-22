import { expect, test } from "@playwright/test";
import { INVOICE_IDS, USERS, expectNoAccusatoryWords, openAs } from "./helpers";

// The core demo: INV006 (Ubuntu Cleaning) has the same amount as already-paid INV001 and over-bills PO001.
// Approval is blocked until each flag is reviewed; then finance approves and pays, and the audit trail
// records every step. The supplier then sees PAID, but never the flags.
test("finance reviews INV006's flags, then approves and pays it", async ({ page }) => {
  await openAs(page, USERS.finance, `/invoices/${INVOICE_IDS.INV006}`);
  await expect(page.getByTestId("invoice-number")).toContainText("INV006");
  await expectNoAccusatoryWords(page);

  // Blocked while flags are open.
  await expect(page.getByTestId("btn-approve")).toBeDisabled();
  await expect(page.getByTestId("approve-blocked")).toBeVisible();

  // Clear both flags with a note.
  const resolveButtons = page.locator('[data-testid^="btn-resolve-flag-"]');
  await expect(resolveButtons).toHaveCount(2);
  for (let i = 0; i < 2; i++) {
    await resolveButtons.first().click();
    await page.getByTestId("outcome-cleared").click();
    await page.getByTestId("field-resolve-note").fill("Checked with supplier: separate November service, PO to be topped up.");
    await page.getByTestId("btn-confirm-resolve").click();
    await expect(page.getByTestId("resolve-dialog")).toBeHidden(); // <dialog> stays in the DOM, closed
  }
  await expect(resolveButtons).toHaveCount(0);

  // Approve, then pay with a reference.
  await expect(page.getByTestId("btn-approve")).toBeEnabled();
  await page.getByTestId("btn-approve").click();
  await page.getByTestId("btn-confirm-action").click();
  await expect(page.getByTestId("status-badge").first()).toContainText(/approved/i);

  await page.getByTestId("btn-pay").click();
  await page.getByTestId("field-action").fill("EFT-E2E-0006");
  await page.getByTestId("btn-confirm-action").click();
  await expect(page.getByTestId("status-badge").first()).toContainText(/paid/i);
  await expect(page.getByTestId("payment-reference")).toContainText("EFT-E2E-0006");

  // Every step is in the audit trail.
  const audit = page.getByTestId("audit-timeline");
  await expect(audit.getByTestId("audit-event-FLAG_CLEARED")).toHaveCount(2);
  await expect(audit.getByTestId("audit-event-APPROVED")).toHaveCount(1);
  await expect(audit.getByTestId("audit-event-PAID")).toHaveCount(1);

  // The supplier sees PAID, and nothing about flags.
  await openAs(page, USERS.ubuntu, `/invoices/${INVOICE_IDS.INV006}`);
  await expect(page.getByTestId("status-badge").first()).toContainText(/paid/i);
  await expect(page.getByTestId("flags-panel")).toHaveCount(0);
  await expect(page.getByTestId("audit-timeline").getByTestId("audit-event-FLAG_CLEARED")).toHaveCount(0);
});
