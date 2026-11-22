import { expect, test } from "@playwright/test";
import { USERS, openAs } from "./helpers";

const today = new Date().toISOString().slice(0, 10);

test("supplier submits an invoice against its own PO; a repeated number is refused", async ({ page }) => {
  await openAs(page, USERS.ubuntu, "/submit");

  await page.getByTestId("field-po").selectOption("8"); // PO008 (stable seed id)
  await page.getByTestId("field-invoice-number").fill("UBC-E2E-001");
  await page.getByTestId("field-amount").fill("40000");
  await page.getByTestId("field-invoice-date").fill(today);
  await page.getByTestId("field-description").fill("Office cleaning, November (E2E)");
  await page.getByTestId("btn-submit-invoice").click();

  // Lands on the new invoice, status SUBMITTED, and a supplier sees no review wording or flags.
  await expect(page.getByTestId("invoice-detail")).toBeVisible();
  await expect(page.getByTestId("invoice-number")).toContainText("UBC-E2E-001");
  await expect(page.getByTestId("status-badge").first()).toContainText(/submitted/i);
  await expect(page.getByTestId("flags-panel")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(/needs review/i);

  // Same number again (different case and spacing) is an exact duplicate: refused, nothing saved.
  await openAs(page, USERS.ubuntu, "/submit");
  await page.getByTestId("field-po").selectOption("8"); // PO008 (stable seed id)
  await page.getByTestId("field-invoice-number").fill("  ubc-e2e-001 ");
  await page.getByTestId("field-amount").fill("10000");
  await page.getByTestId("field-invoice-date").fill(today);
  await page.getByTestId("btn-submit-invoice").click();
  await expect(page.getByText(/already|duplicate/i).first()).toBeVisible();
  await expect(page.getByTestId("submit-form")).toBeVisible();
});

test("an inactive supplier is told it cannot submit", async ({ page }) => {
  await openAs(page, USERS.sisonke, "/submit");
  await expect(
    page.getByTestId("supplier-inactive-notice").or(page.getByTestId("no-po-notice")),
  ).toBeVisible();
  await expect(page.getByTestId("btn-submit-invoice")).toHaveCount(0);
});
