import "server-only";
import { z } from "zod";

const schema = z.object({
  APP_ENV: z.enum(["demo", "production"]).default("demo"),
  APP_URL: z.url().default("http://localhost:3000"),
  DATABASE_URL: z.string().min(1, "DATABASE_URL é obrigatória"),
  BETTER_AUTH_SECRET: z.string().min(32, "BETTER_AUTH_SECRET deve ter ao menos 32 caracteres"),
  EMAIL_TRANSPORT: z.enum(["dev", "none"]).default("dev"),
  AUTH_RATE_LIMIT_SIGNIN_WINDOW: z.coerce.number().int().positive().default(60),
  AUTH_RATE_LIMIT_SIGNIN_MAX: z.coerce.number().int().positive().default(5),
  AUTH_RATE_LIMIT_RESET_WINDOW: z.coerce.number().int().positive().default(300),
  AUTH_RATE_LIMIT_RESET_MAX: z.coerce.number().int().positive().default(3),
  LOG_LEVEL: z.enum(["trace", "debug", "info", "warn", "error", "fatal", "silent"]).default("info"),
});

export type Env = z.infer<typeof schema>;

let cached: Env | undefined;

/** Lê e valida variáveis de ambiente na primeira utilização. */
export function env(): Env {
  if (!cached) {
    const parsed = schema.safeParse(process.env);
    if (!parsed.success) {
      const issues = parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
      throw new Error(`Configuração inválida: ${issues}`);
    }
    if (parsed.data.APP_ENV === "production" && parsed.data.EMAIL_TRANSPORT === "dev") {
      throw new Error("EMAIL_TRANSPORT=dev não é permitido com APP_ENV=production");
    }
    cached = parsed.data;
  }
  return cached;
}

export const isDemoEnv = () => env().APP_ENV === "demo";

/** Apenas para testes: força nova leitura das variáveis de ambiente. */
export function resetEnvCache() {
  cached = undefined;
}
