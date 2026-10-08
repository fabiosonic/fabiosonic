import { route, readJson } from "@/server/api";
import { createLive } from "@/server/services/courses";

export const POST = route(async ({ req, ctx }) => createLive(ctx, await readJson(req)), { roles: ["ADMIN"] });
