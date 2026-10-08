import { ZodError } from "zod";

export type ErrorCode =
  | "UNAUTHENTICATED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "VALIDATION"
  | "CONFLICT"
  | "RATE_LIMITED"
  | "BAD_REQUEST"
  | "INTERNAL";

const STATUS: Record<ErrorCode, number> = {
  UNAUTHENTICATED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  VALIDATION: 422,
  CONFLICT: 409,
  RATE_LIMITED: 429,
  BAD_REQUEST: 400,
  INTERNAL: 500,
};

export type FieldErrors = Record<string, string[]>;

/** Erro de aplicação com código padronizado e mensagem segura para o usuário. */
export class AppError extends Error {
  readonly status: number;
  constructor(
    readonly code: ErrorCode,
    message: string,
    readonly fieldErrors?: FieldErrors,
  ) {
    super(message);
    this.name = "AppError";
    this.status = STATUS[code];
  }
}

export const notFound = (what = "Registro") => new AppError("NOT_FOUND", `${what} não encontrado(a).`);
export const forbidden = () => new AppError("FORBIDDEN", "Você não tem permissão para esta ação.");

export function fromZod(error: ZodError): AppError {
  const fieldErrors: FieldErrors = {};
  for (const issue of error.issues) {
    const key = issue.path.join(".") || "_";
    (fieldErrors[key] ??= []).push(issue.message);
  }
  return new AppError("VALIDATION", "Verifique os campos destacados.", fieldErrors);
}

export interface ErrorBody {
  error: { code: ErrorCode; message: string; fieldErrors?: FieldErrors; requestId?: string };
}
