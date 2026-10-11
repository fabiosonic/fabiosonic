// Avisos ao responsável humano. O sistema só chama você quando o lead quer falar
// com uma pessoa, pergunta preço, traz dúvida técnica ou aceita reunião.
import { config } from './config.ts';
import { emailConfigurado, enviarEmail } from './canais/email.ts';
import { enviarTextoWhatsapp, whatsappConfigurado } from './canais/whatsapp.ts';
import { log } from './registro.ts';
import { escaparHtml } from './util/texto.ts';

export async function avisarResponsavel(titulo: string, texto: string, linkLead?: string) {
  const resultados: string[] = [];
  const corpo = `${texto}${linkLead ? `\n\nAbrir no painel: ${linkLead}` : ''}`;
  if (config.responsavel.email && emailConfigurado()) {
    try {
      await enviarEmail({
        para: config.responsavel.email,
        assunto: `[Central Comercial] ${titulo}`,
        texto: corpo,
        html: `<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5"><h3 style="margin:0 0 8px">${escaparHtml(titulo)}</h3><p style="white-space:pre-line">${escaparHtml(texto)}</p>${linkLead ? `<p><a href="${linkLead}">Abrir no painel</a></p>` : ''}</div>`,
        linkDescadastro: config.urlPublica,
      });
      resultados.push('email');
    } catch (e) {
      log('notificacao', `falha ao avisar por e-mail: ${(e as Error).message}`);
    }
  }
  if (config.responsavel.whatsapp && whatsappConfigurado()) {
    try {
      await enviarTextoWhatsapp(config.responsavel.whatsapp, `🔔 ${titulo}\n\n${corpo}`);
      resultados.push('whatsapp');
    } catch (e) {
      // Na API oficial, texto livre só chega se você tiver falado com o número
      // da empresa nas últimas 24 h; o painel continua mostrando o aviso.
      log('notificacao', `falha ao avisar por WhatsApp: ${(e as Error).message}`);
    }
  }
  return resultados;
}
