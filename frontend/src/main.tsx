import { Component, ReactNode, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { Resumo } from "./api";
import "./estilo.css";
import Capturas from "./pages/Capturas";
import Certificados from "./pages/Certificados";
import Configuracoes from "./pages/Configuracoes";
import Documentos from "./pages/Documentos";
import Empresas from "./pages/Empresas";
import Eventos from "./pages/Eventos";
import Historico from "./pages/Historico";
import Integracoes from "./pages/Integracoes";
import Lacunas from "./pages/Lacunas";
import VisaoGeral from "./pages/VisaoGeral";
import { useDados } from "./ui";

/** Para-quedas: se uma página falhar ao renderizar, mostra o erro em vez de tela branca. */
class Limite extends Component<{ children: ReactNode }, { erro: Error | null }> {
  state = { erro: null as Error | null };
  static getDerivedStateFromError(erro: Error) {
    return { erro };
  }
  render() {
    if (this.state.erro) {
      return (
        <div style={{ padding: 24 }}>
          <div className="aviso erro" style={{ display: "block" }}>
            <strong>Esta página encontrou um erro.</strong>
            <p style={{ margin: "8px 0" }}>{this.state.erro.message}</p>
            <p className="mudo" style={{ fontSize: 12 }}>
              Se você acabou de atualizar o sistema, atualize a página forçando o recarregamento
              (Ctrl+Shift+R). Se persistir, clique abaixo.
            </p>
            <button onClick={() => { this.setState({ erro: null }); location.reload(); }}>Recarregar painel</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const MENU: [string, string][] = [
  ["/", "Visão geral"], ["/empresas", "Empresas"], ["/certificados", "Certificados"], ["/capturas", "Capturas"],
  ["/documentos", "Documentos"], ["/lacunas", "Lacunas"], ["/eventos", "Eventos"], ["/historico", "Histórico"],
  ["/integracoes", "Integrações"], ["/configuracoes", "Configurações"],
];

function Shell() {
  const { dados } = useDados<Resumo>("/api/resumo");
  const modo = dados?.modo;
  return (
    <div className="app">
      <aside>
        <div className="marca">
          <span className="logo">M&amp;O</span>
          <div>
            <strong>XML Captador</strong>
            <small>NF-e 55 · NFC-e 65 · saída</small>
          </div>
        </div>
        <nav>
          {MENU.map(([to, t]) => (
            <NavLink key={to} to={to} end={to === "/"}>{t}</NavLink>
          ))}
        </nav>
        <footer>Moraes e Oliveira Contabilidade Ltda</footer>
      </aside>
      <main>
        {modo && (
          <div className={`faixa-modo ${modo === "REAL" ? "real" : "simulado"}`}>
            {modo === "REAL"
              ? <>Produção — <strong>notas reais</strong> obtidas das fontes oficiais com o certificado A1 de cada cliente.</>
              : <>Atenção: servidor em modo <strong>{modo}</strong> (uso exclusivo de testes automatizados). Não utilize.</>}
          </div>
        )}
        <Limite>
        <Routes>
          <Route path="/" element={<VisaoGeral />} />
          <Route path="/empresas" element={<Empresas />} />
          <Route path="/certificados" element={<Certificados />} />
          <Route path="/capturas" element={<Capturas />} />
          <Route path="/documentos" element={<Documentos />} />
          <Route path="/lacunas" element={<Lacunas />} />
          <Route path="/eventos" element={<Eventos />} />
          <Route path="/historico" element={<Historico />} />
          <Route path="/integracoes" element={<Integracoes />} />
          <Route path="/configuracoes" element={<Configuracoes />} />
        </Routes>
        </Limite>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </StrictMode>,
);
