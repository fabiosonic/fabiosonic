import "server-only";
import pino from "pino";

/** Logger estruturado (JSON). Campos sensíveis são removidos. */
export const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  base: { app: "plataforma-opcoes" },
  redact: {
    paths: [
      "password",
      "*.password",
      "newPassword",
      "*.newPassword",
      "token",
      "*.token",
      "headers.cookie",
      "headers.authorization",
      "*.headers.cookie",
      "*.headers.authorization",
    ],
    censor: "[removido]",
  },
});
