import { expect, test } from "@playwright/test";
import { USERS, login } from "./helpers";

test("login inválido mostra mensagem e válido abre o painel", async ({ page }) => {
  await page.goto("/painel");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("E-mail").fill(USERS.user);
  await page.getByLabel("Senha").fill("errada123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "E-mail ou senha inválidos" })).toBeVisible();
  await login(page, USERS.user);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Olá, Carla");
  await expect(page.getByText("Resumo da carteira")).toBeVisible();
});

test("logout encerra a sessão", async ({ page }) => {
  await login(page, USERS.user);
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/carteira");
  await expect(page).toHaveURL(/\/login$/);
});

test("administrador cria usuário e ele recupera o acesso pela caixa de e-mail local", async ({ browser }) => {
  const email = `recupera${Date.now()}@teste.local`;
  const admin = await browser.newPage();
  await login(admin, USERS.admin);
  await admin.goto("/admin/usuarios");
  await admin.getByRole("textbox", { name: "Nome" }).fill("Usuário Recuperação");
  await admin.getByRole("textbox", { name: "E-mail" }).fill(email);
  await admin.getByRole("textbox", { name: "Senha temporária" }).fill("Temporaria@123");
  await admin.getByRole("button", { name: "Criar usuário" }).click();
  await expect(admin.getByText("Usuário criado.")).toBeVisible();

  const page = await browser.newPage();
  await page.goto("/recuperar-acesso");
  await page.getByLabel("E-mail").fill(email);
  await page.getByRole("button", { name: "Enviar link" }).click();
  await expect(page.getByText("Pedido registrado")).toBeVisible();

  await page.goto("/dev/emails");
  const msg = page.locator("li").filter({ has: page.getByTestId("email-to").getByText(email, { exact: true }) });
  const body = await msg.getByTestId("email-body").innerText();
  const url = body.match(/https?:\/\/\S+/)![0];
  await page.goto(url);
  await expect(page).toHaveURL(/\/redefinir-senha\?token=/);
  await page.getByRole("textbox", { name: "Nova senha", exact: true }).fill("NovaSenha@2026");
  await page.getByRole("textbox", { name: "Confirmar nova senha" }).fill("NovaSenha@2026");
  await page.getByRole("button", { name: "Salvar nova senha" }).click();
  await expect(page.getByText("Senha redefinida")).toBeVisible();

  // O link é de uso único: reutilizá-lo leva à mensagem de link inválido.
  await page.goto(url);
  await expect(page.getByText(/inválido, expirado ou já utilizado/)).toBeVisible();

  await login(page, email, "NovaSenha@2026");
});
