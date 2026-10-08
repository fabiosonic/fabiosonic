import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

test("boleta clássica: calcula trava de alta, salva e reabre", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/simulador?modo=classica");
  await page.getByLabel("Nome").fill("Trava E2E");
  await page.getByLabel("Ativo").selectOption("PETR4");
  await page.getByLabel("Preço de referência (R$)").fill("36,50");

  const legs = page.locator("ol > li");
  await legs.nth(0).getByLabel("Strike (R$)").fill("36");
  await legs.nth(0).getByLabel("Prêmio (R$)").fill("1,85");
  await page.getByRole("button", { name: "Perna", exact: true }).click();
  await legs.nth(1).getByLabel("Operação").selectOption("SELL");
  await legs.nth(1).getByLabel("Strike (R$)").fill("39");
  await legs.nth(1).getByLabel("Prêmio (R$)").fill("0,72");

  const results = page.getByText("Resultado no vencimento").first().locator("xpath=ancestor::section[1]");
  await expect(results).toContainText("R$ 113,00 (débito)");
  await expect(results).toContainText("R$ 37,13");
  await expect(results).toContainText("+R$ 187,00");
  await expect(page.getByRole("table", { name: "Resultado no vencimento por preço do ativo" })).toBeVisible();

  await page.getByRole("button", { name: "Salvar simulação" }).click();
  await expect(page).toHaveURL(/\/simulador\/[a-z0-9]+$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Trava E2E");
  await page.reload();
  await expect(page.locator("ol > li")).toHaveCount(2);
  await expect(page.getByText("R$ 37,13").first()).toBeVisible();

  await page.goto("/simulador/salvas");
  await expect(page.getByRole("link", { name: "Trava E2E" })).toBeVisible();
});

test("boleta rápida: venda de CALL mostra perda ilimitada", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/simulador");
  await page.getByLabel("Operação").selectOption("SELL");
  await page.getByLabel("Strike (R$)").fill("40");
  await page.getByLabel("Prêmio (R$)").fill("0,50");
  await expect(page.getByText("Perda teoricamente ilimitada").first()).toBeVisible();
});

test("previsões: cenários sem probabilidades", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/simulador?modo=previsoes");
  await page.getByLabel("Strike (R$)").fill("36");
  await page.getByLabel("Prêmio (R$)").fill("1");
  await page.getByRole("button", { name: "Sugerir ±10%" }).click();
  const table = page.getByRole("table", { name: "Resultados por cenário" });
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(page.getByText(/Nenhuma probabilidade é atribuída/)).toBeVisible();
});

test("mercado: filtra, ordena e envia contrato ao simulador", async ({ page }) => {
  await login(page, USERS.user);
  await page.goto("/mercado");
  await page.getByLabel("Ativo", { exact: true }).selectOption("VALE3");
  await page.getByLabel("Tipo").selectOption("PUT");
  await page.getByRole("button", { name: "Filtrar" }).click();
  await expect(page).toHaveURL(/ativo=VALE3/);
  await page.getByRole("button", { name: /Strike/ }).click();
  await expect(page).toHaveURL(/ordem=strike/);
  const first = page.getByRole("link", { name: /^Simular VALE/ }).first();
  await first.click();
  await expect(page).toHaveURL(/\/simulador\?opcao=VALE/);
  await expect(page.getByLabel("Instrumento")).toHaveValue("PUT");
});
