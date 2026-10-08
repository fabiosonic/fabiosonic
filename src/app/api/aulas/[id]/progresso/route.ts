import { route, readJson } from "@/server/api";
import { setLessonProgress } from "@/server/services/courses";

export const POST = route<{ id: string }>(async ({ req, ctx, params }) => {
  const body = (await readJson(req)) as { completed?: unknown };
  return setLessonProgress(ctx, params.id, body.completed !== false);
});
