import { route, readJson } from "@/server/api";
import { STAFF } from "@/server/authz";
import { getStrategy, updateStrategy } from "@/server/services/content";

export const GET = route<{ id: string }>(async ({ ctx, params }) => getStrategy(ctx, params.id));
export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateStrategy(ctx, params.id, await readJson(req)), { roles: STAFF });
