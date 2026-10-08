import { expect, test } from "@playwright/test";
import { USERS, expectNoHorizontalOverflow, login } from "./helpers";

test("desktop: navegação lateral, foco visível e páginas sem rolagem horizontal", async ({ page }) => {
  await login(page, USERS.admin);
  const nav = page.getByRole("navigation", { name: "Navegação principal" });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "Painel" })).toHaveAttribute("aria-current", "page");
  for (const p of ["/painel", "/carteira", "/mercado", "/simulador", "/operacoes", "/admin", "/admin/usuarios", "/admin/auditoria", "/admin/cursos", "/admin/agenda"]) {
    await page.goto(p);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
  // Link de pular para o conteúdo é o primeiro item focável.
  await page.goto("/painel");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Pular para o conteúdo" })).toBeFocused();
});
