import { route, readJson } from "@/server/api";
import { deleteLesson, updateLesson } from "@/server/services/courses";

export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateLesson(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
export const DELETE = route<{ id: string }>(async ({ ctx, params }) => deleteLesson(ctx, params.id), { roles: ["ADMIN"] });
