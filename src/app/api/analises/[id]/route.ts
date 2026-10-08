import { route, readJson } from "@/server/api";
import { STAFF } from "@/server/authz";
import { getAnalysis, updateAnalysis } from "@/server/services/content";

export const GET = route<{ id: string }>(async ({ ctx, params }) => getAnalysis(ctx, params.id));
export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateAnalysis(ctx, params.id, await readJson(req)), { roles: STAFF });
