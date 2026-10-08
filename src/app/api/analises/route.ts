import { route, readJson } from "@/server/api";
import { STAFF } from "@/server/authz";
import { createAnalysis } from "@/server/services/content";

export const POST = route(async ({ req, ctx }) => createAnalysis(ctx, await readJson(req)), { roles: STAFF });
