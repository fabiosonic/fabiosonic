"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Table, Td, Th } from "@/components/ui/table";

type RowStatus = "valida" | "erro" | "duplicada_no_arquivo" | "nova" | "atualizacao" | "identica";
interface Preview {
  fileName: string;
  alreadyImported: boolean;
  fatal?: string;
  rows: { line: number; status: RowStatus; errors: string[]; raw: Record<string, string> }[];
  summary: { total: number; novas: number; atualizacoes: number; identicas: number; erros: number };
}

const STATUS: Record<RowStatus, { label: string; tone: "success" | "info" | "neutral" | "danger" | "warning" }> = {
  nova: { label: "Nova", tone: "success" },
  atualizacao: { label: "Atualização", tone: "info" },
  identica: { label: "Idêntica (ignorada)", tone: "neutral" },
  erro: { label: "Erro", tone: "danger" },
  duplicada_no_arquivo: { label: "Duplicada no arquivo", tone: "warning" },
  valida: { label: "Válida", tone: "success" },
};

const MAX = 512 * 1024;

export function ImportCsv() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "confirm" | null>(null);

  function pick(f: File | null) {
    setPreview(null);
    setSuccess(null);
    setError(null);
    if (f && !/\.csv$/i.test(f.name)) return setError("Selecione um arquivo .csv.");
    if (f && f.size > MAX) return setError("Arquivo acima do limite de 512 KB.");
    setFile(f);
  }

  async function send(kind: "previa" | "confirmar") {
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    setBusy(kind === "previa" ? "preview" : "confirm");
    setError(null);
    const res = await api<Preview & { imported: number; skipped: number }>("POST", `/api/carteira/importacao/${kind}`, form);
    setBusy(null);
    if (!res.ok) return setError(res.error.message);
    if (kind === "previa") setPreview(res.data);
    else {
      setSuccess(`Importação concluída: ${res.data.imported} linha(s) aplicada(s), ${res.data.skipped} ignorada(s).`);
      setPreview(null);
      setFile(null);
      if (input.current) input.current.value = "";
      router.refresh();
    }
  }

  const canConfirm = preview && !preview.fatal && !preview.alreadyImported && preview.summary.erros === 0 && preview.summary.novas + preview.summary.atualizacoes > 0;

  return (
    <Panel title="Arquivo">
      <div className="space-y-4">
        {success && (
          <Alert tone="success">
            {success}{" "}
            <a href="/carteira" className="underline">
              Ver carteira
            </a>
          </Alert>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 flex-1">
            <label htmlFor="csv" className="block text-sm font-medium text-slate-700">
              Arquivo CSV
            </label>
            <input
              ref={input}
              id="csv"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => pick(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border file:border-slate-300 file:bg-white file:px-3 file:py-1.5 file:text-sm"
            />
          </div>
          <Button onClick={() => send("previa")} disabled={!file || busy !== null}>
            {busy === "preview" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FileUp className="size-4" aria-hidden="true" />}
            Pré-visualizar
          </Button>
        </div>

        {preview && (
          <div className="space-y-3" aria-live="polite">
            {preview.fatal && <Alert tone="error">{preview.fatal}</Alert>}
            {preview.alreadyImported && <Alert tone="warning">Este arquivo já foi importado anteriormente. Para evitar duplicidade, a importação está bloqueada.</Alert>}
            {!preview.fatal && (
              <>
                <p className="text-sm text-slate-700">
                  {preview.summary.total} linha(s): <strong>{preview.summary.novas}</strong> nova(s), <strong>{preview.summary.atualizacoes}</strong> atualização(ões),{" "}
                  <strong>{preview.summary.identicas}</strong> idêntica(s) e <strong>{preview.summary.erros}</strong> com erro.
                </p>
                <Table caption="Prévia da importação">
                  <thead>
                    <tr>
                      <Th>Linha</Th>
                      <Th>Ticker</Th>
                      <Th>Quantidade</Th>
                      <Th>Preço médio</Th>
                      <Th>Data</Th>
                      <Th>Situação</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((r) => (
                      <tr key={r.line}>
                        <Td className="tabular">{r.line}</Td>
                        <Td>{r.raw.ticker}</Td>
                        <Td className="tabular">{r.raw.quantidade}</Td>
                        <Td className="tabular">{r.raw.preco_medio}</Td>
                        <Td>{r.raw.data_referencia}</Td>
                        <Td>
                          <Badge tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Badge>
                          {r.errors.length > 0 && <span className="block text-xs text-loss-700">{r.errors.join(" ")}</span>}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                {preview.summary.erros > 0 && <Alert tone="error">Corrija as linhas com erro no arquivo e envie novamente.</Alert>}
                <Button onClick={() => send("confirmar")} disabled={!canConfirm || busy !== null}>
                  {busy === "confirm" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                  Confirmar importação
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
