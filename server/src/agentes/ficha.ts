// Ficha consolidada de um lead e a lista de FATOS numerados que os agentes de
// redação podem usar. Só entra como fato o que tem origem registrada.
import { json, todos, um } from '../banco.ts';
import { primeiroNome, tituloProprio } from '../util/texto.ts';

export type Ficha = {
  lead: Record<string, any>;
  empresa: Record<string, any>;
  socios: Record<string, any>[];
  contatos: Record<string, any>[];
};

export function carregarFicha(leadId: number): Ficha | null {
  const lead = um<Record<string, any>>('SELECT * FROM leads WHERE id = ?', leadId);
  if (!lead) return null;
  const empresa = um<Record<string, any>>('SELECT * FROM empresas WHERE id = ?', lead.empresa_id)!;
  const socios = todos('SELECT * FROM socios WHERE empresa_id = ? ORDER BY id', empresa.id);
  const contatos = todos('SELECT * FROM contatos WHERE empresa_id = ? ORDER BY optin DESC, id', empresa.id);
  return { lead, empresa, socios, contatos };
}

export const nomeEmpresa = (e: Record<string, any>) => tituloProprio(e.nome_fantasia || e.razao_social || 'sua empresa');

/** Sócio a quem a mensagem é dirigida: preferência para quem administra. */
export function destinatario(f: Ficha) {
  const administrador = f.socios.find((s) => /administrador|s[óo]cio-administrador|diretor|presidente|titular/i.test(s.qualificacao ?? ''));
  return administrador ?? f.socios[0] ?? null;
}

const diasDesde = (data: string | null) => (data ? Math.floor((Date.now() - new Date(data).getTime()) / 86_400_000) : null);

export function montarFatos(f: Ficha, incluirPessoais = true): string[] {
  const e = f.empresa;
  const fatos: string[] = [];
  fatos.push(`Empresa: ${nomeEmpresa(e)}${e.razao_social && e.nome_fantasia ? ` (razão social ${tituloProprio(e.razao_social)})` : ''}`);
  if (e.cnae_descricao || e.cnae_principal) fatos.push(`Atividade principal (CNAE): ${e.cnae_descricao ?? e.cnae_principal}`);
  if (e.segmento) fatos.push(`Segmento: ${e.segmento}`);
  if (e.municipio) fatos.push(`Localização: ${tituloProprio(e.municipio)}/${e.uf}`);
  const dias = diasDesde(e.data_abertura);
  if (dias !== null) fatos.push(dias <= 365 ? `Empresa aberta há ${dias} dias (${e.data_abertura})` : `Empresa ativa desde ${e.data_abertura?.slice(0, 4)}`);
  if (e.porte) fatos.push(`Porte cadastral: ${tituloProprio(e.porte)}`);
  if (e.optante_mei) fatos.push('Optante pelo MEI (cadastro)');
  else if (e.optante_simples !== null && e.optante_simples !== undefined) fatos.push(e.optante_simples ? 'Optante pelo Simples Nacional (cadastro)' : 'Não optante pelo Simples Nacional (cadastro)');
  const cnaesSec = json<{ descricao: string }[]>(e.cnaes_secundarios, []);
  if (cnaesSec.length) fatos.push(`Atividades secundárias: ${cnaesSec.slice(0, 3).map((c) => c.descricao).join('; ')}`);
  const site = json<{ resumo?: string; sinais?: string[] }>(e.site_resumo, {});
  if (site.resumo) fatos.push(`Site da empresa: ${site.resumo}`);
  for (const s of site.sinais ?? []) fatos.push(`Observado no site: ${s}`);
  if (f.socios.length > 1) fatos.push(`Quadro societário com ${f.socios.length} pessoas`);
  if (incluirPessoais) {
    const d = destinatario(f);
    if (d) {
      fatos.push(`Destinatário: ${primeiroNome(d.nome)} — ${d.qualificacao ?? 'sócio'}`);
      const outras = json<{ razao_social: string | null }[]>(d.outras_empresas, []);
      if (outras.length) fatos.push(`${primeiroNome(d.nome)} também participa de ${outras.length} outra(s) empresa(s)${outras[0]?.razao_social ? `, como ${tituloProprio(outras[0].razao_social)}` : ''}`);
      for (const fc of json<string[]>(d.fatos_conversa, [])) fatos.push(`Contado pelo lead: ${fc}`);
    }
  }
  for (const n of json<string[]>(f.lead.necessidades, []).filter((n) => n.startsWith('Informado pelo lead'))) fatos.push(n);
  return fatos.map((t, i) => `[F${i + 1}] ${t}`);
}
