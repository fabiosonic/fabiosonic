import { route, readJson } from "@/server/api";
import { createCourse } from "@/server/services/courses";

export const POST = route(async ({ req, ctx }) => createCourse(ctx, await readJson(req)), { roles: ["ADMIN"] });
