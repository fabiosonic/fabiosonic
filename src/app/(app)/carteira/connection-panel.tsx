"use client";

import { useState } from "react";
import { ShieldAlert } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import { ConnectionBadge } from "@/components/ui/badge";
import { ActionButton } from "@/components/ui/action-button";
import { Alert } from "@/components/ui/alert";
import { formatDate, formatDateTime } from "@/lib/format";

interface PortfolioInfo {
  connectionStatus: "DISCONNECTED" | "CONNECTED" | "SYNCING" | "ERROR";
  connectionProvider: string | null;
  connectedAt: string | null;
  lastSyncAt: string | null;
  lastReferenceDate: string | null;
  lastError: string | null;
}

export function ConnectionPanel({ portfolio }: { portfolio: PortfolioInfo }) {
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [result, setResult] = useState<{ status: string; message?: string; positions?: number } | null>(null);
  const status = portfolio.connectionStatus;

  return (
    <Panel title="Conexão B3" actions={<ConnectionBadge status={status} />}>
      <Alert tone="warning" title="Modo demonstrativo">
        Esta conexão é simulada: não acessa a B3, não solicita senha e gera posições fictícias. A integração oficial depende de contrato e autorização junto à B3.
      </Alert>

      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500">Conectada desde</dt>
          <dd>{formatDateTime(portfolio.connectedAt)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500">Última sincronização</dt>
          <dd>{formatDateTime(portfolio.lastSyncAt)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-slate-500">Data-base (D+1)</dt>
          <dd>{formatDate(portfolio.lastReferenceDate)}</dd>
        </div>
      </dl>

      {status === "ERROR" && portfolio.lastError && (
        <Alert tone="error" title="Falha na última sincronização" className="mt-3">
          {portfolio.lastError}
        </Alert>
      )}
      {result && (
        <Alert tone={result.status === "SUCCESS" ? "success" : "error"} className="mt-3">
          {result.status === "SUCCESS" ? `Sincronização concluída: ${result.positions} posição(ões).` : result.message}
        </Alert>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {status === "DISCONNECTED" ? (
          <ActionButton
            url="/api/carteira/conectar"
            variant="primary"
            size="md"
            confirm={{
              title: "Conectar em modo demonstrativo?",
              description:
                "Nenhuma credencial será solicitada e nenhum dado real da B3 será acessado. As posições geradas são fictícias e servem apenas para demonstrar o fluxo.",
            }}
            confirmLabel="Conectar (demonstração)"
          >
            Conectar (demonstração)
          </ActionButton>
        ) : (
          <>
            <ActionButton
              url="/api/carteira/sincronizar"
              body={{ simulateFailure }}
              variant="primary"
              size="md"
              onDone={(d) => setResult(d as { status: string; message?: string; positions?: number })}
            >
              Sincronizar agora
            </ActionButton>
            <ActionButton
              url="/api/carteira/desconectar"
              variant="danger"
              size="md"
              confirm={{ title: "Desconectar a carteira?", description: "As posições obtidas pela conexão demonstrativa serão removidas. Posições importadas por CSV permanecem." }}
              confirmLabel="Desconectar"
            >
              Desconectar
            </ActionButton>
          </>
        )}
      </div>

      {status !== "DISCONNECTED" && (
        <label className="mt-3 flex items-center gap-2 text-xs text-slate-600">
          <input type="checkbox" checked={simulateFailure} onChange={(e) => setSimulateFailure(e.target.checked)} className="size-4" />
          <ShieldAlert className="size-3.5" aria-hidden="true" />
          Simular falha do provedor (para testar o estado de erro)
        </label>
      )}
    </Panel>
  );
}
