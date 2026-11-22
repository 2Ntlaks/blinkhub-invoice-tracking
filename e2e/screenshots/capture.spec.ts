import { expect, test } from "@playwright/test";
import { INVOICE_IDS, USERS, openAs } from "../tests/helpers";

const OUT = "../docs/screenshots";

test("capture README screenshots", async ({ page }) => {
  await openAs(page, USERS.manager, "/dashboard");
  await expect(page.getByTestId("kpi-overdue-amount-value")).toBeVisible();
  await page.waitForTimeout(800); // let chart animations settle
  await page.screenshot({ path: `${OUT}/dashboard.png`, fullPage: true });

  await openAs(page, USERS.finance, "/invoices");
  await expect(page.getByTestId("invoice-row-INV003")).toBeVisible();
  await page.screenshot({ path: `${OUT}/finance-queue.png` });

  await openAs(page, USERS.finance, `/invoices/${INVOICE_IDS.INV006}`);
  await expect(page.getByTestId("flags-panel")).toBeVisible();
  await page.screenshot({ path: `${OUT}/needs-review-inv006.png`, fullPage: true });

  await openAs(page, USERS.ubuntu, "/submit");
  await page.getByTestId("field-po").selectOption("8");
  await page.getByTestId("field-invoice-number").fill("UBC-2026-114");
  await page.getByTestId("field-amount").fill("95000");
  await page.getByTestId("field-description").fill("Office cleaning, November");
  await page.screenshot({ path: `${OUT}/supplier-submit.png` });

  await openAs(page, USERS.ubuntu, `/invoices/${INVOICE_IDS.INV006}`);
  await expect(page.getByTestId("audit-timeline")).toBeVisible();
  await page.screenshot({ path: `${OUT}/supplier-view-no-flags.png`, fullPage: true });

  await openAs(page, USERS.sisonke, "/submit");
  await expect(page.getByTestId("supplier-inactive-notice")).toBeVisible();
  await page.screenshot({ path: `${OUT}/inactive-supplier.png` });
});
