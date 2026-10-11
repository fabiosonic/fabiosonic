// Rotas públicas: webhooks do WhatsApp, formulário de captação do site e
// descadastro com um clique. Não exigem sessão, mas cada uma valida a origem.
import type { FastifyInstance } from 'fastify';
import { config } from '../config.ts';
import { executar, um } from '../banco.ts';
import { processarEntrada, registrarEntrada } from '../agentes/atendente.ts';
import { validarTokenDescadastro } from '../canais/email.ts';
import { interpretarWebhookCloud, interpretarWebhookEvolution, validarAssinaturaCloud, type EventoWhatsapp } from '../canais/whatsapp.ts';
import { lerConfiguracoes } from '../configuracoes.ts';
import { criarLead } from '../leads.ts';
import { log, registrarEvento } from '../registro.ts';
import { escaparHtml } from '../util/texto.ts';

const STATUS_ORDEM = ['enviada', 'entregue', 'lida'];

async function tratarEventosWhatsapp(eventos: EventoWhatsapp[]) {
  for (const ev of eventos) {
    if (ev.tipo === 'status') {
      const m = um<{ id: number; status: string }>("SELECT id, status FROM mensagens WHERE id_externo = ? AND direcao = 'saida'", ev.idExterno);
      if (!m) continue;
      if (ev.status === 'falhou') executar("UPDATE mensagens SET status = 'falhou', erro = ? WHERE id = ?", ev.erro ?? 'falha informada pelo WhatsApp', m.id);
      else if (STATUS_ORDEM.indexOf(ev.status) > STATUS_ORDEM.indexOf(m.status)) executar('UPDATE mensagens SET status = ? WHERE id = ?', ev.status, m.id);
      continue;
    }
    const id = registrarEntrada({ canal: 'whatsapp', de: ev.de, texto: ev.texto, idExterno: ev.idExterno, nome: ev.nome });
    // Resposta em tempo real; se falhar, o agente Atendente tenta de novo no próximo ciclo
    if (id) void processarEntrada(id).catch((e) => log('atendente', `processamento adiado: ${e.message}`));
  }
}

const limitePorIp = new Map<string, number[]>();
function dentroDoLimite(ip: string, max = 5, janelaMs = 3600_000) {
  const agora = Date.now();
  const lista = (limitePorIp.get(ip) ?? []).filter((t) => agora - t < janelaMs);
  lista.push(agora);
  limitePorIp.set(ip, lista);
  return lista.length <= max;
}

const pagina = (titulo: string, corpo: string) => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escaparHtml(titulo)}</title>
<style>body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f6f7f9;color:#14171c;display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}
main{background:#fff;border:1px solid #e3e6ea;border-radius:16px;padding:32px;max-width:440px;box-shadow:0 8px 30px rgba(0,0,0,.06)}h1{font-size:20px;margin:0 0 12px}p{line-height:1.55;color:#4a5260}
button{background:#14171c;color:#fff;border:0;border-radius:10px;padding:12px 18px;font-size:15px;cursor:pointer}</style></head><body><main>${corpo}</main></body></html>`;

export function rotasPublicas(app: FastifyInstance) {
  // WhatsApp Cloud API (Meta): verificação do webhook
  app.get<{ Querystring: Record<string, string> }>('/webhooks/whatsapp', async (r, resposta) => {
    if (r.query['hub.mode'] === 'subscribe' && r.query['hub.verify_token'] === config.whatsapp.cloudTokenVerificacao && config.whatsapp.cloudTokenVerificacao) {
      return resposta.type('text/plain').send(r.query['hub.challenge']);
    }
    return resposta.code(403).send('token inválido');
  });

  app.post('/webhooks/whatsapp', async (r, resposta) => {
    if (!validarAssinaturaCloud((r as any).corpoBruto ?? '', r.headers['x-hub-signature-256'] as string | undefined)) return resposta.code(401).send();
    await tratarEventosWhatsapp(interpretarWebhookCloud(r.body));
    return { ok: true };
  });

  app.post<{ Querystring: { token?: string } }>('/webhooks/evolution', async (r, resposta) => {
    if (!config.whatsapp.evolutionTokenWebhook || r.query.token !== config.whatsapp.evolutionTokenWebhook) return resposta.code(401).send();
    await tratarEventosWhatsapp(interpretarWebhookEvolution(r.body));
    return { ok: true };
  });

  // Formulário de contato do site (captação receptiva). Exige consentimento explícito.
  app.post<{ Body: Record<string, string | boolean> }>('/publico/lead', async (r, resposta) => {
    resposta.header('access-control-allow-origin', '*');
    const b = r.body ?? {};
    if (b.website) return { ok: true }; // campo-isca contra robôs
    if (!dentroDoLimite(r.ip)) return resposta.code(429).send({ erro: 'Muitas solicitações' });
    if (b.consentimento !== true && b.consentimento !== 'true' && b.consentimento !== 'on') {
      return resposta.code(400).send({ erro: 'É necessário aceitar o contato do escritório.' });
    }
    try {
      const { leadId } = criarLead({
        cnpj: String(b.cnpj ?? ''),
        empresa: String(b.empresa ?? '') || undefined,
        email: String(b.email ?? ''),
        whatsapp: String(b.whatsapp ?? b.telefone ?? ''),
        nome: String(b.nome ?? '') || undefined,
        origem: 'formulario_site',
        origemDetalhe: `Formulário do site (${r.headers.referer ?? 'origem não informada'}) com consentimento`,
        optin: true,
      });
      const texto = String(b.mensagem ?? '').trim();
      if (texto) {
        const contato = um<{ tipo: string; valor: string }>("SELECT c.tipo, c.valor FROM contatos c JOIN leads l ON l.empresa_id = c.empresa_id WHERE l.id = ? AND c.tipo IN ('email','whatsapp') ORDER BY c.tipo LIMIT 1", leadId);
        if (contato) {
          const id = registrarEntrada({ canal: contato.tipo as 'email' | 'whatsapp', de: contato.valor, texto, idExterno: `form-${Date.now()}`, assunto: 'Contato pelo site' });
          if (id) void processarEntrada(id).catch(() => undefined);
        }
      }
      return { ok: true, mensagem: 'Recebemos seu contato. Retornaremos em breve.' };
    } catch (e) {
      return resposta.code(400).send({ erro: (e as Error).message });
    }
  });
  app.options('/publico/lead', async (_r, resposta) =>
    resposta.header('access-control-allow-origin', '*').header('access-control-allow-headers', 'content-type').header('access-control-allow-methods', 'POST').send(),
  );

  // Descadastro (link no rodapé de todos os e-mails)
  app.get<{ Params: { token: string } }>('/descadastro/:token', async (r, resposta) => {
    const id = validarTokenDescadastro(r.params.token);
    const nome = lerConfiguracoes().escritorio.nome;
    if (!id) return resposta.code(404).type('text/html').send(pagina('Link inválido', '<h1>Link inválido</h1><p>Este link de descadastro não é válido.</p>'));
    return resposta.type('text/html').send(
      pagina('Parar de receber contatos', `<h1>Parar de receber contatos</h1><p>Confirme para não receber novos contatos comerciais de ${escaparHtml(nome)}.</p><form method="post"><button type="submit">Confirmar descadastro</button></form>`),
    );
  });

  app.post<{ Params: { token: string } }>('/descadastro/:token', async (r, resposta) => {
    const id = validarTokenDescadastro(r.params.token);
    if (!id) return resposta.code(404).send();
    const contato = um<{ id: number; empresa_id: number; tipo: string; valor: string }>('SELECT id, empresa_id, tipo, valor FROM contatos WHERE id = ?', id);
    if (contato) {
      executar('INSERT OR IGNORE INTO bloqueios (valor, tipo, motivo) VALUES (?, ?, ?)', contato.valor, contato.tipo, 'Descadastro pelo link');
      executar('UPDATE contatos SET bloqueado = 1 WHERE valor = ?', contato.valor);
      const lead = um<{ id: number; etapa: string }>('SELECT id, etapa FROM leads WHERE empresa_id = ?', contato.empresa_id);
      if (lead) {
        executar("UPDATE mensagens SET status = 'descartada', erro = 'descadastro' WHERE lead_id = ? AND direcao = 'saida' AND status IN ('aguardando_aprovacao','aprovada') AND contato_id = ?", lead.id, contato.id);
        registrarEvento(lead.id, 'descadastro', 'operacoes', { canal: contato.tipo });
        const restantes = um<{ n: number }>('SELECT COUNT(*) n FROM contatos WHERE empresa_id = ? AND bloqueado = 0 AND tipo IN (\'email\',\'whatsapp\')', contato.empresa_id)!.n;
        if (!restantes && !['cliente', 'com_voce'].includes(lead.etapa)) {
          executar("UPDATE leads SET etapa = 'perdida', motivo_perda = 'descadastro', proxima_acao = NULL, proxima_acao_em = NULL WHERE id = ?", lead.id);
        }
      }
    }
    return resposta.type('text/html').send(pagina('Descadastro confirmado', '<h1>Pronto</h1><p>Você não receberá novos contatos comerciais. Obrigado.</p>'));
  });
}
