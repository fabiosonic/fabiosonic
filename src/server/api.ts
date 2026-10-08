import "server-only";
import { NextResponse, type NextRequest } from "next/server";
import type { Role } from "@/generated/prisma/enums";
import { AppError, forbidden, type ErrorBody } from "./errors";
import { getActorFromHeaders } from "./auth";
import { clientIp, newRequestId, type Ctx } from "./context";
import { env } from "./env";
import { logger } from "./logger";
import { audit } from "./audit";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const MAX_JSON_BYTES = 256 * 1024;

/**
 * Proteção CSRF: requisições que alteram estado precisam vir da mesma origem
 * (cabeçalho Origin, com Referer como alternativa). Cookies de sessão são SameSite=Lax.
 */
export function assertSameOrigin(req: Request) {
  const allowed = new URL(env().APP_URL).origin;
  const origin = req.headers.get("origin");
  const referer = req.headers.get("referer");
  const source = origin ?? (referer ? new URL(referer).origin : null);
  const self = new URL(req.url).origin;
  if (!source || (source !== allowed && source !== self)) {
    throw new AppError("FORBIDDEN", "Origem da requisição não permitida.");
  }
}

export function errorResponse(error: unknown, requestId: string) {
  if (error instanceof AppError) {
    const body: ErrorBody = {
      error: { code: error.code, message: error.message, fieldErrors: error.fieldErrors, requestId },
    };
    return NextResponse.json(body, { status: error.status, headers: { "x-request-id": requestId } });
  }
  logger.error({ err: error, requestId }, "Erro não tratado");
  const body: ErrorBody = {
    error: { code: "INTERNAL", message: "Erro interno. Tente novamente mais tarde.", requestId },
  };
  return NextResponse.json(body, { status: 500, headers: { "x-request-id": requestId } });
}

export async function readJson(req: Request): Promise<unknown> {
  const len = Number(req.headers.get("content-length") ?? 0);
  if (len > MAX_JSON_BYTES) throw new AppError("BAD_REQUEST", "Requisição muito grande.");
  const text = await req.text();
  if (text.length > MAX_JSON_BYTES) throw new AppError("BAD_REQUEST", "Requisição muito grande.");
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new AppError("BAD_REQUEST", "JSON inválido.");
  }
}

type RouteContext<P> = { params: Promise<P> };

interface HandlerArgs<P> {
  req: NextRequest;
  ctx: Ctx;
  params: P;
}

interface RouteOptions {
  roles?: Role[];
}

/**
 * Envolve um route handler: requestId, CSRF, autenticação, autorização por perfil,
 * respostas de erro padronizadas e auditoria de acessos negados.
 */
export function route<P = Record<string, string>>(
  handler: (args: HandlerArgs<P>) => Promise<unknown>,
  options: RouteOptions = {},
) {
  return async (req: NextRequest, context: RouteContext<P>) => {
    const requestId = req.headers.get("x-request-id") ?? newRequestId();
    const ip = clientIp(req.headers);
    let ctx: Ctx | undefined;
    try {
      if (!SAFE_METHODS.has(req.method)) assertSameOrigin(req);
      const actor = await getActorFromHeaders(req.headers);
      if (!actor) throw new AppError("UNAUTHENTICATED", "Sessão expirada ou inválida. Entre novamente.");
      ctx = { actor, requestId, ip };
      if (options.roles && !options.roles.includes(actor.role)) throw forbidden();
      const params = (await context.params) as P;
      const result = await handler({ req, ctx, params });
      if (result instanceof Response) return result;
      return NextResponse.json(result ?? { ok: true }, { headers: { "x-request-id": requestId } });
    } catch (error) {
      if (ctx && error instanceof AppError && error.code === "FORBIDDEN") {
        await audit(ctx, {
          action: "access.denied",
          resourceType: "route",
          metadata: { method: req.method, path: new URL(req.url).pathname },
        }).catch(() => undefined);
      }
      return errorResponse(error, requestId);
    }
  };
}
