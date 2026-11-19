// Cliente da API local. Todos os números exibidos vêm daqui (nenhum valor fictício no código).
export type Json = Record<string, unknown>;

function token(): string {
  try {
    return localStorage.getItem("moxml_token") ?? "";
  } catch {
    return "";
  }
}

async function req<T>(metodo: string, url: string, corpo?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const t = token();
  if (t) headers["x-api-token"] = t;
  let body: BodyInit | undefined;
  if (form) body = form;
  else if (corpo !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(corpo);
  }
  const r = await fetch(url, { method: metodo, headers, body });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export const api = {
  get: <T>(url: string) => req<T>("GET", url),
  post: <T>(url: string, corpo?: unknown) => req<T>("POST", url, corpo),
  put: <T>(url: string, corpo?: unknown) => req<T>("PUT", url, corpo),
  patch: <T>(url: string, corpo?: unknown) => req<T>("PATCH", url, corpo),
  upload: <T>(url: string, form: FormData) => req<T>("POST", url, undefined, form),
};

export interface Resumo {
  modo: "SIMULADO" | "REAL";
  empresas_cadastradas: number;
  empresas_ativas: number;
  empresas_processadas_ultimo_lote: number;
  xmls_recuperados: number;
  nfe_recuperadas: number;
  nfce_recuperadas: number;
  xmls_pendentes: number;
  documentos_cancelados: number;
  eventos: number;
  lacunas: number;
  certificados_vencendo: number;
  erros_por_fonte_7d: Record<string, number>;
  execucoes_com_erro_7d: number;
  ultima_sincronizacao: string | null;
  proximas_execucoes: string[];
  captura_em_andamento: boolean;
}

export interface Empresa {
  id: number;
  razao_social: string;
  cnpj: string;
  uf: string;
  regime: string | null;
  ativo: boolean;
  captura_nfe: boolean;
  captura_nfce: boolean;
  nome_pasta: string | null;
  certificado: { status: string; validade: string } | null;
  documentos: number;
  pendentes: number;
  ultima_execucao: { status: string; inicio: string } | null;
}

export interface Documento {
  id: number;
  empresa_id: number;
  chave: string;
  modelo: string;
  serie: number;
  numero: number;
  data_emissao: string | null;
  valor: number | null;
  situacao: string;
  tipo_xml: string;
  protocolo: string | null;
  origem: string;
  hash_sha256: string;
  assinatura_ok: boolean | null;
  modo: string;
}

export interface Execucao {
  id: number;
  lote: string;
  empresa: string | null;
  empresa_id: number | null;
  modelo: string | null;
  gatilho: string;
  inicio: string;
  fim: string | null;
  status: string;
  quantidade: number;
  erros: number;
  detalhes: Json | null;
  modo: string;
}

export interface LogItem {
  seq: number;
  momento: string;
  nivel: string;
  mensagem: string;
  execucao_id: number | null;
  empresa: string | null;
}
