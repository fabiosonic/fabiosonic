import { route, readJson } from "@/server/api";
import { addLesson } from "@/server/services/courses";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => addLesson(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
