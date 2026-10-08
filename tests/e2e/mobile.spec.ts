import { expect, test } from "@playwright/test";
import { USERS, expectNoHorizontalOverflow, login } from "./helpers";

const PAGES = ["/painel", "/carteira", "/mercado", "/opcoes-diarias", "/simulador", "/operacoes", "/cursos", "/solicitacoes", "/agenda", "/notificacoes"];

test("menu móvel abre, navega e fecha", async ({ page }) => {
  await login(page, USERS.user);
  await page.getByRole("button", { name: "Abrir menu" }).click();
  const menu = page.getByRole("dialog", { name: "Menu" });
  await expect(menu).toBeVisible();
  await menu.getByRole("link", { name: "Simulador (boletas)" }).click();
  await expect(page).toHaveURL(/\/simulador$/);
  await expect(menu).toBeHidden();
  await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Menu" })).toBeHidden();
});

test("páginas principais sem rolagem horizontal no celular", async ({ page }) => {
  await login(page, USERS.user);
  for (const p of PAGES) {
    await page.goto(p);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});

test("simulador funciona no celular", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/simulador");
  await page.getByLabel("Strike (R$)").fill("36");
  await page.getByLabel("Prêmio (R$)").fill("1,85");
  await expect(page.getByText("R$ 185,00 (débito)").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("administração sem rolagem horizontal no celular", async ({ page }) => {
  await login(page, USERS.admin);
  for (const p of ["/admin", "/admin/usuarios", "/admin/cursos", "/admin/agenda", "/admin/auditoria", "/operacoes/nova"]) {
    await page.goto(p);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});
