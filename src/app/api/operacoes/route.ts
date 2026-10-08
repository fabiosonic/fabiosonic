import { route, readJson } from "@/server/api";
import { STAFF } from "@/server/authz";
import { createStrategy } from "@/server/services/content";

export const POST = route(async ({ req, ctx }) => createStrategy(ctx, await readJson(req)), { roles: STAFF });
