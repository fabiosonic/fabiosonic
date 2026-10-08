import { route } from "@/server/api";
import { refreshQuotes } from "@/server/services/market";

export const POST = route(async ({ ctx }) => refreshQuotes(ctx), { roles: ["ADMIN"] });
