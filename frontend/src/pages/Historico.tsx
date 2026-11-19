import { useState } from "react";
import { Execucao } from "../api";
import { Cartao, Erro, Selo, Tabela, fmt, useDados } from "../ui";

interface Log { momento: string; nivel: string; mensagem: string; }

export default function Historico() {
  const { dados, erro } = useDados<Execucao[]>("/api/execucoes?limite=300");
  const [sel, setSel] = useState<Execucao | null>(null);
  const { dados: logs } = useDados<Log[]>(sel ? `/api/execucoes/${sel.id}/logs` : null, [sel?.id]);
  return (
    <>
      <h1>Histórico de execuções</h1>
      <p className="subtitulo">Uma linha por empresa × modelo em cada lote. Falhas são isoladas por empresa.</p>
      <Erro msg={erro} />
      <Cartao titulo="Execuções">
        <Tabela<Execucao> linhas={dados} chave={(x) => x.id} vazio="Nenhuma execução registrada."
          cols={[
            { t: "Início", r: (x) => fmt.data(x.inicio) }, { t: "Fim", r: (x) => fmt.data(x.fim) },
            { t: "Empresa", r: (x) => x.empresa ?? "—" }, { t: "Mod.", r: (x) => x.modelo ?? "—" },
            { t: "Gatilho", r: (x) => x.gatilho }, { t: "Status", r: (x) => <Selo v={x.status} /> },
            { t: "XMLs", r: (x) => fmt.num(x.quantidade), cls: "num" }, { t: "Erros", r: (x) => fmt.num(x.erros), cls: "num" },
            { t: "Modo", r: (x) => <Selo v={x.modo} /> },
            { t: "", r: (x) => <a href="#" onClick={(e) => { e.preventDefault(); setSel(x); }}>detalhes</a> },
          ]} />
      </Cartao>
      {sel && (
        <Cartao titulo={`Execução #${sel.id} — ${sel.empresa ?? ""} ${sel.modelo ?? ""}`}>
          <pre className="logs">{JSON.stringify(sel.detalhes, null, 2)}</pre>
          <h2 style={{ margin: "12px 0 8px" }}>Registros</h2>
          <div className="logs">
            {logs?.length ? logs.map((l, i) => <div key={i} className={l.nivel}>[{fmt.data(l.momento)}] {l.nivel} {l.mensagem}</div>)
              : <span className="mudo">Sem registros.</span>}
          </div>
        </Cartao>
      )}
    </>
  );
}
