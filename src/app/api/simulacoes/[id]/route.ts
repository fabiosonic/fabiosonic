import { route, readJson } from "@/server/api";
import { deleteSimulation, getSimulation, updateSimulation } from "@/server/services/simulations";

export const GET = route<{ id: string }>(async ({ ctx, params }) => getSimulation(ctx, params.id));
export const PUT = route<{ id: string }>(async ({ req, ctx, params }) => updateSimulation(ctx, params.id, await readJson(req)));
export const DELETE = route<{ id: string }>(async ({ ctx, params }) => deleteSimulation(ctx, params.id));
