import { route } from "@/server/api";
import { disconnect } from "@/server/services/portfolio";

export const POST = route(async ({ ctx }) => disconnect(ctx));
