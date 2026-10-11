// Canal de WhatsApp com dois provedores:
// - "cloud": API oficial do WhatsApp Business (Meta). Recomendado. Mensagem
//   iniciada pela empresa só com MODELO aprovado pela Meta; texto livre apenas
//   dentro da janela de 24 h após a última mensagem do lead.
// - "evolution": Evolution API (WhatsApp Web não oficial). Funciona com número
//   comum, mas viola os termos do WhatsApp e o número pode ser banido,
//   principalmente com envios para quem não salvou o contato.
import { createHmac, timingSafeEqual } from 'node:crypto';
import { config } from '../config.ts';

let fetchImpl: typeof fetch = (...a) => fetch(...a);
export const definirFetchWhatsapp = (f: typeof fetch) => (fetchImpl = f);

export const whatsappConfigurado = () => {
  const w = config.whatsapp;
  if (w.provedor === 'cloud') return Boolean(w.cloudToken && w.cloudIdNumero);
  if (w.provedor === 'evolution') return Boolean(w.evolutionUrl && w.evolutionChave && w.evolutionInstancia);
  return false;
};

/** Na API oficial, a primeira mensagem (fora da janela de 24 h) precisa usar modelo aprovado. */
export const exigeModeloForaDaJanela = () => config.whatsapp.provedor === 'cloud';

async function chamar(url: string, corpo: unknown, cabecalhos: Record<string, string>) {
  const r = await fetchImpl(url, { method: 'POST', headers: { 'content-type': 'application/json', ...cabecalhos }, body: JSON.stringify(corpo), signal: AbortSignal.timeout(20000) });
  const dados: any = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`WhatsApp HTTP ${r.status}: ${JSON.stringify(dados).slice(0, 300)}`);
  return dados;
}

export async function enviarTextoWhatsapp(numero: string, texto: string): Promise<{ idExterno: string }> {
  const w = config.whatsapp;
  if (w.provedor === 'cloud') {
    const d = await chamar(
      `https://graph.facebook.com/${w.cloudVersaoApi}/${w.cloudIdNumero}/messages`,
      { messaging_product: 'whatsapp', to: numero, type: 'text', text: { preview_url: false, body: texto } },
      { authorization: `Bearer ${w.cloudToken}` },
    );
    return { idExterno: d.messages?.[0]?.id ?? '' };
  }
  if (w.provedor === 'evolution') {
    const d = await chamar(`${w.evolutionUrl}/message/sendText/${w.evolutionInstancia}`, { number: numero, text: texto }, { apikey: w.evolutionChave });
    return { idExterno: d.key?.id ?? '' };
  }
  throw new Error('WhatsApp não configurado');
}

/**
 * Envia o modelo aprovado. Sugestão de modelo (categoria Marketing) para cadastrar na Meta:
 * "Olá, {{1}}! Aqui é da {{2}}. {{3}} Podemos conversar? Se preferir não receber mensagens, responda PARAR."
 * {{3}} recebe a frase personalizada escrita pela IA para este lead.
 */
export async function enviarModeloWhatsapp(numero: string, variaveis: string[]): Promise<{ idExterno: string }> {
  const w = config.whatsapp;
  if (w.provedor !== 'cloud') return enviarTextoWhatsapp(numero, variaveis.join(' '));
  if (!w.nomeModelo) throw new Error('Defina WA_NOME_MODELO com o modelo aprovado pela Meta');
  const d = await chamar(
    `https://graph.facebook.com/${w.cloudVersaoApi}/${w.cloudIdNumero}/messages`,
    {
      messaging_product: 'whatsapp',
      to: numero,
      type: 'template',
      template: {
        name: w.nomeModelo,
        language: { code: w.idiomaModelo },
        components: [{ type: 'body', parameters: variaveis.map((t) => ({ type: 'text', text: t.replace(/\s*\n+\s*/g, ' ').slice(0, 900) })) }],
      },
    },
    { authorization: `Bearer ${w.cloudToken}` },
  );
  return { idExterno: d.messages?.[0]?.id ?? '' };
}

export type EventoWhatsapp =
  | { tipo: 'mensagem'; de: string; nome: string | null; texto: string; idExterno: string; data: Date }
  | { tipo: 'status'; idExterno: string; status: 'enviada' | 'entregue' | 'lida' | 'falhou'; erro?: string };

export function validarAssinaturaCloud(corpoBruto: string, assinatura: string | undefined): boolean {
  if (!config.whatsapp.cloudSegredoApp) return true;
  if (!assinatura?.startsWith('sha256=')) return false;
  const esperado = createHmac('sha256', config.whatsapp.cloudSegredoApp).update(corpoBruto).digest('hex');
  const a = Buffer.from(assinatura.slice(7));
  const b = Buffer.from(esperado);
  return a.length === b.length && timingSafeEqual(a, b);
}

const STATUS_CLOUD: Record<string, 'enviada' | 'entregue' | 'lida' | 'falhou'> = { sent: 'enviada', delivered: 'entregue', read: 'lida', failed: 'falhou' };

export function interpretarWebhookCloud(corpo: any): EventoWhatsapp[] {
  const eventos: EventoWhatsapp[] = [];
  for (const entrada of corpo?.entry ?? []) {
    for (const mudanca of entrada.changes ?? []) {
      const v = mudanca.value ?? {};
      const nomes = new Map<string, string>((v.contacts ?? []).map((c: any) => [c.wa_id, c.profile?.name]));
      for (const m of v.messages ?? []) {
        const texto = m.text?.body ?? m.button?.text ?? m.interactive?.button_reply?.title ?? (m.type ? `[${m.type}]` : '');
        eventos.push({ tipo: 'mensagem', de: m.from, nome: nomes.get(m.from) ?? null, texto, idExterno: m.id, data: new Date(Number(m.timestamp) * 1000) });
      }
      for (const s of v.statuses ?? []) {
        const status = STATUS_CLOUD[s.status];
        if (status) eventos.push({ tipo: 'status', idExterno: s.id, status, erro: s.errors?.[0]?.title });
      }
    }
  }
  return eventos;
}

export function interpretarWebhookEvolution(corpo: any): EventoWhatsapp[] {
  const evento = String(corpo?.event ?? '').toLowerCase();
  const d = corpo?.data ?? {};
  if (evento.includes('messages.upsert') || evento.includes('messages_upsert')) {
    if (d.key?.fromMe) return [];
    const de = String(d.key?.remoteJid ?? '').split('@')[0];
    const texto = d.message?.conversation ?? d.message?.extendedTextMessage?.text ?? '';
    if (!de || !texto || String(d.key?.remoteJid).endsWith('@g.us')) return [];
    return [{ tipo: 'mensagem', de, nome: d.pushName ?? null, texto, idExterno: d.key?.id ?? '', data: new Date((d.messageTimestamp ?? Date.now() / 1000) * 1000) }];
  }
  if (evento.includes('messages.update') || evento.includes('messages_update')) {
    const mapa: Record<string, 'entregue' | 'lida'> = { DELIVERY_ACK: 'entregue', READ: 'lida', PLAYED: 'lida' };
    const status = mapa[d.status];
    if (status && d.keyId) return [{ tipo: 'status', idExterno: d.keyId, status }];
  }
  return [];
}
