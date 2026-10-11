// API do painel. Todas as rotas exigem sessão (ver autenticacao.ts).
import type { FastifyInstance } from 'fastify';
import { executar, json, todos, um } from '../banco.ts';
import { lerConfiguracoes, pendenciasIdentificacao, salvarConfiguracoes, type Configuracoes } from '../configuracoes.ts';
import { config } from '../config.ts';
import { ETAPAS, mudarEtapa, agendarProximaAcao, type Etapa } from '../funil.ts';
import { AGENTES, executarAgente, situacaoAgentes } from '../agendador.ts';
import { indicadores } from '../agentes/operacoes.ts';
import { redigirMensagem, type TipoMensagem } from '../agentes/redator.ts';
import { regrasDeterministicas } from '../agentes/revisor.ts';
import { carregarFicha, montarFatos, nomeEmpresa } from '../agentes/ficha.ts';
import { ROTULO_MOTIVO } from '../agentes/atendente.ts';
import { briefingDiario } from '../agentes/diretor.ts';
import { situacaoProvedores } from '../ia/roteador.ts';
import { emailConfigurado, imapConfigurado } from '../canais/email.ts';
import { whatsappConfigurado } from '../canais/whatsapp.ts';
import { criarLead, importarLista } from '../leads.ts';
import { registrarEvento } from '../registro.ts';
import { SEGMENTOS } from '../util/segmentos.ts';
import { agoraSql } from '../util/tempo.ts';
import { tituloProprio } from '../util/texto.ts';
import { exigirSessao } from './autenticacao.ts';

const canais = () => ({
  email: emailConfigurado(),
  imap: imapConfigurado(),
  whatsapp: whatsappConfigurado(),
  whatsappProvedor: config.whatsapp.provedor || null,
  avisoResponsavel: { email: Boolean(config.responsavel.email), whatsapp: Boolean(config.responsavel.whatsapp) },
});

const resumoLead = (l: Record<string, any>) => ({
  id: l.id,
  etapa: l.etapa,
  pontuacao: l.pontuacao,
  temperatura: l.temperatura,
  empresa: tituloProprio(l.nome_fantasia || l.razao_social) || 'Sem nome',
  razaoSocial: l.razao_social,
  cnpj: l.cnpj,
  segmento: l.segmento,
  cidade: l.municipio ? `${tituloProprio(l.municipio)}/${l.uf}` : null,
  dataAbertura: l.data_abertura,
  origem: l.origem,
  proximaAcao: l.proxima_acao,
  proximaAcaoEm: l.proxima_acao_em,
  atualizadoEm: l.atualizado_em,
  criadoEm: l.criado_em,
  ultimaMensagem: l.ultima_mensagem ?? null,
});

export function rotasApi(app: FastifyInstance) {
  app.register(async (api) => {
    api.addHook('preHandler', exigirSessao);

    api.get('/api/contadores', async () => ({
      atendimentos: um<{ n: number }>("SELECT COUNT(*) n FROM atendimentos_humanos WHERE status <> 'resolvido'")!.n,
      aprovacao: um<{ n: number }>("SELECT COUNT(*) n FROM mensagens WHERE status = 'aguardando_aprovacao'")!.n,
      modo: lerConfiguracoes().autonomia.modo,
      iaSimulada: config.ia.simulada,
    }));

    api.get('/api/painel', async () => {
      const c = lerConfiguracoes();
      const atendimentos = todos<Record<string, any>>(
        `SELECT a.*, e.nome_fantasia, e.razao_social, e.segmento, l.pontuacao FROM atendimentos_humanos a
         JOIN leads l ON l.id = a.lead_id JOIN empresas e ON e.id = l.empresa_id
         WHERE a.status <> 'resolvido' ORDER BY a.criado_em DESC LIMIT 6`,
      ).map((a) => ({ ...a, empresa: tituloProprio(a.nome_fantasia || a.razao_social), rotulo: ROTULO_MOTIVO[a.motivo] ?? a.motivo }));
      const briefing = um<{ detalhe: string; criado_em: string }>("SELECT detalhe, criado_em FROM eventos WHERE tipo = 'briefing' ORDER BY id DESC LIMIT 1");
      const atividade = todos<Record<string, any>>(
        `SELECT ev.id, ev.tipo, ev.agente, ev.detalhe, ev.criado_em, ev.lead_id, e.nome_fantasia, e.razao_social FROM eventos ev
         LEFT JOIN leads l ON l.id = ev.lead_id LEFT JOIN empresas e ON e.id = l.empresa_id
         WHERE ev.tipo NOT IN ('briefing') ORDER BY ev.id DESC LIMIT 14`,
      ).map((e) => ({ ...e, empresa: tituloProprio(e.nome_fantasia || e.razao_social) || null, detalhe: json(e.detalhe, e.detalhe) }));
      return {
        indicadores: indicadores(30),
        atendimentos,
        briefing: briefing ? { ...json<{ texto: string }>(briefing.detalhe, { texto: '' }), criadoEm: briefing.criado_em } : null,
        atividade,
        provedores: situacaoProvedores().filter((p) => p.configurado),
        agentes: situacaoAgentes().map((a) => ({ id: a.id, nome: a.nome, rodando: a.rodando, ultimaExecucao: a.ultimaExecucao, falhas24h: a.falhas24h })),
        canais: canais(),
        modo: c.autonomia.modo,
        pendenciasIdentificacao: pendenciasIdentificacao(c),
        etapas: ETAPAS,
        iaSimulada: config.ia.simulada,
      };
    });

    api.get<{ Querystring: { etapa?: string; busca?: string; segmento?: string; limite?: string; pagina?: string; ordem?: string } }>('/api/leads', async (r) => {
      const q = r.query;
      const filtros: string[] = [];
      const p: (string | number)[] = [];
      if (q.etapa) {
        filtros.push(`l.etapa IN (${q.etapa.split(',').map(() => '?').join(',')})`);
        p.push(...q.etapa.split(','));
      }
      if (q.segmento) {
        filtros.push('e.segmento = ?');
        p.push(q.segmento);
      }
      if (q.busca) {
        filtros.push('(e.nome_fantasia LIKE ? OR e.razao_social LIKE ? OR e.cnpj LIKE ? OR e.municipio LIKE ?)');
        const b = `%${q.busca.trim()}%`;
        p.push(b, b, `%${q.busca.replace(/\D/g, '') || q.busca}%`, b);
      }
      const onde = filtros.length ? `WHERE ${filtros.join(' AND ')}` : '';
      const limite = Math.min(Number(q.limite) || 60, 500);
      const pagina = Math.max(Number(q.pagina) || 1, 1);
      const ordem = q.ordem === 'pontuacao' ? 'l.pontuacao DESC NULLS LAST' : q.ordem === 'abertura' ? 'e.data_abertura DESC' : 'l.atualizado_em DESC';
      const linhas = todos<Record<string, any>>(
        `SELECT l.*, e.cnpj, e.nome_fantasia, e.razao_social, e.segmento, e.municipio, e.uf, e.data_abertura, e.origem,
           (SELECT corpo FROM mensagens m WHERE m.lead_id = l.id ORDER BY m.id DESC LIMIT 1) ultima_mensagem
         FROM leads l JOIN empresas e ON e.id = l.empresa_id ${onde} ORDER BY ${ordem} LIMIT ? OFFSET ?`,
        ...p,
        limite,
        (pagina - 1) * limite,
      );
      const total = um<{ n: number }>(`SELECT COUNT(*) n FROM leads l JOIN empresas e ON e.id = l.empresa_id ${onde}`, ...p)!.n;
      return { total, pagina, leads: linhas.map(resumoLead) };
    });

    api.post<{ Body: { cnpj?: string; email?: string; whatsapp?: string; nome?: string; site?: string; origem?: string; optin?: boolean } }>('/api/leads', async (r, resposta) => {
      try {
        const b = r.body ?? {};
        return criarLead({ ...b, origem: 'cadastro_manual', origemDetalhe: b.origem || 'Cadastrado no painel', optin: Boolean(b.optin) });
      } catch (e) {
        return resposta.code(400).send({ erro: (e as Error).message });
      }
    });

    api.post<{ Body: { texto: string; origem?: string } }>('/api/leads/importar', async (r) => importarLista(r.body?.texto ?? '', r.body?.origem || 'Lista importada no painel'));

    api.get<{ Params: { id: string } }>('/api/leads/:id', async (r, resposta) => {
      const f = carregarFicha(Number(r.params.id));
      if (!f) return resposta.code(404).send({ erro: 'Lead não encontrado' });
      const mensagens = todos('SELECT m.*, c.valor AS destino FROM mensagens m LEFT JOIN contatos c ON c.id = m.contato_id WHERE m.lead_id = ? ORDER BY m.id', f.lead.id).map((m) => ({ ...m, revisao: json(m.revisao, null) }));
      const eventos = todos('SELECT * FROM eventos WHERE lead_id = ? ORDER BY id DESC LIMIT 80', f.lead.id).map((e) => ({ ...e, detalhe: json(e.detalhe, e.detalhe) }));
      const atendimentos = todos('SELECT * FROM atendimentos_humanos WHERE lead_id = ? ORDER BY id DESC', f.lead.id).map((a) => ({ ...a, rotulo: ROTULO_MOTIVO[a.motivo] ?? a.motivo }));
      return {
        lead: { ...f.lead, pontuacao_motivos: json(f.lead.pontuacao_motivos, []), necessidades: json(f.lead.necessidades, []) },
        empresa: { ...f.empresa, nome: nomeEmpresa(f.empresa), municipio: f.empresa.municipio ? tituloProprio(f.empresa.municipio) : null, cnaes_secundarios: json(f.empresa.cnaes_secundarios, []), site_resumo: json(f.empresa.site_resumo, null) },
        socios: f.socios.map((s) => ({ ...s, nome: tituloProprio(s.nome), outras_empresas: json(s.outras_empresas, []), fatos_conversa: json(s.fatos_conversa, []) })),
        contatos: f.contatos,
        fatos: montarFatos(f),
        mensagens,
        eventos,
        atendimentos,
      };
    });

    api.patch<{ Params: { id: string }; Body: { etapa?: Etapa; motivo?: string; evidencia?: string; valorEstimado?: number } }>('/api/leads/:id', async (r, resposta) => {
      const id = Number(r.params.id);
      const b = r.body ?? {};
      if (b.etapa) {
        if (!ETAPAS.some((e) => e.id === b.etapa)) return resposta.code(400).send({ erro: 'Etapa inválida' });
        if (b.etapa === 'cliente' && !b.evidencia?.trim()) return resposta.code(400).send({ erro: 'Para marcar como cliente, informe a evidência do contrato formalizado.' });
        if (b.etapa === 'perdida') executar('UPDATE leads SET motivo_perda = ? WHERE id = ?', b.motivo || 'não registrado', id);
        mudarEtapa(id, b.etapa, 'humano', b.motivo, b.evidencia ? { evidencia: b.evidencia } : {});
        if (['proposta', 'negociacao', 'cliente', 'perdida', 'descartada', 'pausada'].includes(b.etapa)) {
          agendarProximaAcao(id, null, null);
          executar("UPDATE mensagens SET status = 'descartada' WHERE lead_id = ? AND direcao = 'saida' AND status IN ('aguardando_aprovacao','aprovada') AND agente <> 'humano'", id);
        }
        if (b.etapa === 'qualificada') agendarProximaAcao(id, 'primeiro_contato', agoraSql());
      }
      if (b.valorEstimado !== undefined) executar('UPDATE leads SET valor_estimado = ? WHERE id = ?', b.valorEstimado, id);
      return { ok: true };
    });

    // Mensagem escrita por você (vai direto para a fila de envio)
    api.post<{ Params: { id: string }; Body: { canal: 'email' | 'whatsapp'; corpo: string; assunto?: string } }>('/api/leads/:id/mensagens', async (r, resposta) => {
      const f = carregarFicha(Number(r.params.id));
      if (!f) return resposta.code(404).send({ erro: 'Lead não encontrado' });
      const b = r.body;
      const contato = f.contatos.find((c) => c.tipo === b.canal && !c.bloqueado);
      if (!contato) return resposta.code(400).send({ erro: `Lead sem contato de ${b.canal} disponível` });
      const ultimaEntrada = um<{ id_externo: string; assunto: string }>("SELECT id_externo, assunto FROM mensagens WHERE lead_id = ? AND direcao = 'entrada' AND canal = ? ORDER BY id DESC LIMIT 1", f.lead.id, b.canal);
      const { id } = executar(
        `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, assunto, corpo, status, agente, em_resposta_a, agendada_para, revisao)
         VALUES (?, ?, ?, 'saida', ?, ?, 'aprovada', 'atendente', ?, ?, ?)`,
        f.lead.id, contato.id, b.canal, b.assunto || (ultimaEntrada?.assunto ? `Re: ${ultimaEntrada.assunto.replace(/^re:\s*/i, '')}` : null), b.corpo,
        ultimaEntrada?.id_externo ?? null, agoraSql(), JSON.stringify({ aprovado: true, etapas: ['humano'], problemas: [], autor: 'humano' }),
      );
      registrarEvento(f.lead.id, 'mensagem_manual', 'humano', { mensagemId: id, canal: b.canal });
      return { id };
    });

    api.post<{ Params: { id: string }; Body: { tipo?: TipoMensagem; canal?: 'email' | 'whatsapp' } }>('/api/leads/:id/redigir', async (r, resposta) => {
      try {
        const id = await redigirMensagem(Number(r.params.id), r.body?.tipo ?? 'primeiro_contato', r.body?.canal ?? 'email');
        if (!id) return resposta.code(400).send({ erro: 'Lead sem canal de contato utilizável' });
        return { id };
      } catch (e) {
        return resposta.code(503).send({ erro: (e as Error).message });
      }
    });

    api.get('/api/mensagens/aprovacao', async () =>
      todos<Record<string, any>>(
        `SELECT m.*, c.valor AS destino, e.nome_fantasia, e.razao_social, e.segmento, l.pontuacao, l.etapa FROM mensagens m
         JOIN leads l ON l.id = m.lead_id JOIN empresas e ON e.id = l.empresa_id LEFT JOIN contatos c ON c.id = m.contato_id
         WHERE m.status = 'aguardando_aprovacao' ORDER BY m.id`,
      ).map((m) => ({ ...m, empresa: tituloProprio(m.nome_fantasia || m.razao_social), revisao: json(m.revisao, null) })),
    );

    api.post<{ Params: { id: string }; Body: { corpo?: string; assunto?: string } }>('/api/mensagens/:id/aprovar', async (r, resposta) => {
      const m = um<Record<string, any>>("SELECT * FROM mensagens WHERE id = ? AND status = 'aguardando_aprovacao'", Number(r.params.id));
      if (!m) return resposta.code(404).send({ erro: 'Mensagem não está aguardando aprovação' });
      const corpo = r.body?.corpo ?? m.corpo;
      const assunto = r.body?.assunto ?? m.assunto;
      const alertas = regrasDeterministicas(`${assunto ?? ''}\n${corpo}`);
      const revisao = { ...json<Record<string, unknown>>(m.revisao, {}), aprovacaoHumana: { em: agoraSql(), editada: corpo !== m.corpo || assunto !== m.assunto, alertasMantidos: alertas } };
      executar("UPDATE mensagens SET status = 'aprovada', corpo = ?, assunto = ?, revisao = ?, agendada_para = ? WHERE id = ?", corpo, assunto, JSON.stringify(revisao), agoraSql(), m.id);
      registrarEvento(m.lead_id, 'mensagem_aprovada', 'humano', { mensagemId: m.id, editada: revisao.aprovacaoHumana.editada });
      return { ok: true, alertas };
    });

    api.post<{ Body: { ids: number[] } }>('/api/mensagens/aprovar-lote', async (r) => {
      let aprovadas = 0;
      for (const id of r.body?.ids ?? []) {
        const m = um<Record<string, any>>("SELECT * FROM mensagens WHERE id = ? AND status = 'aguardando_aprovacao'", id);
        if (!m || !json<{ aprovado?: boolean }>(m.revisao, {}).aprovado) continue; // lote só aprova o que o revisor liberou
        executar("UPDATE mensagens SET status = 'aprovada', agendada_para = ? WHERE id = ?", agoraSql(), id);
        registrarEvento(m.lead_id, 'mensagem_aprovada', 'humano', { mensagemId: id, lote: true });
        aprovadas++;
      }
      return { aprovadas };
    });

    api.post<{ Params: { id: string }; Body: { motivo?: string; regenerar?: boolean } }>('/api/mensagens/:id/rejeitar', async (r, resposta) => {
      const m = um<Record<string, any>>("SELECT * FROM mensagens WHERE id = ? AND status = 'aguardando_aprovacao'", Number(r.params.id));
      if (!m) return resposta.code(404).send({ erro: 'Mensagem não está aguardando aprovação' });
      executar("UPDATE mensagens SET status = 'descartada', erro = ? WHERE id = ?", `Rejeitada por você${r.body?.motivo ? `: ${r.body.motivo}` : ''}`, m.id);
      registrarEvento(m.lead_id, 'mensagem_rejeitada', 'humano', { mensagemId: m.id, motivo: r.body?.motivo });
      let novaId: number | null = null;
      if (r.body?.regenerar) {
        const rev = json<{ tipo?: TipoMensagem }>(m.revisao, {});
        novaId = await redigirMensagem(m.lead_id, rev.tipo && rev.tipo !== ('conversa' as string) ? rev.tipo : 'primeiro_contato', m.canal).catch(() => null);
      }
      return { ok: true, novaId };
    });

    api.get('/api/conversas', async () =>
      todos<Record<string, any>>(
        `SELECT l.id lead_id, l.etapa, e.nome_fantasia, e.razao_social, m.canal, m.direcao, m.corpo, m.criado_em, m.intencao,
           (SELECT COUNT(*) FROM mensagens x WHERE x.lead_id = l.id AND x.direcao = 'entrada') recebidas
         FROM leads l JOIN empresas e ON e.id = l.empresa_id
         JOIN mensagens m ON m.id = (SELECT MAX(id) FROM mensagens WHERE lead_id = l.id AND status NOT IN ('descartada','aguardando_aprovacao'))
         WHERE EXISTS (SELECT 1 FROM mensagens WHERE lead_id = l.id AND direcao = 'entrada')
         ORDER BY m.id DESC LIMIT 100`,
      ).map((c) => ({ ...c, empresa: tituloProprio(c.nome_fantasia || c.razao_social) })),
    );

    api.get<{ Querystring: { status?: string } }>('/api/atendimentos', async (r) =>
      todos<Record<string, any>>(
        `SELECT a.*, e.nome_fantasia, e.razao_social, e.segmento, e.municipio, e.uf, l.pontuacao, l.etapa,
           (SELECT corpo FROM mensagens WHERE id = a.mensagem_id) mensagem
         FROM atendimentos_humanos a JOIN leads l ON l.id = a.lead_id JOIN empresas e ON e.id = l.empresa_id
         WHERE ${r.query.status === 'todos' ? '1=1' : "a.status <> 'resolvido'"} ORDER BY a.id DESC LIMIT 200`,
      ).map((a) => ({ ...a, empresa: tituloProprio(a.nome_fantasia || a.razao_social), rotulo: ROTULO_MOTIVO[a.motivo] ?? a.motivo })),
    );

    api.post<{ Params: { id: string; acao: string }; Body: { resultado?: Etapa; observacao?: string } }>('/api/atendimentos/:id/:acao', async (r, resposta) => {
      const a = um<Record<string, any>>('SELECT * FROM atendimentos_humanos WHERE id = ?', Number(r.params.id));
      if (!a) return resposta.code(404).send({ erro: 'Atendimento não encontrado' });
      if (r.params.acao === 'assumir') {
        executar("UPDATE atendimentos_humanos SET status = 'assumido' WHERE id = ?", a.id);
        registrarEvento(a.lead_id, 'atendimento_assumido', 'humano', { atendimento: a.id });
      } else if (r.params.acao === 'resolver') {
        executar("UPDATE atendimentos_humanos SET status = 'resolvido', resolvido_em = datetime('now') WHERE id = ?", a.id);
        const destino = r.body?.resultado;
        if (destino && ETAPAS.some((e) => e.id === destino)) mudarEtapa(a.lead_id, destino, 'humano', r.body?.observacao);
        else if (destino === undefined) mudarEtapa(a.lead_id, 'respondeu', 'humano', 'Devolvido ao atendimento automático');
        executar('UPDATE leads SET turnos_automaticos = 0 WHERE id = ?', a.lead_id);
        registrarEvento(a.lead_id, 'atendimento_resolvido', 'humano', { atendimento: a.id, resultado: destino, observacao: r.body?.observacao });
      } else return resposta.code(400).send({ erro: 'Ação inválida' });
      return { ok: true };
    });

    api.get('/api/agentes', async () => ({
      agentes: situacaoAgentes(),
      execucoes: todos("SELECT * FROM execucoes_agentes ORDER BY id DESC LIMIT 60"),
    }));

    api.post<{ Params: { id: string } }>('/api/agentes/:id/executar', async (r, resposta) => {
      if (!AGENTES.some((a) => a.id === r.params.id && a.executar)) return resposta.code(404).send({ erro: 'Agente não executável' });
      if (r.params.id === 'diretor') return { processados: 1, resumo: await briefingDiario(true) };
      return executarAgente(r.params.id);
    });

    api.get('/api/ia', async () => ({
      provedores: situacaoProvedores(),
      porHora: todos(
        `SELECT strftime('%Y-%m-%d %H:00', criado_em) hora, provedor, COUNT(*) total, SUM(sucesso) sucesso
         FROM uso_ia WHERE criado_em >= datetime('now', '-1 day') GROUP BY 1, 2 ORDER BY 1`,
      ),
      porTarefa: todos("SELECT tarefa, provedor, COUNT(*) n FROM uso_ia WHERE sucesso = 1 AND criado_em >= datetime('now', '-7 days') GROUP BY 1, 2 ORDER BY n DESC"),
      falhas: todos("SELECT provedor, modelo, tarefa, status_http, erro, criado_em FROM uso_ia WHERE sucesso = 0 ORDER BY id DESC LIMIT 25"),
      simulada: config.ia.simulada,
      privacidadeEstrita: lerConfiguracoes().ia.privacidade_estrita,
    }));

    api.post<{ Params: { id: string } }>('/api/ia/:id/reativar', async (r) => {
      executar('UPDATE estado_provedores SET pausado_ate = NULL, motivo = NULL WHERE provedor = ?', r.params.id);
      return { ok: true };
    });

    api.get('/api/configuracoes', async () => {
      const c = lerConfiguracoes();
      return { configuracoes: c, pendencias: pendenciasIdentificacao(c), canais: canais(), segmentos: SEGMENTOS, etapas: ETAPAS, urlPublica: config.urlPublica };
    });

    api.put<{ Body: Partial<Configuracoes> }>('/api/configuracoes', async (r) => {
      const c = salvarConfiguracoes(r.body ?? {});
      registrarEvento(null, 'configuracoes_alteradas', 'humano', { chaves: Object.keys(r.body ?? {}) });
      return { configuracoes: c, pendencias: pendenciasIdentificacao(c) };
    });

    api.get('/api/bloqueios', async () => todos('SELECT * FROM bloqueios ORDER BY criado_em DESC LIMIT 500'));
    api.post<{ Body: { valor: string; tipo?: string; motivo?: string } }>('/api/bloqueios', async (r) => {
      const valor = (r.body?.valor ?? '').trim().toLowerCase();
      if (!valor) return { ok: false };
      executar('INSERT OR IGNORE INTO bloqueios (valor, tipo, motivo) VALUES (?, ?, ?)', valor, r.body.tipo ?? (valor.includes('@') ? 'email' : 'whatsapp'), r.body.motivo ?? 'Bloqueio manual');
      executar('UPDATE contatos SET bloqueado = 1 WHERE valor = ?', valor);
      return { ok: true };
    });
  });
}
