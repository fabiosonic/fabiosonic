import { requirePageCtx } from "@/server/session";
import { PageHeader, Panel } from "@/components/ui/panel";
import { ImportCsv } from "./import-csv";

export const metadata = { title: "Importar posições (CSV)" };

export default async function ImportPage() {
  await requirePageCtx();
  return (
    <>
      <PageHeader title="Importar posições (CSV)" description="Envie um arquivo, confira a prévia e confirme. Linhas idênticas às já importadas são ignoradas; o mesmo arquivo não pode ser importado duas vezes." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ImportCsv />
        </div>
        <Panel title="Formato esperado">
          <p className="text-sm text-slate-600">Cabeçalho obrigatório, separador “;” (recomendado) ou “,”. Limite: 512 KB e 1.000 linhas.</p>
          <pre className="mt-3 overflow-x-auto rounded bg-slate-50 p-3 text-xs">
{`ticker;quantidade;preco_medio;data_referencia;tipo
PETR4;300;32,45;03/10/2026;ACAO
BOVA11;50;120,10;03/10/2026;ETF`}
          </pre>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>Quantidade: inteiro diferente de zero (negativa para posição vendida).</li>
            <li>Preço médio: decimal com vírgula ou ponto, até 4 casas.</li>
            <li>Data: dd/mm/aaaa ou aaaa-mm-dd, não futura.</li>
            <li>Tipo (opcional): ACAO, OPCAO, FII, ETF ou OUTRO.</li>
          </ul>
        </Panel>
      </div>
    </>
  );
}
