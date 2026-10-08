import { route } from "@/server/api";
import { getRequest } from "@/server/services/requests";

export const GET = route<{ id: string }>(async ({ ctx, params }) => getRequest(ctx, params.id));
