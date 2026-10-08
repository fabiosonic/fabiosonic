import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

test("usuário não vê nem acessa a administração", async ({ page }) => {
  await login(page, USERS.user);
  const nav = page.getByRole("navigation", { name: "Navegação principal" });
  await expect(nav.getByRole("link", { name: "Usuários" })).toHaveCount(0);
  await page.goto("/admin/usuarios");
  await expect(page.getByRole("heading", { name: "Acesso negado" })).toBeVisible();
  const res = await page.request.post("/api/admin/usuarios", { data: {}, headers: { origin: new URL(page.url()).origin } });
  expect(res.status()).toBe(403);
});

test("usuário não acessa pedido de outro usuário", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/solicitacoes");
  await expect(page.getByText("Pedido de outro usuário")).toHaveCount(0);
});

test("administrador acessa indicadores, usuários e auditoria", async ({ page }) => {
  await login(page, USERS.admin);
  await page.getByRole("link", { name: "Indicadores" }).click();
  await expect(page.getByRole("heading", { name: "Indicadores" })).toBeVisible();
  await page.getByRole("link", { name: "Auditoria" }).click();
  await page.getByLabel("Ação (prefixo)").fill("auth.");
  await page.getByRole("button", { name: "Filtrar" }).click();
  await expect(page.getByRole("cell", { name: "auth.login" }).first()).toBeVisible();
});
