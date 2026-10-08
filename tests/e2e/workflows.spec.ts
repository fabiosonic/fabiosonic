import { expect, test } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import { USERS, login } from "./helpers";

test("analista publica operação e usuário a consulta", async ({ browser }) => {
  const title = `Operação E2E ${Date.now()}`;
  const analyst = await browser.newPage();
  await login(analyst, USERS.analyst);
  await analyst.goto("/operacoes/nova");
  await analyst.getByLabel("Título").fill(title);
  await analyst.getByLabel("Vencimento").fill("2027-01-15");
  const leg = analyst.locator("ol > li").first();
  await leg.getByLabel("Strike").fill("36");
  await leg.getByLabel("Prêmio").fill("1,50");
  await analyst.getByLabel("Resumo").fill("Resumo da operação de teste ponta a ponta.");
  await analyst.getByLabel("Premissas").fill("Premissas hipotéticas para o teste automatizado.");
  await analyst.getByLabel("Riscos").fill("Perda limitada ao prêmio pago na montagem.");
  await analyst.getByRole("button", { name: "Salvar como rascunho" }).click();
  await expect(analyst.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(analyst.getByText("Rascunho").first()).toBeVisible();
  await analyst.getByRole("button", { name: "Publicar" }).click();
  await analyst.getByRole("dialog").getByRole("button", { name: "Publicar" }).click();
  await expect(analyst.getByText("Publicado").first()).toBeVisible();

  const user = await browser.newPage();
  await login(user, USERS.user);
  await user.goto("/operacoes");
  await user.getByRole("link", { name: title }).click();
  await expect(user.getByRole("heading", { level: 1 })).toHaveText(title);
  await user.goto("/notificacoes");
  await expect(user.getByText(title).first()).toBeVisible();
});

test("pedido de análise: usuário abre, analista responde, usuário vê resposta", async ({ browser }) => {
  const subject = `Pedido E2E ${Date.now()}`;
  const user = await browser.newPage();
  await login(user, USERS.user);
  await user.goto("/solicitacoes/nova");
  await user.getByLabel("Assunto").fill(subject);
  await user.getByLabel("Descrição").fill("Gostaria de entender o risco desta estrutura de opções.");
  await user.getByRole("button", { name: "Enviar pedido" }).click();
  await expect(user.getByRole("heading", { level: 1 })).toHaveText(subject);
  const url = user.url();

  const analyst = await browser.newPage();
  await login(analyst, USERS.analyst);
  await analyst.goto(url);
  await analyst.getByLabel("Mensagem").fill("Resposta da equipe de análise.");
  await analyst.getByRole("button", { name: "Enviar" }).click();
  await expect(analyst.getByText("Resposta da equipe de análise.")).toBeVisible();

  await user.reload();
  await expect(user.getByText("Resposta da equipe de análise.")).toBeVisible();
  await expect(user.getByText("Respondido").first()).toBeVisible();
});

test("carteira: conexão demonstrativa, sincronização e importação CSV", async ({ page }) => {
  await login(page, USERS.user2);
  await page.goto("/carteira");
  await expect(page.getByText("Modo demonstrativo", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Conectar (demonstração)" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Conectar (demonstração)" }).click();
  await expect(page.getByText("Conectado").first()).toBeVisible();
  await page.getByRole("button", { name: "Sincronizar agora" }).click();
  await expect(page.getByText(/Sincronização concluída/)).toBeVisible();
  await expect(page.getByRole("table", { name: "Histórico de sincronizações" }).getByText("Concluída").first()).toBeVisible();

  const file = path.join(os.tmpdir(), `posicoes-${Date.now()}.csv`);
  fs.writeFileSync(file, "ticker;quantidade;preco_medio;data_referencia\nABEV3;500;12,10;01/10/2026\nBBAS3;0;10;01/10/2026\n");
  await page.goto("/carteira/importar");
  await page.getByLabel("Arquivo CSV").setInputFiles(file);
  await page.getByRole("button", { name: "Pré-visualizar" }).click();
  await expect(page.getByText(/Quantidade deve ser um inteiro/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar importação" })).toBeDisabled();

  fs.writeFileSync(file, "ticker;quantidade;preco_medio;data_referencia\nABEV3;500;12,10;01/10/2026\n");
  await page.getByLabel("Arquivo CSV").setInputFiles(file);
  await page.getByRole("button", { name: "Pré-visualizar" }).click();
  await page.getByRole("button", { name: "Confirmar importação" }).click();
  await expect(page.getByText(/Importação concluída: 1 linha/)).toBeVisible();
  await page.goto("/carteira");
  await expect(page.getByRole("cell", { name: "ABEV3" })).toBeVisible();
});

test("curso: marcar aula como concluída persiste", async ({ page }) => {
  await login(page, USERS.user2);
  await page.goto("/cursos/estrategias-com-travas");
  await page.getByRole("link", { name: "Trava de alta com CALL" }).click();
  await page.getByRole("button", { name: "Marcar como concluída" }).click();
  await expect(page.getByRole("button", { name: "Marcar como não concluída" })).toBeVisible();
  await page.goto("/cursos");
  await expect(page.getByRole("progressbar", { name: "Progresso em Estratégias com travas" })).toHaveAttribute("aria-valuenow", "33");
});
