import { test, expect } from "@playwright/test";
const account = {
  id: "123",
  label: "Demo Gold",
  server: "Fake-Demo",
  login_suffix: "5678",
  status: "ONLINE",
  margin_mode: "RETAIL_HEDGING",
  selected: true,
  last_seen_at: new Date().toISOString(),
  ea_version: "fake-0.1",
  execution_enabled: false,
  mappings: [{ alias: "gold", actual_symbol: "XAUUSD.a" }],
};
test("signed-out page has pairing instructions", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Your terminal\.\s*Your control\./ }),
  ).toBeVisible();
  await expect(
    page.getByText("Your broker password stays with MT5.", { exact: false }),
  ).toBeVisible();
});
for (const viewport of [
  { width: 1440, height: 1100 },
  { width: 390, height: 844 },
])
  test(`account view and mapping at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.route("**/v1/web/accounts", (r) =>
      r.fulfill({ json: [account] }),
    );
    await page.route("**/v1/web/history", (r) =>
      r.fulfill({
        json: [
          {
            id: "test-operation",
            account_id: "123",
            type: "PROTECT_BREAKEVEN",
            status: "PARTIAL",
            created_at: new Date().toISOString(),
            payload: { symbol: "XAUUSD.a", side: "BUY", target_fraction: 0.5 },
            summary: { code: "OK", planned_volume: 0.3, confirmed_volume: 0.2 },
          },
        ],
      }),
    );
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Demo Gold" }),
    ).toBeVisible();
    await expect(page.getByText("0.3 / 0.2 lots")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.getByRole("button", { name: "Edit aliases" }).click();
    await expect(
      page.getByRole("heading", { name: "Map an exact broker symbol" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Revoke", exact: true }).click();
    await expect(page.getByRole("alertdialog")).toBeVisible();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.screenshot({
      path: `test-results/dashboard-${viewport.width}.png`,
      fullPage: true,
    });
  });

test("signed-out navigation explains the selected protected view", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to view your accounts" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Accounts", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Activity", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in to view your activity" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sign in to view your activity" }),
  ).toBeVisible();
  await page
    .getByText("Telegram sign-in not working?", { exact: true })
    .click();
  await expect(page.getByText(/If Telegram shows/)).toBeVisible();
});

test("authenticated navigation switches account and activity views", async ({
  page,
}) => {
  await page.route("**/v1/web/accounts", (r) => r.fulfill({ json: [account] }));
  await page.route("**/v1/web/history", (r) => r.fulfill({ json: [] }));
  await page.goto("/");
  await page.getByRole("link", { name: "Activity", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Recent activity" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Demo Gold" })).toBeHidden();
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Demo Gold" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recent activity" }),
  ).toBeHidden();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Recent activity" }),
  ).toBeVisible();
});
