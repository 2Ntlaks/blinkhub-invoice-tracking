import { expect, test } from "@playwright/test";
import { INVOICE_IDS, USERS, openAs } from "./helpers";

// INV008 repeats INV002 (same supplier, same amount, same day). Finance rejects it with a reason;
// the supplier can see that reason (it is theirs to act on), but not the internal flags.
test("finance rejects INV008 with a reason the supplier can read", async ({ page }) => {
  await openAs(page, USERS.finance, `/invoices/${INVOICE_IDS.INV008}`);
  await expect(page.getByTestId("invoice-number")).toContainText("INV008");

  // A too-short reason is refused by the form.
  await page.getByTestId("btn-reject").click();
  await page.getByTestId("field-action").fill("dup");
  await page.getByTestId("btn-confirm-action").click();
  await expect(page.getByTestId("action-dialog")).toBeVisible();

  const reason = "Same amount and date as INV002 for PO003; please confirm whether this is a second delivery.";
  await page.getByTestId("field-action").fill(reason);
  await page.getByTestId("btn-confirm-action").click();
  await expect(page.getByTestId("status-badge").first()).toContainText(/rejected/i);
  await expect(page.getByTestId("rejection-reason")).toContainText("INV002");

  await openAs(page, USERS.thuto, `/invoices/${INVOICE_IDS.INV008}`);
  await expect(page.getByTestId("status-badge").first()).toContainText(/rejected/i);
  await expect(page.getByTestId("rejection-reason")).toContainText("INV002");
  await expect(page.getByTestId("flags-panel")).toHaveCount(0);

  // Contract 3.5: flags on a rejected invoice are history, not open review work. INV006's two flags
  // were cleared in journey 03 and INV008 is now rejected, so nothing is left to review.
  await openAs(page, USERS.manager, "/dashboard");
  await expect(page.getByTestId("kpi-open-flags-value")).toContainText("0");
});
