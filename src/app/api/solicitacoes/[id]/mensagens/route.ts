import { route, readJson } from "@/server/api";
import { addMessage } from "@/server/services/requests";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => addMessage(ctx, params.id, await readJson(req)));
