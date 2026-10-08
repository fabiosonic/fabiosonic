import { NextResponse, type NextRequest } from "next/server";
import { getSessionCookie } from "better-auth/cookies";

const PUBLIC_PATHS = ["/login", "/recuperar-acesso", "/redefinir-senha", "/dev/emails", "/api/auth", "/api/health"];

/**
 * Atribui um identificador de requisição (x-request-id) e faz o redirecionamento
 * otimista para /login quando não há cookie de sessão. A verificação definitiva
 * de sessão e permissões ocorre no servidor, em cada página e rota de API.
 */
export function proxy(request: NextRequest) {
  const requestId = request.headers.get("x-request-id") ?? crypto.randomUUID();
  const headers = new Headers(request.headers);
  headers.set("x-request-id", requestId);

  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isPublic && !pathname.startsWith("/api/") && !getSessionCookie(request)) {
    const url = new URL("/login", request.url);
    return NextResponse.redirect(url, { headers: { "x-request-id": requestId } });
  }

  const response = NextResponse.next({ request: { headers } });
  response.headers.set("x-request-id", requestId);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg).*)"],
};
