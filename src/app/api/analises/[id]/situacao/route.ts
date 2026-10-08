import { route, readJson } from "@/server/api";
import { STAFF } from "@/server/authz";
import { changeAnalysisStatus } from "@/server/services/content";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => changeAnalysisStatus(ctx, params.id, await readJson(req)), { roles: STAFF });
