import { useState } from "react";
import { Documento, Empresa } from "../api";
import { Cartao, Erro, Selo, Tabela, fmt, useDados } from "../ui";

interface Pagina { total: number; pagina: number; limite: number; itens: Documento[]; }
interface Pendente { chave: string; empresa_id: number; modelo: string; serie: number; numero: number; status: string; situacao_sefaz: string | null; origem: string; tentativas: number; mensagem: string | null; }

export default function Documentos() {
  const { dados: empresas } = useDados<Empresa[]>("/api/empresas");
  const [f, setF] = useState({ empresa_id: "", modelo: "", situacao: "", chave: "", inicio: "", fim: "" });
  const [pagina, setPagina] = useState(1);
  const qs = new URLSearchParams(Object.entries({ ...f, pagina: String(pagina), limite: "50" }).filter(([, v]) => v)).toString();
  const { dados, erro } = useDados<Pagina>(`/api/documentos?${qs}`, [qs]);
  const { dados: pend } = useDados<Pendente[]>(`/api/pendentes${f.empresa_id ? `?empresa_id=${f.empresa_id}` : ""}`, [f.empresa_id]);
  const nome = (id: number) => empresas?.find((e) => e.id === id)?.razao_social ?? id;
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPagina(1); };
  const paginas = dados ? Math.max(1, Math.ceil(dados.total / dados.limite)) : 1;
  return (
    <>
      <h1>Documentos</h1>
      <p className="subtitulo">XMLs integrais recuperados e validados (assinatura, chave, protocolo).</p>
      <Erro msg={erro} />
      <Cartao titulo={`XMLs (${fmt.num(dados?.total)})`}>
        <div className="filtros">
          <select value={f.empresa_id} onChange={(e) => set("empresa_id", e.target.value)}>
            <option value="">Todas as empresas</option>{empresas?.map((e) => <option key={e.id} value={e.id}>{e.razao_social}</option>)}</select>
          <select value={f.modelo} onChange={(e) => set("modelo", e.target.value)}><option value="">Modelo</option><option value="55">NF-e 55</option><option value="65">NFC-e 65</option></select>
          <select value={f.situacao} onChange={(e) => set("situacao", e.target.value)}><option value="">Situação</option>
            {["AUTORIZADA", "CANCELADA", "DENEGADA", "SEM_PROTOCOLO"].map((s) => <option key={s}>{s}</option>)}</select>
          <input placeholder="chave (parte)" value={f.chave} onChange={(e) => set("chave", e.target.value)} />
          <input type="date" value={f.inicio} onChange={(e) => set("inicio", e.target.value)} title="emissão a partir de" />
          <input type="date" value={f.fim} onChange={(e) => set("fim", e.target.value)} title="emissão até" />
        </div>
        <Tabela<Documento> linhas={dados?.itens ?? null} chave={(d) => d.id} vazio="Nenhum documento com estes filtros."
          cols={[
            { t: "Empresa", r: (d) => nome(d.empresa_id) },
            { t: "Mod.", r: (d) => d.modelo }, { t: "Série", r: (d) => d.serie },
            { t: "Número", r: (d) => fmt.num(d.numero), cls: "num" },
            { t: "Emissão", r: (d) => fmt.data(d.data_emissao) },
            { t: "Valor", r: (d) => fmt.moeda(d.valor), cls: "num" },
            { t: "Situação", r: (d) => <Selo v={d.situacao} /> },
            { t: "Assinatura", r: (d) => (d.assinatura_ok ? "íntegra" : d.assinatura_ok === false ? "inválida" : "—") },
            { t: "Origem", r: (d) => d.origem },
            { t: "Chave", r: (d) => <span className="mono" title={d.hash_sha256}>{fmt.chave(d.chave)}</span> },
            { t: "", r: (d) => <a href={`/api/documentos/${d.id}/xml`}>XML</a> },
          ]} />
        <div className="paginacao">
          <button className="secundario" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
          <span className="mudo">Página {pagina} de {paginas}</span>
          <button className="secundario" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>Próxima</button>
        </div>
      </Cartao>
      <Cartao titulo={`Pendentes de XML integral (${pend?.length ?? 0})`}>
        <p className="mudo">Chaves conhecidas por fonte legítima cujo XML ainda não foi obtido. Situação SEFAZ não equivale a XML.</p>
        <Tabela<Pendente> linhas={pend} chave={(p) => p.chave} vazio="Nenhuma pendência."
          cols={[
            { t: "Empresa", r: (p) => nome(p.empresa_id) }, { t: "Mod.", r: (p) => p.modelo },
            { t: "Série/Número", r: (p) => `${p.serie}/${p.numero}` }, { t: "Status", r: (p) => <Selo v={p.status} /> },
            { t: "Situação SEFAZ", r: (p) => <Selo v={p.situacao_sefaz} /> }, { t: "Tentativas", r: (p) => p.tentativas, cls: "num" },
            { t: "Mensagem", r: (p) => <span className="mudo">{p.mensagem ?? "—"}</span> },
          ]} />
      </Cartao>
    </>
  );
}
