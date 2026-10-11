// Canal de e-mail: envio por SMTP (Google Workspace, Zoho, Outlook, Brevo etc.)
// e leitura das respostas por IMAP. Cada envio leva identificação do escritório
// (NBC PG 01, item 4(r)) e link de descadastro com cabeçalho List-Unsubscribe.
import nodemailer, { type Transporter } from 'nodemailer';
import { ImapFlow } from 'imapflow';
import { simpleParser } from 'mailparser';
import { createHmac } from 'node:crypto';
import { config } from '../config.ts';
import type { Configuracoes } from '../configuracoes.ts';
import { escaparHtml } from '../util/texto.ts';

let transporte: Transporter | null = null;
export const emailConfigurado = () => Boolean(config.smtp.host && config.smtp.usuario && config.smtp.senha);
export const imapConfigurado = () => Boolean(config.imap.host && config.imap.usuario && config.imap.senha);

/** Para testes: substitui o transporte SMTP. */
export const definirTransporte = (t: Transporter | null) => (transporte = t);

function obterTransporte() {
  if (!transporte) {
    transporte = nodemailer.createTransport({
      host: config.smtp.host,
      port: config.smtp.porta,
      secure: config.smtp.seguro,
      auth: { user: config.smtp.usuario, pass: config.smtp.senha },
    });
  }
  return transporte;
}

export const tokenDescadastro = (contatoId: number) =>
  `${contatoId}.${createHmac('sha256', config.segredoSessao).update(`descadastro:${contatoId}`).digest('hex').slice(0, 20)}`;

export function validarTokenDescadastro(token: string): number | null {
  const [id] = token.split('.');
  return tokenDescadastro(Number(id)) === token ? Number(id) : null;
}

export function assinatura(c: Configuracoes) {
  const e = c.escritorio;
  const linhas = [
    e.cargo_assinatura ? `${e.cargo_assinatura} — ${e.nome}` : e.nome,
    [e.razao_social, e.cnpj && `CNPJ ${e.cnpj}`, e.crc_organizacao && `CRC ${e.crc_organizacao}`].filter(Boolean).join(' · '),
    e.responsavel_tecnico.nome && `Responsável técnico: ${e.responsavel_tecnico.nome}${e.responsavel_tecnico.categoria ? ` (${e.responsavel_tecnico.categoria})` : ''}${e.responsavel_tecnico.crc ? ` — CRC ${e.responsavel_tecnico.crc}` : ''}`,
    [e.telefone, e.site].filter(Boolean).join(' · '),
  ].filter(Boolean);
  return linhas.join('\n');
}

export function montarEmail(c: Configuracoes, corpo: string, contatoId: number) {
  const link = `${config.urlPublica}/descadastro/${tokenDescadastro(contatoId)}`;
  const rodape = `Se preferir não receber novos contatos, responda "parar" ou acesse: ${link}`;
  const texto = `${corpo.trim()}\n\n--\n${assinatura(c)}\n\n${rodape}`;
  const html = `<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.55;color:#1f2328">${escaparHtml(corpo.trim())
    .split(/\n{2,}/)
    .map((p) => `<p style="margin:0 0 12px">${p.replace(/\n/g, '<br>')}</p>`)
    .join('')}<p style="margin:20px 0 0;color:#57606a;font-size:12px;border-top:1px solid #d0d7de;padding-top:10px">${escaparHtml(assinatura(c)).replace(/\n/g, '<br>')}</p><p style="color:#8c959f;font-size:11px">Se preferir não receber novos contatos, responda "parar" ou <a href="${link}" style="color:#8c959f">clique aqui</a>.</p></div>`;
  return { texto, html, link };
}

export async function enviarEmail(opcoes: {
  para: string;
  assunto: string;
  texto: string;
  html: string;
  linkDescadastro: string;
  emRespostaA?: string | null;
}) {
  const info = await obterTransporte().sendMail({
    from: config.smtp.remetente || config.smtp.usuario,
    to: opcoes.para,
    subject: opcoes.assunto,
    text: opcoes.texto,
    html: opcoes.html,
    inReplyTo: opcoes.emRespostaA ?? undefined,
    references: opcoes.emRespostaA ?? undefined,
    headers: {
      'List-Unsubscribe': `<${opcoes.linkDescadastro}>`,
      'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    },
  });
  return { idExterno: info.messageId as string };
}

export type EmailRecebido = { de: string; assunto: string; texto: string; idMensagem: string; emRespostaA: string | null; referencias: string[]; data: Date };

/** Lê e-mails não lidos da caixa de entrada e os marca como lidos. */
export async function lerCaixaDeEntrada(limite = 50): Promise<EmailRecebido[]> {
  const cliente = new ImapFlow({
    host: config.imap.host,
    port: config.imap.porta,
    secure: config.imap.seguro,
    auth: { user: config.imap.usuario, pass: config.imap.senha },
    logger: false,
  });
  const recebidos: EmailRecebido[] = [];
  await cliente.connect();
  const trava = await cliente.getMailboxLock('INBOX');
  try {
    const uids = (await cliente.search({ seen: false }, { uid: true })) || [];
    for (const uid of uids.slice(0, limite)) {
      const msg = await cliente.fetchOne(String(uid), { envelope: true, source: true, headers: ['in-reply-to', 'references'] }, { uid: true });
      if (!msg || !msg.envelope) continue;
      const analisado = await simpleParser(msg.source!);
      const refs = analisado.references;
      recebidos.push({
        de: msg.envelope.from?.[0]?.address?.toLowerCase() ?? '',
        assunto: msg.envelope.subject ?? '',
        texto: analisado.text ?? '',
        idMensagem: msg.envelope.messageId ?? `uid-${uid}`,
        emRespostaA: analisado.inReplyTo ?? null,
        referencias: Array.isArray(refs) ? refs : refs ? [refs] : [],
        data: msg.envelope.date ?? new Date(),
      });
      await cliente.messageFlagsAdd(String(uid), ['\\Seen'], { uid: true });
    }
  } finally {
    trava.release();
    await cliente.logout();
  }
  return recebidos;
}
