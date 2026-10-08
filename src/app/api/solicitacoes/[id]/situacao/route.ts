import { route, readJson } from "@/server/api";
import { changeRequestStatus } from "@/server/services/requests";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => changeRequestStatus(ctx, params.id, await readJson(req)));
