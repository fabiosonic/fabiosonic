import { route, readJson } from "@/server/api";
import { updateCourse } from "@/server/services/courses";

export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateCourse(ctx, params.id, await readJson(req)), { roles: ["ADMIN"] });
