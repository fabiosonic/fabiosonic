// Acesso ao painel por senha única (SENHA_ADMIN) com cookie assinado.
// Sem senha definida, o painel só responde a acessos locais (127.0.0.1).
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import { createHmac, timingSafeEqual } from 'node:crypto';
import { config } from '../config.ts';

const DURACAO_MS = 7 * 86_400_000;
const assinar = (valor: string) => createHmac('sha256', config.segredoSessao).update(valor).digest('hex');

export function criarToken() {
  const expira = String(Date.now() + DURACAO_MS);
  return `${expira}.${assinar(expira)}`;
}

export function tokenValido(token: string | undefined) {
  if (!token) return false;
  const [expira, assinatura] = token.split('.');
  if (!expira || !assinatura || Number(expira) < Date.now()) return false;
  const a = Buffer.from(assinatura);
  const b = Buffer.from(assinar(expira));
  return a.length === b.length && timingSafeEqual(a, b);
}

const acessoLocal = (r: FastifyRequest) => ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(r.ip);

export function autenticado(r: FastifyRequest) {
  if (!config.senhaAdmin) return acessoLocal(r);
  return tokenValido(r.cookies?.sessao);
}

export async function exigirSessao(r: FastifyRequest, resposta: FastifyReply) {
  if (!autenticado(r)) return resposta.code(401).send({ erro: 'Faça login para continuar' });
}

const tentativas = new Map<string, { n: number; ate: number }>();

export function rotasAutenticacao(app: FastifyInstance) {
  app.get('/api/sessao', async (r) => ({ autenticado: autenticado(r), requerSenha: Boolean(config.senhaAdmin) }));

  app.post<{ Body: { senha?: string } }>('/api/entrar', async (r, resposta) => {
    const t = tentativas.get(r.ip);
    if (t && t.n >= 5 && t.ate > Date.now()) return resposta.code(429).send({ erro: 'Muitas tentativas. Aguarde alguns minutos.' });
    const senha = r.body?.senha ?? '';
    const ok = config.senhaAdmin && senha.length === config.senhaAdmin.length && timingSafeEqual(Buffer.from(senha), Buffer.from(config.senhaAdmin));
    if (!ok) {
      tentativas.set(r.ip, { n: (t?.n ?? 0) + 1, ate: Date.now() + 10 * 60_000 });
      return resposta.code(401).send({ erro: 'Senha incorreta' });
    }
    tentativas.delete(r.ip);
    resposta.setCookie('sessao', criarToken(), {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      secure: config.urlPublica.startsWith('https'),
      maxAge: DURACAO_MS / 1000,
    });
    return { autenticado: true };
  });

  app.post('/api/sair', async (_r, resposta) => {
    resposta.clearCookie('sessao', { path: '/' });
    return { autenticado: false };
  });
}
