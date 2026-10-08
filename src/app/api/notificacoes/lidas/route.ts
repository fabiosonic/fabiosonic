import { route } from "@/server/api";
import { markAllRead } from "@/server/services/notifications";

export const POST = route(async ({ ctx }) => ({ updated: await markAllRead(ctx) }));
