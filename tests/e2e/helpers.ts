import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Demo@2026!";
export const USERS = {
  admin: "admin@demo.local",
  analyst: "analista@demo.local",
  user: "usuario@demo.local",
  user2: "usuario2@demo.local",
};

export async function login(page: Page, email: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/painel$/);
}

/** Garante que a página não tem rolagem horizontal (conteúdo fora da tela). */
export async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "rolagem horizontal na página").toBeLessThanOrEqual(1);
}
