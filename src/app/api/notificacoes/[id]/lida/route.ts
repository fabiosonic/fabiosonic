import { route } from "@/server/api";
import { markRead } from "@/server/services/notifications";

export const POST = route<{ id: string }>(async ({ ctx, params }) => markRead(ctx, params.id));
