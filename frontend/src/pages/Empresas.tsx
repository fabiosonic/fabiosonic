import { FormEvent, useState } from "react";
import { api, Empresa } from "../api";
import { Cartao, Erro, Ok, Selo, Tabela, fmt, useDados } from "../ui";

interface Serie {
  id: number; modelo: string; serie: number; ambiente: number; ultimo_numero_identificado: number | null;
  ultimo_numero_recuperado: number | null; chave_semente: string | null; data_semente: string | null; ativo: boolean;
}

function Detalhe({ e, aoAlterar }: { e: Empresa; aoAlterar: () => void }) {
  const { dados: series, recarregar } = useDados<Serie[]>(`/api/empresas/${e.id}/series`);
  const [msg, setMsg] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [chaves, setChaves] = useState("");

  async function enviar(fn: () => Promise<unknown>, ok: string) {
    setErro(null); setMsg(null);
    try { await fn(); setMsg(ok); await recarregar(); aoAlterar(); } catch (x) { setErro((x as Error).message); }
  }
  async function semente(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    await enviar(() => api.upload(`/api/empresas/${e.id}/semente`, fd), "XML semente importado e série inicializada.");
  }
  async function certificado(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const fd = new FormData(ev.currentTarget);
    fd.set("confirmo_autorizacao", (ev.currentTarget.elements.namedItem("confirmo") as HTMLInputElement).checked ? "true" : "false");
    await enviar(() => api.upload(`/api/empresas/${e.id}/certificado`, fd), "Certificado validado e guardado no cofre.");
    ev.currentTarget?.reset();
  }
  return (
    <Cartao titulo={`${e.razao_social} — ${fmt.cnpj(e.cnpj)}`}>
      <Erro msg={erro} /><Ok msg={msg} />
      <h2>Séries controladas</h2>
      <Tabela<Serie> linhas={series} chave={(s) => s.id} vazio="Nenhuma série: importe um XML semente por modelo/série."
        cols={[
          { t: "Modelo", r: (s) => s.modelo }, { t: "Série", r: (s) => s.serie },
          { t: "Últ. identificado", r: (s) => fmt.num(s.ultimo_numero_identificado), cls: "num" },
          { t: "Últ. recuperado", r: (s) => fmt.num(s.ultimo_numero_recuperado), cls: "num" },
          { t: "Semente", r: (s) => (s.data_semente ? fmt.dia(s.data_semente) : "—") },
        ]} />
      <div className="duas" style={{ marginTop: 16 }}>
        <form onSubmit={semente} className="form">
          <label>XML semente (NF-e ou NFC-e recente, um por série)
            <input type="file" name="arquivo" accept=".xml" required /></label>
          <button>Importar semente</button>
        </form>
        <form onSubmit={certificado} className="form">
          <label>Certificado A1 (.pfx/.p12)<input type="file" name="arquivo" accept=".pfx,.p12" required /></label>
          <label>Senha<input type="password" name="senha" required autoComplete="off" /></label>
          <label>Autorizado por<input name="autorizado_por" required placeholder="nome e cargo do responsável" /></label>
          <label>Termo/contrato de autorização<input name="termo" required placeholder="ex.: Contrato 15/2026, cláusula 4" /></label>
          <label className="check"><input type="checkbox" name="confirmo" /> Confirmo a autorização expressa do titular</label>
          <button>Enviar certificado</button>
        </form>
      </div>
      <h2 style={{ marginTop: 16 }}>Chaves conhecidas</h2>
      <p className="mudo">Uma por linha. Só são aceitas chaves válidas deste CNPJ (nunca se gera chave por tentativa).</p>
      <textarea value={chaves} onChange={(x) => setChaves(x.target.value)} />
      <button style={{ marginTop: 8 }} onClick={() =>
        enviar(async () => {
          const r = await api.post<{ aceitas: number; rejeitadas: { chave: string; motivo: string }[] }>(
            `/api/empresas/${e.id}/chaves`, { chaves: chaves.split(/\s+/).filter(Boolean) });
          if (r.rejeitadas.length) throw new Error(`${r.aceitas} aceitas; rejeitadas: ${r.rejeitadas.map((x) => `${x.chave} (${x.motivo})`).join("; ")}`);
          setChaves("");
        }, "Chaves cadastradas.")}>Cadastrar chaves</button>
      <div className="acoes" style={{ marginTop: 16 }}>
        <button className="secundario" onClick={() => enviar(() => api.patch(`/api/empresas/${e.id}`, { ativo: !e.ativo }), e.ativo ? "Empresa desativada." : "Empresa ativada.")}>
          {e.ativo ? "Desativar empresa" : "Ativar empresa"}</button>
        <button className="secundario" onClick={() => enviar(() => api.post("/api/capturas/executar", { empresas: [e.id] }), "Captura iniciada para esta empresa.")}>
          Capturar agora</button>
      </div>
    </Cartao>
  );
}

export default function Empresas() {
  const [busca, setBusca] = useState("");
  const { dados, erro, recarregar } = useDados<Empresa[]>(`/api/empresas${busca ? `?busca=${encodeURIComponent(busca)}` : ""}`, [busca]);
  const [sel, setSel] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [erroForm, setErroForm] = useState<string | null>(null);

  async function criar(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    setErroForm(null);
    try {
      await api.post("/api/empresas", {
        razao_social: f.get("razao"), cnpj: f.get("cnpj"), uf: f.get("uf"), regime: f.get("regime") || null,
        nome_pasta: f.get("pasta") || null, captura_nfe: f.get("nfe") === "on", captura_nfce: f.get("nfce") === "on",
      });
      setMsg("Empresa cadastrada."); ev.currentTarget.reset(); await recarregar();
    } catch (x) { setErroForm((x as Error).message); }
  }
  const atual = dados?.find((e) => e.id === sel);
  return (
    <>
      <h1>Empresas</h1>
      <p className="subtitulo">Carteira de clientes, certificados e séries controladas.</p>
      <Erro msg={erro} />
      <Cartao titulo="Nova empresa">
        <Erro msg={erroForm} /><Ok msg={msg} />
        <form className="form" onSubmit={criar}>
          <label>Razão social<input name="razao" required /></label>
          <label>CNPJ<input name="cnpj" required placeholder="00.000.000/0000-00" /></label>
          <label>UF<select name="uf" defaultValue="RJ"><option>RJ</option><option>SP</option></select></label>
          <label>Regime<select name="regime" defaultValue=""><option value="">—</option><option>Simples Nacional</option><option>Lucro Presumido</option><option>Lucro Real</option><option>MEI</option></select></label>
          <label>Pasta no Drive (opcional)<input name="pasta" placeholder="nome exato em CLIENTES ATIVOS" /></label>
          <label className="check"><input type="checkbox" name="nfe" defaultChecked /> NF-e 55</label>
          <label className="check"><input type="checkbox" name="nfce" defaultChecked /> NFC-e 65</label>
          <button>Cadastrar</button>
        </form>
      </Cartao>
      <Cartao titulo={`Carteira (${dados?.length ?? 0})`} acoes={<input placeholder="buscar razão social ou CNPJ" value={busca} onChange={(e) => setBusca(e.target.value)} />}>
        <Tabela<Empresa> linhas={dados} chave={(e) => e.id}
          cols={[
            { t: "Razão social", r: (e) => <a href="#" onClick={(x) => { x.preventDefault(); setSel(e.id); }}>{e.razao_social}</a> },
            { t: "CNPJ", r: (e) => <span className="mono">{fmt.cnpj(e.cnpj)}</span> },
            { t: "UF", r: (e) => e.uf },
            { t: "Modelos", r: (e) => [e.captura_nfe && "55", e.captura_nfce && "65"].filter(Boolean).join(" · ") },
            { t: "Certificado", r: (e) => e.certificado ? <><Selo v={e.certificado.status} /> <span className="mudo">{fmt.dia(e.certificado.validade)}</span></> : <Selo v="PENDENTE" /> },
            { t: "XMLs", r: (e) => fmt.num(e.documentos), cls: "num" },
            { t: "Pendentes", r: (e) => fmt.num(e.pendentes), cls: "num" },
            { t: "Última execução", r: (e) => e.ultima_execucao ? <Selo v={e.ultima_execucao.status} /> : "—" },
            { t: "Ativa", r: (e) => (e.ativo ? "Sim" : "Não") },
          ]} />
      </Cartao>
      {atual && <Detalhe e={atual} aoAlterar={recarregar} />}
    </>
  );
}
