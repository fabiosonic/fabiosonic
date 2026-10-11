import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import './estilos.css';
import { api } from './api';
import { Estrutura } from './componentes/Estrutura';
import { Avisos, Carregando } from './componentes/ui';
import { Entrar } from './paginas/Entrar';
import { Painel } from './paginas/Painel';
import { ComVoce } from './paginas/ComVoce';
import { Aprovacao } from './paginas/Aprovacao';
import { Leads } from './paginas/Leads';
import { LeadDetalhe } from './paginas/LeadDetalhe';
import { Conversas } from './paginas/Conversas';
import { Agentes } from './paginas/Agentes';
import { IA } from './paginas/IA';
import { Configuracoes } from './paginas/Configuracoes';

function App() {
  const [sessao, setSessao] = useState<{ autenticado: boolean; requerSenha: boolean } | null>(null);
  useEffect(() => {
    api('/api/sessao').then(setSessao);
    const expirou = () => setSessao((s) => (s ? { ...s, autenticado: false } : s));
    window.addEventListener('sessao-expirada', expirou);
    return () => window.removeEventListener('sessao-expirada', expirou);
  }, []);

  if (!sessao) return <Carregando />;
  if (!sessao.autenticado) return <Entrar requerSenha={sessao.requerSenha} aoEntrar={() => setSessao({ ...sessao, autenticado: true })} />;

  return (
    <Estrutura>
      <Routes>
        <Route path="/" element={<Painel />} />
        <Route path="/com-voce" element={<ComVoce />} />
        <Route path="/aprovacao" element={<Aprovacao />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/leads/:id" element={<LeadDetalhe />} />
        <Route path="/conversas" element={<Conversas />} />
        <Route path="/conversas/:id" element={<Conversas />} />
        <Route path="/agentes" element={<Agentes />} />
        <Route path="/ia" element={<IA />} />
        <Route path="/configuracoes" element={<Configuracoes />} />
        <Route path="*" element={<Painel />} />
      </Routes>
    </Estrutura>
  );
}

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
      <Avisos />
    </BrowserRouter>
  </StrictMode>,
);
