import { route, readJson } from "@/server/api";
import { updateUser } from "@/server/services/users";

export const PATCH = route<{ id: string }>(async ({ req, ctx, params }) => updateUser(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
