import { route } from "@/server/api";
import { deleteCsvPosition } from "@/server/services/portfolio";

export const DELETE = route<{ id: string }>(async ({ ctx, params }) => deleteCsvPosition(ctx, params.id));
