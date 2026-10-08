import { route, readJson } from "@/server/api";
import { createRequest } from "@/server/services/requests";

export const POST = route(async ({ req, ctx }) => createRequest(ctx, await readJson(req)));
