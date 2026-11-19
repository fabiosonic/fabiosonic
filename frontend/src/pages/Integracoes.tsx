import { useState } from "react";
import { api } from "../api";
import { Cartao, Erro, Ok, Selo, Tabela, fmt, useDados } from "../ui";

interface Conector { nome: string; descricao: string; oficial: boolean; comercial: boolean; capacidades: string[]; ativo: boolean; limites: Record<string, unknown>; }
interface Linha { uf: string; modelo: string; conector: string; status: string; motivo: string; evidencia: string; oficial: boolean; comercial: boolean; }
interface Integ { conectores: Conector[]; matriz: Linha[]; estatisticas_fontes: { servico: string; cstat: string | null; quantidade: number }[]; google_drive: { ativo: boolean; status: Record<string, number> }; dominio: { modo: string }; }

export default function Integracoes() {
  const { dados, erro, recarregar } = useDados<Integ>("/api/integracoes");
  const [msg, setMsg] = useState<string | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const hoje = new Date();
  const [comp, setComp] = useState({ ano: hoje.getFullYear(), mes: hoje.getMonth() || 12 });

  async function acao(fn: () => Promise<unknown>, ok: (r: unknown) => string) {
    setMsg(null); setFalha(null);
    try { const r = await fn(); setMsg(ok(r)); await recarregar(); } catch (e) { setFalha((e as Error).message); }
  }
  return (
    <>
      <h1>Integrações e fontes</h1>
      <p className="subtitulo">Matriz de cobertura UF × modelo × fonte, conectores, Google Drive e Domínio.</p>
      <Erro msg={erro || falha} /><Ok msg={msg} />
      <Cartao titulo="Matriz de cobertura">
        <p className="mudo">NÃO COMPROVADO = documentado oficialmente, mas ainda sem teste real com certificado autorizado. Só é operacional após o teste de aceitação.</p>
        <Tabela<Linha> linhas={dados?.matriz ?? null} chave={(l) => `${l.uf}${l.modelo}${l.conector}`}
          cols={[
            { t: "UF", r: (l) => l.uf }, { t: "Modelo", r: (l) => l.modelo }, { t: "Fonte", r: (l) => l.conector },
            { t: "Tipo", r: (l) => (l.comercial ? "comercial (opcional)" : l.oficial ? "oficial" : "cliente") },
            { t: "Status", r: (l) => <Selo v={l.status} /> },
            { t: "Motivo / evidência", r: (l) => <span className="mudo">{l.motivo}{l.evidencia ? ` — ${l.evidencia}` : ""}</span> },
          ]} />
      </Cartao>
      <Cartao titulo="Conectores">
        <Tabela<Conector> linhas={dados?.conectores ?? null} chave={(c) => c.nome}
          cols={[
            { t: "Conector", r: (c) => <strong>{c.nome}</strong> }, { t: "Descrição", r: (c) => c.descricao },
            { t: "Capacidades", r: (c) => c.capacidades.join(", ") },
            { t: "Ativo", r: (c) => c.comercial
              ? <button className="secundario" onClick={() => acao(() => api.put(`/api/conectores/${c.nome}`, { ativo: !c.ativo }), () => "Conector atualizado.")}>
                  {c.ativo ? "Desligar" : "Ligar"}</button>
              : (c.ativo ? "Sim" : "Não") },
          ]} />
      </Cartao>
      <div className="duas">
        <Cartao titulo="Google Drive" acoes={<button disabled={!dados?.google_drive.ativo}
          onClick={() => acao(() => api.post("/api/drive/sincronizar"), (r) => `Drive: ${JSON.stringify(r)}`)}>Sincronizar agora</button>}>
          <p>Status: <Selo v={dados?.google_drive.ativo ? "DISPONIVEL" : "NAO_CONFIGURADO"} /></p>
          <p className="mudo">Arquivos só contam como sincronizados quando a API devolve id e MD5 iguais ao local.</p>
          <Tabela<[string, number]> linhas={dados ? Object.entries(dados.google_drive.status) : null} chave={(l) => l[0]} vazio="Nenhum envio ainda."
            cols={[{ t: "Status", r: (l) => <Selo v={l[0]} /> }, { t: "Arquivos", r: (l) => fmt.num(l[1]), cls: "num" }]} />
        </Cartao>
        <Cartao titulo="Domínio (Escrita Fiscal)">
          <p className="mudo">{dados?.dominio.modo}. O pacote contém os XMLs originais (sem alteração), relatórios e manifesto SHA-256. A importação é feita pelo operador no Domínio.</p>
          <div className="form">
            <label>Ano<input type="number" value={comp.ano} onChange={(e) => setComp({ ...comp, ano: Number(e.target.value) })} /></label>
            <label>Mês<input type="number" min={1} max={12} value={comp.mes} onChange={(e) => setComp({ ...comp, mes: Number(e.target.value) })} /></label>
            <button onClick={() => acao(() => api.post<{ pasta: string; documentos: number }[]>("/api/dominio/exportar", comp),
              (r) => `Pacotes gerados: ${(r as { pasta: string; documentos: number }[]).map((x) => `${x.pasta} (${x.documentos} docs)`).join("; ")}`)}>
              Gerar pacotes do mês</button>
          </div>
        </Cartao>
      </div>
      <Cartao titulo="Respostas das fontes (auditoria)">
        <Tabela linhas={dados?.estatisticas_fontes ?? null} chave={(l) => `${l.servico}${l.cstat}`} vazio="Nenhuma chamada registrada."
          cols={[{ t: "Serviço", r: (l) => l.servico }, { t: "cStat", r: (l) => l.cstat ?? "erro de comunicação" },
                 { t: "Quantidade", r: (l) => fmt.num(l.quantidade), cls: "num" }]} />
      </Cartao>
    </>
  );
}
