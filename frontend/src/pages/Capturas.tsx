import { useEffect, useRef, useState } from "react";
import { api, Empresa, LogItem, Resumo } from "../api";
import { Cartao, Erro, Ok, fmt, useDados } from "../ui";

export default function Capturas() {
  const { dados: empresas } = useDados<Empresa[]>("/api/empresas");
  const { dados: resumo, recarregar } = useDados<Resumo>("/api/resumo");
  const [sel, setSel] = useState<number[]>([]);
  const [modelos, setModelos] = useState<string[]>(["55", "65"]);
  const [hist, setHist] = useState({ empresa: "", modelo: "65", serie: "1", numero: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let seq = 0;
    let vivo = true;
    const ciclo = async () => {
      try {
        const novos = await api.get<LogItem[]>(`/api/logs/recentes?desde=${seq}`);
        if (novos.length && vivo) {
          seq = novos[novos.length - 1].seq;
          setLogs((l) => [...l, ...novos].slice(-500));
        }
      } catch { /* servidor indisponível momentaneamente */ }
    };
    void ciclo();
    const t = setInterval(ciclo, 2000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  useEffect(() => fim.current?.scrollIntoView({ block: "nearest" }), [logs]);

  async function executar(historico?: Record<string, number>) {
    setErro(null); setMsg(null);
    try {
      await api.post("/api/capturas/executar", { empresas: sel.length ? sel : null, modelos, historico: historico ?? null });
      setMsg("Captura iniciada. Acompanhe os registros abaixo.");
      setTimeout(recarregar, 1500);
    } catch (x) { setErro((x as Error).message); }
  }
  const alternar = (id: number) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <>
      <h1>Capturas</h1>
      <p className="subtitulo">Execução manual, recuperação histórica e acompanhamento em tempo real.</p>
      <Erro msg={erro} /><Ok msg={msg} />
      <div className="duas">
        <Cartao titulo="Executar agora" acoes={resumo?.captura_em_andamento ? <span className="selo info">em andamento</span> : null}>
          <div className="filtros">
            {["55", "65"].map((m) => (
              <label key={m} className="check"><input type="checkbox" checked={modelos.includes(m)}
                onChange={() => setModelos((x) => (x.includes(m) ? x.filter((y) => y !== m) : [...x, m]))} /> {m === "55" ? "NF-e 55" : "NFC-e 65"}</label>
            ))}
          </div>
          <p className="mudo">Empresas (nenhuma marcada = todas as ativas):</p>
          <div style={{ maxHeight: 220, overflowY: "auto", marginBottom: 12 }}>
            {empresas?.filter((e) => e.ativo).map((e) => (
              <label key={e.id} className="check" style={{ display: "flex", gap: 6 }}>
                <input type="checkbox" checked={sel.includes(e.id)} onChange={() => alternar(e.id)} /> {e.razao_social}
              </label>
            ))}
          </div>
          <button disabled={!modelos.length || resumo?.captura_em_andamento} onClick={() => executar()}>Iniciar captura</button>
          <p className="mudo">Próximas automáticas: {resumo?.proximas_execucoes.slice(0, 3).map(fmt.data).join(" · ") || "—"}</p>
        </Cartao>
        <Cartao titulo="Recuperação histórica">
          <p className="mudo">Retoma a descoberta de uma série a partir de um número anterior. A SEFAZ pode recusar chaves com mais de 6 meses (cStat 526).</p>
          <div className="form">
            <label>Empresa<select value={hist.empresa} onChange={(e) => setHist({ ...hist, empresa: e.target.value })}>
              <option value="">—</option>{empresas?.map((e) => <option key={e.id} value={e.id}>{e.razao_social}</option>)}</select></label>
            <label>Modelo<select value={hist.modelo} onChange={(e) => setHist({ ...hist, modelo: e.target.value })}><option>55</option><option>65</option></select></label>
            <label>Série<input value={hist.serie} onChange={(e) => setHist({ ...hist, serie: e.target.value })} /></label>
            <label>A partir do número<input value={hist.numero} onChange={(e) => setHist({ ...hist, numero: e.target.value })} /></label>
            <button disabled={!hist.empresa || !hist.numero} onClick={() => {
              setSel([Number(hist.empresa)]); setModelos([hist.modelo]);
              void executar({ [`${hist.empresa}|${hist.modelo}|${hist.serie}`]: Number(hist.numero) });
            }}>Recuperar histórico</button>
          </div>
        </Cartao>
      </div>
      <Cartao titulo="Registros em tempo real">
        <div className="logs">
          {logs.length ? logs.map((l) => (
            <div key={l.seq} className={l.nivel}>[{new Date(l.momento).toLocaleTimeString("pt-BR")}] {l.nivel} {l.mensagem}</div>
          )) : <span className="mudo">Sem registros desde a abertura do painel.</span>}
          <div ref={fim} />
        </div>
      </Cartao>
    </>
  );
}
