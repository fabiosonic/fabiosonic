import { route, readJson } from "@/server/api";
import { syncNow } from "@/server/services/portfolio";

export const POST = route(async ({ req, ctx }) => {
  const body = (await readJson(req)) as { simulateFailure?: unknown };
  return syncNow(ctx, { simulateFailure: body.simulateFailure === true });
});
