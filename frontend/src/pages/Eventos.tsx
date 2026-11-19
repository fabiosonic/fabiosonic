import { useState } from "react";
import { Empresa } from "../api";
import { Cartao, Erro, Tabela, fmt, useDados } from "../ui";

interface Ev { id: number; empresa_id: number; chave: string; tipo_evento: string; descricao: string | null; sequencia: number; protocolo: string | null; data_evento: string | null; origem: string; }

export default function Eventos() {
  const { dados: empresas } = useDados<Empresa[]>("/api/empresas");
  const [tipo, setTipo] = useState("");
  const { dados, erro } = useDados<Ev[]>(`/api/eventos${tipo ? `?tipo=${tipo}` : ""}`, [tipo]);
  const nome = (id: number) => empresas?.find((e) => e.id === id)?.razao_social ?? id;
  return (
    <>
      <h1>Eventos</h1>
      <p className="subtitulo">Cancelamentos, cartas de correção e demais eventos vinculados às notas de saída.</p>
      <Erro msg={erro} />
      <Cartao titulo={`Eventos (${dados?.length ?? 0})`} acoes={
        <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos os tipos</option><option value="110111">110111 Cancelamento</option>
          <option value="110112">110112 Cancelamento por substituição</option><option value="110110">110110 Carta de Correção</option>
        </select>}>
        <Tabela<Ev> linhas={dados} chave={(e) => e.id} vazio="Nenhum evento registrado."
          cols={[
            { t: "Empresa", r: (e) => nome(e.empresa_id) }, { t: "Tipo", r: (e) => `${e.tipo_evento} ${e.descricao ?? ""}` },
            { t: "Seq.", r: (e) => e.sequencia, cls: "num" }, { t: "Data", r: (e) => fmt.data(e.data_evento) },
            { t: "Protocolo", r: (e) => <span className="mono">{e.protocolo ?? "—"}</span> },
            { t: "Chave", r: (e) => <span className="mono">{fmt.chave(e.chave)}</span> }, { t: "Origem", r: (e) => e.origem },
          ]} />
      </Cartao>
    </>
  );
}
