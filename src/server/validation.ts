import type { z } from "zod";
import { fromZod } from "./errors";

/** Valida dados de entrada no servidor, lançando AppError(VALIDATION). */
export function parse<T extends z.ZodType>(schema: T, data: unknown): z.infer<T> {
  const result = schema.safeParse(data);
  if (!result.success) throw fromZod(result.error);
  return result.data;
}
