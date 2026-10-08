import { route, readJson } from "@/server/api";
import { createUser } from "@/server/services/users";

export const POST = route(async ({ req, ctx }) => createUser(ctx, await readJson(req)), { roles: ["ADMIN"] });
