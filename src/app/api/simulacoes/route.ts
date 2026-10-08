import { route, readJson } from "@/server/api";
import { createSimulation, listSimulations } from "@/server/services/simulations";

export const GET = route(async ({ req, ctx }) =>
  listSimulations(ctx, { page: Number(req.nextUrl.searchParams.get("pagina") ?? 1), search: req.nextUrl.searchParams.get("q") ?? undefined }),
);
export const POST = route(async ({ req, ctx }) => createSimulation(ctx, await readJson(req)));
