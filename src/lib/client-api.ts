"use client";

export interface ApiError {
  code: string;
  message: string;
  fieldErrors?: Record<string, string[]>;
  requestId?: string;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/** Chamada à API interna com cookies de sessão; erros chegam no formato padronizado. */
export async function api<T = unknown>(method: string, url: string, body?: unknown): Promise<ApiResult<T>> {
  try {
    const isForm = body instanceof FormData;
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: body === undefined || isForm ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
    const text = await res.text();
    const json = text ? JSON.parse(text) : {};
    if (!res.ok) {
      if (res.status === 401) {
        return { ok: false, error: { code: "UNAUTHENTICATED", message: "Sua sessão expirou. Entre novamente." } };
      }
      return { ok: false, error: json.error ?? { code: "INTERNAL", message: "Erro inesperado." } };
    }
    return { ok: true, data: json as T };
  } catch {
    return { ok: false, error: { code: "NETWORK", message: "Falha de conexão. Verifique sua rede e tente novamente." } };
  }
}
