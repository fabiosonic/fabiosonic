import { FormEvent, useState } from "react";
import { api } from "../api";
import { Cartao, Erro, Ok, Tabela, fmt, useDados } from "../ui";

interface Pasta { id: number; caminho: string; empresa_id: number | null; ativo: boolean; ultima_varredura: string | null; }

export default function Configuracoes() {
  const { dados: cfg, erro } = useDados<Record<string, unknown>>("/api/configuracoes");
  const { dados: pastas, recarregar } = useDados<Pasta[]>("/api/pastas");
  const [msg, setMsg] = useState<string | null>(null);
  const [falha, setFalha] = useState<string | null>(null);
  const [token, setToken] = useState("");

  async function novaPasta(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const f = new FormData(ev.currentTarget);
    setFalha(null);
    try {
      await api.post("/api/pastas", { caminho: f.get("caminho"), empresa_id: f.get("empresa") ? Number(f.get("empresa")) : null });
      setMsg("Pasta cadastrada."); await recarregar();
    } catch (x) { setFalha((x as Error).message); }
  }
  function salvarToken() {
    try { localStorage.setItem("moxml_token", token); } catch { /* armazenamento indisponível */ }
    document.cookie = `moxml_token=${encodeURIComponent(token)}; path=/; SameSite=Strict`;
    setMsg("Token salvo neste navegador.");
  }
  return (
    <>
      <h1>Configurações</h1>
      <p className="subtitulo">Parâmetros vêm de variáveis MOXML_* ou de moxml.env na pasta de dados (alterar e reiniciar o serviço).</p>
      <Erro msg={erro || falha} /><Ok msg={msg} />
      <Cartao titulo="Parâmetros em uso">
        <Tabela<[string, unknown]> linhas={cfg ? Object.entries(cfg) : null} chave={(l) => l[0]}
          cols={[{ t: "Parâmetro", r: (l) => <span className="mono">{l[0]}</span> }, { t: "Valor", r: (l) => String(l[1] ?? "—") }]} />
      </Cartao>
      <Cartao titulo="Pastas monitoradas do emissor">
        <form className="form" onSubmit={novaPasta}>
          <label>Caminho (neste computador ou rede)<input name="caminho" required placeholder="\\servidor\PDV\XML" /></label>
          <label>Empresa (id, opcional)<input name="empresa" type="number" /></label>
          <button>Adicionar pasta</button>
        </form>
        <Tabela<Pasta> linhas={pastas} chave={(p) => p.id} vazio="Nenhuma pasta monitorada."
          cols={[{ t: "Caminho", r: (p) => <span className="mono">{p.caminho}</span> }, { t: "Empresa", r: (p) => p.empresa_id ?? "pelo CNPJ do XML" },
                 { t: "Última varredura", r: (p) => fmt.data(p.ultima_varredura) }]} />
      </Cartao>
      <Cartao titulo="Acesso ao painel">
        <p className="mudo">Se MOXML_API_TOKEN estiver definido no servidor, informe-o aqui.</p>
        <div className="acoes"><input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="token" />
          <button onClick={salvarToken}>Salvar</button></div>
      </Cartao>
    </>
  );
}
