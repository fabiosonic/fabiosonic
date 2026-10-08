import { route, readJson } from "@/server/api";
import { addModule } from "@/server/services/courses";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => addModule(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
