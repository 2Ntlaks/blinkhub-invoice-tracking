import { expect, type Page } from "@playwright/test";

// Stable seed ids (docs/api-contract.md section 6).
export const USERS = {
  finance: 1, // Thandi Nkosi
  manager: 2, // Sipho Mokoena
  ubuntu: 3, // Ubuntu Cleaning (supplier portal), supplier 1
  thuto: 5, // Thuto Supplies (supplier portal), supplier 3
  sisonke: 10, // Sisonke Trading (supplier portal), INACTIVE
} as const;

export const INVOICE_IDS = { INV003: 3, INV006: 6, INV008: 8 } as const;

/** Open a page as a demo user (`?as=<id>` is the same demo identity the role switcher sets). */
export async function openAs(page: Page, userId: number, path = "/") {
  const sep = path.includes("?") ? "&" : "?";
  await page.goto(`${path}${sep}as=${userId}`);
  await expect(page.getByTestId("boot-loading")).toHaveCount(0);
}

/** The UI must never use accusatory wording (contract section 6, brief section 3 problem 6). */
export async function expectNoAccusatoryWords(page: Page) {
  await expect(page.locator("body")).not.toContainText(/fraud|suspicious/i);
}
