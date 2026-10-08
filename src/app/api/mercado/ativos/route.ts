import { route } from "@/server/api";
import { listAssets } from "@/server/services/market";

export const GET = route(async ({ req, ctx }) => listAssets(ctx, { q: req.nextUrl.searchParams.get("q") ?? undefined }));
