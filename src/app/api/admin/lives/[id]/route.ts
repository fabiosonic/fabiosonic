import { route, readJson } from "@/server/api";
import { updateLive } from "@/server/services/courses";

export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateLive(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
