// Agente Enriquecedor: completa a ficha da empresa e dos sócios.
// Fontes (todas com origem registrada):
//  - Cadastro CNPJ (Receita, via APIs públicas): dados da empresa e QSA;
//  - Recorte local dos Dados Abertos: outras empresas de cada sócio (grupo econômico);
//  - Site institucional da empresa: atividade, público, sinais e e-mails corporativos;
//  - Conversas com o próprio lead (agente Atendente): fatos que ele mesmo contou.
// Não usa bases vazadas/compradas, consulta de CPF nem raspagem de redes pessoais.
import { executar, json, todos, um } from '../banco.ts';
import { consultarCnpj, CnpjNaoEncontrado } from '../fontes/cnpj.ts';
import { outrasEmpresasDoSocio } from '../fontes/receita-dados-abertos.ts';
import { lerSite } from '../fontes/site.ts';
import { mudarEtapa } from '../funil.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { log, registrarEvento } from '../registro.ts';
import { segmentoPorCnae } from '../util/segmentos.ts';
import { dominioCorporativo, ehCelular, normalizarEmail, normalizarTelefone, pareceEmailDeContador } from '../util/texto.ts';
import { INSTRUCOES } from './instrucoes.ts';

const AGENTE = 'enriquecedor';

/** Um mesmo e-mail/telefone em várias empresas costuma ser do contador que fez o cadastro. */
export function contatoCompartilhado(tipo: string, valor: string, empresaId: number) {
  const r = um<{ n: number }>('SELECT COUNT(DISTINCT empresa_id) n FROM contatos WHERE tipo = ? AND valor = ? AND empresa_id <> ?', tipo, valor, empresaId);
  return (r?.n ?? 0) >= 2;
}

export function adicionarContato(
  empresaId: number,
  tipo: 'email' | 'whatsapp' | 'telefone',
  valor: string,
  origem: string,
  extra: { socioId?: number | null; optin?: boolean; provavelContador?: boolean } = {},
) {
  const bloqueado = Boolean(um('SELECT 1 FROM bloqueios WHERE valor = ?', valor));
  const provavelContador = extra.provavelContador ?? false;
  executar(
    `INSERT INTO contatos (empresa_id, socio_id, tipo, valor, origem, optin, provavel_contador, bloqueado)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(empresa_id, tipo, valor) DO UPDATE SET optin = MAX(optin, excluded.optin)`,
    empresaId,
    extra.socioId ?? null,
    tipo,
    valor,
    origem,
    extra.optin ?? false,
    provavelContador,
    bloqueado,
  );
  // Ao detectar o compartilhamento, marca também os registros anteriores.
  if (contatoCompartilhado(tipo, valor, empresaId)) executar('UPDATE contatos SET provavel_contador = 1 WHERE tipo = ? AND valor = ?', tipo, valor);
}

export async function enriquecerLead(leadId: number, opcoes: { manterEtapa?: boolean } = {}) {
  const etapa = (para: Parameters<typeof mudarEtapa>[1], motivo: string) => {
    if (!opcoes.manterEtapa) mudarEtapa(leadId, para, AGENTE, motivo);
  };
  const lead = um<{ empresa_id: number }>('SELECT empresa_id FROM leads WHERE id = ?', leadId);
  if (!lead) return;
  const empresa = um<Record<string, any>>('SELECT * FROM empresas WHERE id = ?', lead.empresa_id)!;
  const fontes: string[] = [];

  // 1) Cadastro CNPJ
  if (/^\d{14}$/.test(empresa.cnpj)) {
    try {
      const c = await consultarCnpj(empresa.cnpj);
      fontes.push(c.fonte);
      executar(
        `UPDATE empresas SET razao_social = COALESCE(?, razao_social), nome_fantasia = COALESCE(?, nome_fantasia),
           cnae_principal = COALESCE(?, cnae_principal), cnae_descricao = COALESCE(?, cnae_descricao), cnaes_secundarios = ?,
           natureza_juridica = ?, porte = COALESCE(?, porte), capital_social = COALESCE(?, capital_social),
           data_abertura = COALESCE(?, data_abertura), situacao = ?, optante_simples = ?, optante_mei = ?,
           logradouro = COALESCE(?, logradouro), numero = COALESCE(?, numero), bairro = COALESCE(?, bairro),
           municipio = COALESCE(?, municipio), uf = COALESCE(?, uf), cep = COALESCE(?, cep),
           email_cadastro = COALESCE(?, email_cadastro), telefone_cadastro = COALESCE(?, telefone_cadastro),
           atualizado_em = datetime('now') WHERE id = ?`,
        c.razao_social, c.nome_fantasia, c.cnae_principal, c.cnae_descricao, JSON.stringify(c.cnaes_secundarios),
        c.natureza_juridica, c.porte, c.capital_social, c.data_abertura, c.situacao, c.optante_simples, c.optante_mei,
        c.logradouro, c.numero, c.bairro, c.municipio, c.uf, c.cep, c.email?.toLowerCase() ?? null, c.telefones[0] ?? null, empresa.id,
      );
      for (const s of c.socios) {
        executar(
          `INSERT INTO socios (empresa_id, nome, qualificacao, faixa_etaria, data_entrada, documento_mascarado, origem)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(empresa_id, nome) DO UPDATE SET qualificacao = excluded.qualificacao,
             faixa_etaria = COALESCE(excluded.faixa_etaria, faixa_etaria), data_entrada = COALESCE(excluded.data_entrada, data_entrada),
             documento_mascarado = COALESCE(excluded.documento_mascarado, documento_mascarado)`,
          empresa.id, s.nome, s.qualificacao, s.faixa_etaria, s.data_entrada, s.documento_mascarado, `QSA via ${c.fonte}`,
        );
      }
      for (const t of c.telefones) registrarTelefone(empresa.id, t, `Cadastro CNPJ (${c.fonte})`);
      const email = normalizarEmail(c.email);
      if (email) adicionarContato(empresa.id, 'email', email, `Cadastro CNPJ (${c.fonte})`, { provavelContador: pareceEmailDeContador(email) });
    } catch (e) {
      if (e instanceof CnpjNaoEncontrado) {
        etapa('descartada', 'CNPJ não encontrado na Receita');
        return;
      }
      throw e; // fonte indisponível: o agendador tenta de novo depois
    }
  }

  const atual = um<Record<string, any>>('SELECT * FROM empresas WHERE id = ?', empresa.id)!;
  if (atual.situacao && atual.situacao !== 'ATIVA') {
    etapa('descartada', `Situação cadastral ${atual.situacao}`);
    return;
  }

  // Contatos já vindos dos Dados Abertos
  const emailRf = normalizarEmail(atual.email_cadastro);
  if (emailRf) adicionarContato(empresa.id, 'email', emailRf, atual.origem_detalhe ?? 'Cadastro CNPJ', { provavelContador: pareceEmailDeContador(emailRf) });
  if (atual.telefone_cadastro) registrarTelefone(empresa.id, atual.telefone_cadastro, atual.origem_detalhe ?? 'Cadastro CNPJ');

  // 2) Outras empresas de cada sócio (grupo econômico)
  const basico = String(atual.cnpj).slice(0, 8);
  for (const s of todos<{ id: number; nome: string; documento_mascarado: string | null }>('SELECT id, nome, documento_mascarado FROM socios WHERE empresa_id = ?', empresa.id)) {
    const outras = outrasEmpresasDoSocio(s.nome, s.documento_mascarado, basico);
    if (outras.length) executar('UPDATE socios SET outras_empresas = ? WHERE id = ?', JSON.stringify(outras), s.id);
  }

  // 3) Site institucional
  let site: string | null = atual.site;
  if (!site) {
    const corporativo = todos<{ valor: string }>("SELECT valor FROM contatos WHERE empresa_id = ? AND tipo = 'email' AND provavel_contador = 0", empresa.id)
      .map((c) => dominioCorporativo(c.valor))
      .find(Boolean);
    if (corporativo) site = corporativo;
  }
  const segmento = segmentoPorCnae(atual.cnae_principal);
  if (site) {
    const leitura = await lerSite(site).catch(() => null);
    if (leitura) {
      fontes.push('site');
      for (const e of leitura.emails) adicionarContato(empresa.id, 'email', e, `Site ${leitura.url}`);
      let resumo = leitura.descricao || leitura.titulo;
      let sinais: string[] = [];
      try {
        const analise = await perguntarJson<{ resumo: string; segmento: string; sinais: string[] }>({
          tarefa: 'analise_site',
          sistema: INSTRUCOES.analistaSite,
          usuario: `Empresa: ${atual.nome_fantasia || atual.razao_social}\nCNAE: ${atual.cnae_principal} ${atual.cnae_descricao ?? ''}\nTítulo: ${leitura.titulo}\nDescrição: ${leitura.descricao}\nTexto do site:\n${leitura.texto}`,
          dadosPessoais: false,
        });
        resumo = analise.resumo || resumo;
        sinais = (analise.sinais ?? []).slice(0, 6);
      } catch (e) {
        log(AGENTE, `análise do site indisponível: ${(e as Error).message}`);
      }
      executar('UPDATE empresas SET site = ?, site_resumo = ? WHERE id = ?', leitura.url, JSON.stringify({ resumo, sinais, redes: leitura.redes }), empresa.id);
    }
  }

  executar("UPDATE empresas SET segmento = ?, enriquecida_em = datetime('now') WHERE id = ?", segmento, empresa.id);
  registrarEvento(leadId, 'enriquecimento', AGENTE, { fontes, socios: um<{ n: number }>('SELECT COUNT(*) n FROM socios WHERE empresa_id = ?', empresa.id)?.n });
  etapa('enriquecida', `Fontes: ${fontes.join(', ') || 'dados já importados'}`);
}

function registrarTelefone(empresaId: number, bruto: string, origem: string) {
  const tel = normalizarTelefone(bruto);
  if (!tel) return;
  adicionarContato(empresaId, ehCelular(tel) ? 'whatsapp' : 'telefone', tel, origem);
}

/** Fatos que o lead contou na conversa ficam na ficha (dado fornecido pelo titular). */
export function registrarFatosDaConversa(leadId: number, fatos: string[]) {
  if (!fatos.length) return;
  const lead = um<{ empresa_id: number }>('SELECT empresa_id FROM leads WHERE id = ?', leadId);
  if (!lead) return;
  const socio = um<{ id: number; fatos_conversa: string }>('SELECT id, fatos_conversa FROM socios WHERE empresa_id = ? ORDER BY id LIMIT 1', lead.empresa_id);
  const necessidades = json<string[]>(um<{ necessidades: string }>('SELECT necessidades FROM leads WHERE id = ?', leadId)?.necessidades, []);
  if (socio) {
    const atuais = json<string[]>(socio.fatos_conversa, []);
    executar('UPDATE socios SET fatos_conversa = ? WHERE id = ?', JSON.stringify([...new Set([...atuais, ...fatos])].slice(-30)), socio.id);
  } else {
    executar('UPDATE leads SET necessidades = ? WHERE id = ?', JSON.stringify([...necessidades, ...fatos.map((f) => `Informado pelo lead: ${f}`)]), leadId);
  }
  registrarEvento(leadId, 'fatos_conversa', 'atendente', { fatos });
}

export function pendentesDeEnriquecimento(limite: number) {
  return todos<{ id: number }>("SELECT id FROM leads WHERE etapa = 'mapeada' ORDER BY criado_em LIMIT ?", limite);
}
