import { expect, test } from "@playwright/test";
import { INVOICE_IDS, USERS, expectNoAccusatoryWords, openAs } from "./helpers";

// Runs first, on the untouched seed: the dashboard must reproduce the case-study findings exactly
// (docs/data-assumptions.md section 3), and a manager must not be able to change anything.
test("manager sees the case-study numbers and cannot act on invoices", async ({ page }) => {
  await openAs(page, USERS.manager, "/dashboard");

  await expect(page.getByTestId("kpi-outstanding-count-value")).toContainText("5");
  await expect(page.getByTestId("kpi-overdue-count-value")).toContainText("5");
  await expect(page.getByTestId("kpi-overdue-amount-value")).toContainText("R955k");
  await expect(page.getByTestId("kpi-avg-turnaround-value")).toContainText("11.7");
  await expect(page.getByTestId("kpi-open-flags-value")).toContainText("4");
  await expect(page.getByTestId("kpi-smme-share-value")).toContainText("16.3");

  // The worst invoice heads the attention list: INV003, Metro Logistics, 65 days, no flag.
  const attention = page.getByTestId("attention-list");
  await expect(attention.locator('[data-testid^="attention-row-"]').first()).toHaveAttribute(
    "data-testid",
    "attention-row-INV003",
  );
  await expectNoAccusatoryWords(page);

  // Read-only: the manager can open a flagged invoice but gets no action or resolve buttons.
  await openAs(page, USERS.manager, `/invoices/${INVOICE_IDS.INV006}`);
  await expect(page.getByTestId("invoice-number")).toContainText("INV006");
  await expect(page.getByTestId("flags-panel")).toBeVisible();
  await expect(page.getByTestId("btn-approve")).toHaveCount(0);
  await expect(page.getByTestId("btn-reject")).toHaveCount(0);
  await expect(page.getByTestId("btn-pay")).toHaveCount(0);
  await expect(page.locator('[data-testid^="btn-resolve-flag-"]')).toHaveCount(0);
});
