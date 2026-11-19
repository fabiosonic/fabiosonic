import { ReactNode, useCallback, useEffect, useState } from "react";
import { api } from "./api";

export const fmt = {
  data: (s: string | null | undefined) => (s ? new Date(s).toLocaleString("pt-BR") : "—"),
  dia: (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString("pt-BR") : "—"),
  moeda: (v: number | null | undefined) =>
    v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }),
  num: (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString("pt-BR")),
  cnpj: (c: string) =>
    c.length === 14 ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c,
  chave: (c: string) => c.replace(/(.{4})/g, "$1 ").trim(),
};

/** Carrega dados da API com estado de carregamento/erro e recarga manual. */
export function useDados<T>(url: string | null, deps: unknown[] = []) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  const recarregar = useCallback(async () => {
    if (!url) return;
    setCarregando(true);
    try {
      setDados(await api.get<T>(url));
      setErro(null);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);
  useEffect(() => {
    void recarregar();
  }, [recarregar]);
  return { dados, erro, carregando, recarregar };
}

const TOM: Record<string, string> = {
  AUTORIZADA: "ok", SUCESSO: "ok", VALIDO: "ok", DISPONIVEL: "ok", RECUPERADA: "ok", CONFIRMADO: "ok", OK: "ok",
  CANCELADA: "neutro", DENEGADA: "alerta", PARCIAL: "alerta", VENCENDO: "alerta", NAO_COMPROVADO: "alerta",
  PENDENTE: "alerta", SEM_PROTOCOLO: "alerta", INUTILIZADA: "neutro", CHAVE_CONHECIDA_XML_PENDENTE: "alerta",
  NAO_CONSTA_NA_SEFAZ: "info", LACUNA_NAO_INVESTIGADA: "alerta", EM_ANDAMENTO: "info", NAO_CONFIGURADO: "neutro",
  ERRO: "erro", FALHA: "erro", VENCIDO: "erro", INDISPONIVEL: "neutro", INTERROMPIDA: "erro", SEM_FONTE: "erro",
  BLOQUEADO: "erro", AVISO: "alerta", INFO: "info", TESTE: "erro", REAL: "ok",
};

export function Selo({ v }: { v: string | null | undefined }) {
  if (!v) return <span className="selo neutro">—</span>;
  return <span className={`selo ${TOM[v] ?? "neutro"}`}>{v.replaceAll("_", " ")}</span>;
}

export function Cartao({ titulo, acoes, children }: { titulo?: string; acoes?: ReactNode; children: ReactNode }) {
  return (
    <section className="cartao">
      {(titulo || acoes) && (
        <header>
          {titulo && <h2>{titulo}</h2>}
          <div className="acoes">{acoes}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({ rotulo, valor, detalhe, tom }: { rotulo: string; valor: ReactNode; detalhe?: string; tom?: string }) {
  return (
    <div className={`kpi ${tom ?? ""}`}>
      <span className="rotulo">{rotulo}</span>
      <strong>{valor}</strong>
      {detalhe && <span className="detalhe">{detalhe}</span>}
    </div>
  );
}

export interface Coluna<T> {
  t: string;
  r: (l: T) => ReactNode;
  cls?: string;
}

export function Tabela<T>({ cols, linhas, vazio, chave }: { cols: Coluna<T>[]; linhas: T[] | null; vazio?: string; chave: (l: T) => string | number }) {
  if (!linhas) return <p className="mudo">Carregando…</p>;
  if (!linhas.length) return <p className="mudo">{vazio ?? "Nenhum registro."}</p>;
  return (
    <div className="rolagem">
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c.t} className={c.cls}>{c.t}</th>)}</tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={chave(l)}>{cols.map((c) => <td key={c.t} className={c.cls}>{c.r(l)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Erro({ msg }: { msg: string | null }) {
  return msg ? <div className="aviso erro">{msg}</div> : null;
}

export function Ok({ msg }: { msg: string | null }) {
  return msg ? <div className="aviso ok">{msg}</div> : null;
}
