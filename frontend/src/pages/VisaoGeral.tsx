import { Link } from "react-router-dom";
import { Execucao, Resumo } from "../api";
import { Cartao, Erro, Kpi, Selo, Tabela, fmt, useDados } from "../ui";

export default function VisaoGeral() {
  const { dados: r, erro } = useDados<Resumo>("/api/resumo");
  const { dados: ex } = useDados<Execucao[]>("/api/execucoes?limite=12");
  const erros = r ? Object.entries(r.erros_por_fonte_7d) : [];
  return (
    <>
      <h1>Visão geral</h1>
      <p className="subtitulo">Situação da captura de XML de saída (NF-e 55 e NFC-e 65) da carteira.</p>
      <Erro msg={erro} />
      {r && (
        <>
          <div className="grade-kpi">
            <Kpi rotulo="Empresas cadastradas" valor={fmt.num(r.empresas_cadastradas)} detalhe={`${r.empresas_ativas} ativas`} />
            <Kpi rotulo="Processadas (último lote)" valor={fmt.num(r.empresas_processadas_ultimo_lote)} />
            <Kpi rotulo="XMLs recuperados" valor={fmt.num(r.xmls_recuperados)} tom="ok" detalhe="XML integral com protocolo" />
            <Kpi rotulo="NF-e recuperadas" valor={fmt.num(r.nfe_recuperadas)} />
            <Kpi rotulo="NFC-e recuperadas" valor={fmt.num(r.nfce_recuperadas)} />
            <Kpi rotulo="XMLs pendentes" valor={fmt.num(r.xmls_pendentes)} tom={r.xmls_pendentes ? "alerta" : ""} detalhe="chave conhecida, XML ainda não obtido" />
            <Kpi rotulo="Cancelados" valor={fmt.num(r.documentos_cancelados)} />
            <Kpi rotulo="Lacunas de numeração" valor={fmt.num(r.lacunas)} tom={r.lacunas ? "alerta" : ""} detalhe="não significa XML perdido" />
            <Kpi rotulo="Certificados vencendo" valor={fmt.num(r.certificados_vencendo)} tom={r.certificados_vencendo ? "erro" : ""} detalhe="≤ 30 dias ou vencidos" />
            <Kpi rotulo="Execuções com erro (7d)" valor={fmt.num(r.execucoes_com_erro_7d)} tom={r.execucoes_com_erro_7d ? "erro" : ""} />
            <Kpi rotulo="Última sincronização" valor={<span style={{ fontSize: 15 }}>{fmt.data(r.ultima_sincronizacao)}</span>}
              detalhe={r.captura_em_andamento ? "captura em andamento" : undefined} />
            <Kpi rotulo="Próxima execução" valor={<span style={{ fontSize: 15 }}>{fmt.data(r.proximas_execucoes[0])}</span>}
              detalhe={r.proximas_execucoes.length ? `${r.proximas_execucoes.length} agendadas` : "agendador parado"} />
          </div>
          <div className="duas">
            <Cartao titulo="Erros por fonte (7 dias)">
              {erros.length ? (
                <Tabela cols={[{ t: "Fonte", r: (l: [string, number]) => l[0] }, { t: "Erros", r: (l) => fmt.num(l[1]), cls: "num" }]}
                  linhas={erros} chave={(l) => l[0]} />
              ) : <p className="mudo">Nenhum erro de comunicação registrado.</p>}
            </Cartao>
            <Cartao titulo="Execuções recentes" acoes={<Link to="/historico">ver histórico</Link>}>
              <Tabela<Execucao> linhas={ex} chave={(l) => l.id} vazio="Nenhuma execução ainda."
                cols={[
                  { t: "Empresa", r: (l) => l.empresa ?? "—" },
                  { t: "Mod.", r: (l) => l.modelo ?? "—" },
                  { t: "Início", r: (l) => fmt.data(l.inicio) },
                  { t: "Status", r: (l) => <Selo v={l.status} /> },
                  { t: "XMLs", r: (l) => fmt.num(l.quantidade), cls: "num" },
                ]} />
            </Cartao>
          </div>
        </>
      )}
    </>
  );
}
