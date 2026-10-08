import "dotenv/config";

// Testes usam SEMPRE o banco isolado de teste.
if (!process.env.TEST_DATABASE_URL) throw new Error("TEST_DATABASE_URL não definida (veja .env.example).");
process.env.DATABASE_URL = process.env.TEST_DATABASE_URL;
process.env.APP_ENV = "demo";
process.env.EMAIL_TRANSPORT = "dev";
process.env.LOG_LEVEL = "silent";
