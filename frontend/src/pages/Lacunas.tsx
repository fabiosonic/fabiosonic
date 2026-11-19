import { useState } from "react";
import { Empresa } from "../api";
import { Cartao, Erro, Selo, Tabela, fmt, useDados } from "../ui";

interface Lacuna { id: number; empresa: string; modelo: string; serie: number; numero: number; periodo: string | null; classificacao: string; observacao: string | null; ultima_verificacao: string; }

const EXPLICA: Record<string, string> = {
  INUTILIZADA: "Faixa homologada de inutilização cobre o número.",
  CHAVE_CONHECIDA_XML_PENDENTE: "A nota existe (chave conhecida por fonte legítima), mas o XML integral ainda não foi obtido.",
  NAO_CONSTA_NA_SEFAZ: "A consulta oficial respondeu 217 (não consta): número possivelmente pulado, rejeitado ou ainda não inutilizado. Investigar com o emissor.",
  LACUNA_NAO_INVESTIGADA: "Número sem documento e ainda não consultado na fonte oficial.",
};

export default function Lacunas() {
  const { dados: empresas } = useDados<Empresa[]>("/api/empresas");
  const [emp, setEmp] = useState("");
  const [cls, setCls] = useState("");
  const qs = new URLSearchParams(Object.entries({ empresa_id: emp, classificacao: cls }).filter(([, v]) => v)).toString();
  const { dados, erro } = useDados<Lacuna[]>(`/api/lacunas?${qs}`, [qs]);
  return (
    <>
      <h1>Lacunas de numeração</h1>
      <p className="subtitulo">Controle por empresa × modelo × série × ambiente. Lacuna não é prova de XML perdido nem de omissão fiscal.</p>
      <Erro msg={erro} />
      <Cartao titulo="Classificações">
        <Tabela<[string, string]> linhas={Object.entries(EXPLICA)} chave={(l) => l[0]}
          cols={[{ t: "Classificação", r: (l) => <Selo v={l[0]} /> }, { t: "Significado", r: (l) => l[1] }]} />
      </Cartao>
      <Cartao titulo={`Lacunas (${dados?.length ?? 0})`} acoes={<>
        <select value={emp} onChange={(e) => setEmp(e.target.value)}><option value="">Todas as empresas</option>
          {empresas?.map((e) => <option key={e.id} value={e.id}>{e.razao_social}</option>)}</select>
        <select value={cls} onChange={(e) => setCls(e.target.value)}><option value="">Todas</option>
          {Object.keys(EXPLICA).map((c) => <option key={c}>{c}</option>)}</select></>}>
        <Tabela<Lacuna> linhas={dados} chave={(l) => l.id} vazio="Nenhuma lacuna encontrada."
          cols={[
            { t: "Empresa", r: (l) => l.empresa }, { t: "Mod.", r: (l) => l.modelo }, { t: "Série", r: (l) => l.serie },
            { t: "Número", r: (l) => fmt.num(l.numero), cls: "num" }, { t: "Período (estimado)", r: (l) => l.periodo ?? "—" },
            { t: "Classificação", r: (l) => <Selo v={l.classificacao} /> },
            { t: "Observação", r: (l) => <span className="mudo">{l.observacao ?? "—"}</span> },
            { t: "Verificado em", r: (l) => fmt.data(l.ultima_verificacao) },
          ]} />
      </Cartao>
    </>
  );
}
