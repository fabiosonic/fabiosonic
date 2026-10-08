import { route } from "@/server/api";
import { connectDemo } from "@/server/services/portfolio";

export const POST = route(async ({ ctx }) => connectDemo(ctx));
