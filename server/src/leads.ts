// Entrada de leads por qualquer origem (manual, importação, formulário do site).
// Todo lead nasce com a origem registrada — requisito da política de dados.
import { executar, um } from './banco.ts';
import { adicionarContato } from './agentes/enriquecedor.ts';
import { registrarEvento } from './registro.ts';
import { cnpjValido, ehCelular, normalizarEmail, normalizarTelefone, somenteDigitos } from './util/texto.ts';

export type NovoLead = {
  cnpj?: string;
  empresa?: string;
  site?: string;
  email?: string;
  whatsapp?: string;
  nome?: string;
  origem: string;
  origemDetalhe?: string;
  optin?: boolean;
};

export function criarLead(n: NovoLead): { leadId: number; novo: boolean } {
  const cnpj = somenteDigitos(n.cnpj);
  if (cnpj && !cnpjValido(cnpj)) throw new Error(`CNPJ inválido: ${n.cnpj}`);
  const email = normalizarEmail(n.email);
  const tel = normalizarTelefone(n.whatsapp);
  if (!cnpj && !email && !tel) throw new Error('Informe ao menos CNPJ, e-mail ou WhatsApp');

  const chave = cnpj || `pendente-${tel ?? email}`;
  const existente = um<{ id: number }>('SELECT id FROM empresas WHERE cnpj = ?', chave);
  const empresaId =
    existente?.id ??
    executar(
      'INSERT INTO empresas (cnpj, nome_fantasia, site, origem, origem_detalhe) VALUES (?, ?, ?, ?, ?)',
      chave,
      n.empresa ?? (n.nome ? `Contato de ${n.nome}` : null),
      n.site ?? null,
      n.origem,
      n.origemDetalhe ?? null,
    ).id;

  let socioId: number | null = null;
  if (n.nome) {
    executar("INSERT OR IGNORE INTO socios (empresa_id, nome, qualificacao, origem) VALUES (?, ?, 'Contato informado', ?)", empresaId, n.nome.toUpperCase(), n.origem);
    socioId = um<{ id: number }>('SELECT id FROM socios WHERE empresa_id = ? AND nome = ?', empresaId, n.nome.toUpperCase())?.id ?? null;
  }
  if (email) adicionarContato(empresaId, 'email', email, n.origemDetalhe ?? n.origem, { socioId, optin: n.optin });
  if (tel) adicionarContato(empresaId, ehCelular(tel) ? 'whatsapp' : 'telefone', tel, n.origemDetalhe ?? n.origem, { socioId, optin: n.optin });

  const lead = um<{ id: number }>('SELECT id FROM leads WHERE empresa_id = ?', empresaId);
  if (lead) return { leadId: lead.id, novo: false };
  const etapa = cnpj ? 'mapeada' : 'respondeu';
  const { id } = executar('INSERT INTO leads (empresa_id, etapa, temperatura) VALUES (?, ?, ?)', empresaId, etapa, n.optin ? 'quente' : null);
  registrarEvento(id, 'lead_criado', n.origem.startsWith('formulario') ? 'prospector' : 'humano', { origem: n.origem, detalhe: n.origemDetalhe });
  return { leadId: id, novo: true };
}

/** Importação em lote: uma linha por empresa — "cnpj;email;whatsapp;nome" (só o CNPJ é obrigatório). */
export function importarLista(texto: string, origem: string) {
  const resultado = { criados: 0, existentes: 0, erros: [] as string[] };
  for (const [i, linha] of texto.split(/\r?\n/).entries()) {
    const partes = linha.split(/[;,\t]/).map((p) => p.trim());
    if (!partes[0] || /cnpj/i.test(partes[0])) continue;
    try {
      const r = criarLead({ cnpj: partes[0], email: partes[1], whatsapp: partes[2], nome: partes[3], origem: 'importacao', origemDetalhe: origem });
      r.novo ? resultado.criados++ : resultado.existentes++;
    } catch (e) {
      resultado.erros.push(`linha ${i + 1}: ${(e as Error).message}`);
    }
  }
  return resultado;
}
