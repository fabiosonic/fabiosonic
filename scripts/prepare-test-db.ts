/**
 * Recria o banco de TESTE do zero: apaga o schema, aplica as migrações e executa o seed demonstrativo.
 * Recusa-se a rodar se TEST_DATABASE_URL não parecer um banco de teste.
 */
import "dotenv/config";
import { execSync } from "node:child_process";
import { Client } from "pg";

async function main() {
  const url = process.env.TEST_DATABASE_URL;
  if (!url) throw new Error("TEST_DATABASE_URL não definida.");
  const dbName = new URL(url).pathname.slice(1);
  if (!/test/i.test(dbName) || url === process.env.DATABASE_URL) {
    throw new Error(`Banco "${dbName}" não parece ser de teste; abortando por segurança.`);
  }
  const client = new Client({ connectionString: url });
  await client.connect();
  await client.query("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;");
  await client.end();

  const env = { ...process.env, DATABASE_URL: url, APP_ENV: "demo" };
  execSync("npx prisma migrate deploy", { stdio: "inherit", env });
  execSync("npx tsx prisma/seed.ts", { stdio: "inherit", env });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
