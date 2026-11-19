import { Cartao, Erro, Selo, Tabela, fmt, useDados } from "../ui";

interface Cert {
  id: number; empresa: string | null; titular: string; cnpj: string | null; validade: string; valido_de: string;
  status: string; ativo: boolean; emissor: string | null; autorizado_por: string; autorizado_em: string; impressao_digital: string;
}

export default function Certificados() {
  const { dados, erro } = useDados<Cert[]>("/api/certificados");
  const dias = (v: string) => Math.floor((new Date(v).getTime() - Date.now()) / 86400000);
  return (
    <>
      <h1>Certificados</h1>
      <p className="subtitulo">A1 guardados no cofre (DPAPI no Windows). Senhas nunca são exibidas nem registradas.</p>
      <Erro msg={erro} />
      <Cartao titulo="Certificados digitais">
        <Tabela<Cert> linhas={dados} chave={(c) => c.id} vazio="Nenhum certificado cadastrado. Cadastre pela página Empresas."
          cols={[
            { t: "Empresa", r: (c) => c.empresa ?? "Escritório" },
            { t: "Titular", r: (c) => c.titular },
            { t: "CNPJ", r: (c) => (c.cnpj ? fmt.cnpj(c.cnpj) : "—") },
            { t: "Validade", r: (c) => fmt.dia(c.validade) },
            { t: "Dias", r: (c) => fmt.num(dias(c.validade)), cls: "num" },
            { t: "Status", r: (c) => <Selo v={c.ativo ? c.status : "SUBSTITUIDO"} /> },
            { t: "Emissor", r: (c) => c.emissor ?? "—" },
            { t: "Autorização", r: (c) => `${c.autorizado_por} em ${fmt.dia(c.autorizado_em)}` },
            { t: "Impressão digital", r: (c) => <span className="mono">{c.impressao_digital}…</span> },
          ]} />
      </Cartao>
    </>
  );
}
