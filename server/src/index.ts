// Central Comercial — Moraes & Oliveira Contabilidade
// Servidor HTTP (painel + API + webhooks) e agendador dos agentes 24/7.
import Fastify from 'fastify';
import cookie from '@fastify/cookie';
import estatico from '@fastify/static';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { banco } from './banco.ts';
import { config } from './config.ts';
import { iniciarAgendador, pararAgendador } from './agendador.ts';
import { provedoresElegiveis } from './ia/roteador.ts';
import { log } from './registro.ts';
import { rotasApi } from './rotas/api.ts';
import { rotasAutenticacao } from './rotas/autenticacao.ts';
import { rotasPublicas } from './rotas/publicas.ts';

export async function criarServidor() {
  banco();
  const app = Fastify({ logger: false, trustProxy: true, bodyLimit: 2 * 1024 * 1024 });
  await app.register(cookie);

  // Guarda o corpo bruto para validar a assinatura do webhook da Meta
  app.addContentTypeParser('application/json', { parseAs: 'string' }, (r, corpo, pronto) => {
    (r as any).corpoBruto = corpo;
    try {
      pronto(null, corpo ? JSON.parse(corpo as string) : {});
    } catch {
      pronto(Object.assign(new Error('JSON inválido'), { statusCode: 400 }), undefined);
    }
  });
  app.addContentTypeParser('application/x-www-form-urlencoded', { parseAs: 'string' }, (_r, corpo, pronto) => {
    pronto(null, Object.fromEntries(new URLSearchParams(corpo as string)));
  });

  rotasAutenticacao(app);
  rotasApi(app);
  rotasPublicas(app);
  app.get('/saude', async () => ({ ok: true, hora: new Date().toISOString() }));

  const painel = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'web', 'dist');
  if (existsSync(painel)) {
    await app.register(estatico, { root: painel, wildcard: false });
    app.setNotFoundHandler((r, resposta) => {
      if (r.method === 'GET' && !r.url.startsWith('/api/') && !r.url.startsWith('/webhooks/')) return resposta.sendFile('index.html');
      return resposta.code(404).send({ erro: 'Não encontrado' });
    });
  }
  return app;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  const app = await criarServidor();
  await app.listen({ port: config.porta, host: '0.0.0.0' });
  log('servidor', `painel em ${config.urlPublica} (porta ${config.porta})`);
  if (!config.senhaAdmin) log('servidor', 'ATENÇÃO: SENHA_ADMIN não definida — o painel só aceita acesso local');
  const ias = provedoresElegiveis(false);
  log('roteador-ia', config.ia.simulada ? 'IA simulada (demonstração)' : `${ias.length} provedor(es) de IA configurado(s): ${ias.map((i) => i.p.id).join(', ') || 'nenhum — defina as chaves no .env'}`);
  iniciarAgendador();
  const encerrar = async () => {
    pararAgendador();
    await app.close();
    process.exit(0);
  };
  process.on('SIGINT', encerrar);
  process.on('SIGTERM', encerrar);
}
