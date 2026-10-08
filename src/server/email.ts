import "server-only";
import { prisma } from "./db";
import { env } from "./env";
import { logger } from "./logger";

export interface OutgoingEmail {
  to: string;
  subject: string;
  body: string;
}

/**
 * Envio de e-mail. No MVP só existe o transporte "dev", que grava a mensagem
 * na caixa local (/dev/emails). Produção exige integrar um provedor.
 */
export async function sendEmail(mail: OutgoingEmail) {
  if (env().EMAIL_TRANSPORT === "dev") {
    await prisma.devEmail.create({ data: mail });
    return;
  }
  logger.warn({ to: mail.to, subject: mail.subject }, "Nenhum provedor de e-mail configurado; mensagem não enviada");
}
