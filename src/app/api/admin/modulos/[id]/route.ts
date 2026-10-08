import { route } from "@/server/api";
import { deleteModule } from "@/server/services/courses";

export const DELETE = route<{ id: string }>(async ({ ctx, params }) => deleteModule(ctx, params.id), { roles: ["ADMIN"] });
