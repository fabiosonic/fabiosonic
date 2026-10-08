import { requirePageCtx } from "@/server/session";
import { listAssets } from "@/server/services/market";
import { PageHeader } from "@/components/ui/panel";
import { RequestForm } from "./request-form";

export const metadata = { title: "Novo pedido de análise" };

export default async function NewRequestPage() {
  const ctx = await requirePageCtx();
  const assets = await listAssets(ctx);
  return (
    <>
      <PageHeader title="Novo pedido de análise" description="Descreva sua dúvida. A equipe de análise responderá por aqui e você será notificado." />
      <RequestForm assets={assets.map((a) => a.ticker)} />
    </>
  );
}
