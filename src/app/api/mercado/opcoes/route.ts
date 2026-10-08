import { route } from "@/server/api";
import { listOptions } from "@/server/services/market";

export const GET = route(async ({ req, ctx }) => {
  const sp = req.nextUrl.searchParams;
  return listOptions(ctx, {
    q: sp.get("q") ?? undefined,
    asset: sp.get("ativo") ?? undefined,
    type: sp.get("tipo") ?? undefined,
    expiration: sp.get("vencimento") ?? undefined,
    sort: sp.get("ordem") ?? undefined,
    dir: sp.get("dir") ?? undefined,
    page: Number(sp.get("pagina") ?? 1),
    pageSize: Number(sp.get("tamanho") ?? 25),
  });
});
