import './ambiente-ia-real.ts';
import './ambiente.ts';
import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { reiniciarBanco, todos, um } from '../src/banco.ts';
import { salvarConfiguracoes } from '../src/configuracoes.ts';
import { definirFetchIA, IAIndisponivel, perguntarIA, perguntarJson } from '../src/ia/roteador.ts';

type Resposta = { status: number; corpo: unknown };
let roteiro: Record<string, Resposta[]> = {};
const chamadas: string[] = [];

definirFetchIA((async (url: string | URL | Request) => {
  const u = String(url);
  const id = u.includes('groq') ? 'groq' : u.includes('generativelanguage') ? 'gemini' : u.includes('models.github') ? 'github' : 'outro';
  chamadas.push(id);
  const r = roteiro[id]?.shift() ?? { status: 500, corpo: { error: 'sem roteiro' } };
  return new Response(JSON.stringify(r.corpo), { status: r.status, headers: { 'content-type': 'application/json' } });
}) as typeof fetch);

const ok = (texto: string): Resposta => ({ status: 200, corpo: { choices: [{ message: { content: texto } }], usage: { prompt_tokens: 10, completion_tokens: 5 } } });

beforeEach(() => {
  reiniciarBanco();
  roteiro = {};
  chamadas.length = 0;
  salvarConfiguracoes({ ia: { ordem_provedores: ['groq', 'gemini', 'github'], privacidade_estrita: true, limites_diarios: {} } });
});

test('quando o crédito acaba, troca de provedor sozinho e mantém o provedor pausado', async () => {
  roteiro.groq = [{ status: 429, corpo: { error: { message: 'Rate limit reached for model ... tokens per day (TPD)' } } }];
  roteiro.gemini = [ok('resposta do gemini'), ok('de novo gemini')];

  const r1 = await perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u' });
  assert.equal(r1.provedor, 'gemini');
  assert.deepEqual(chamadas, ['groq', 'gemini']);

  const estado = um<{ pausado_ate: string; motivo: string }>("SELECT pausado_ate, motivo FROM estado_provedores WHERE provedor = 'groq'")!;
  assert.equal(estado.motivo, 'cota diária esgotada');

  // Segunda chamada já não tenta o Groq
  const r2 = await perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u' });
  assert.equal(r2.provedor, 'gemini');
  assert.deepEqual(chamadas, ['groq', 'gemini', 'gemini']);
  assert.equal(todos('SELECT * FROM uso_ia').length, 3);
});

test('privacidade estrita: dados pessoais não vão para provedor que pode treinar', async () => {
  roteiro.groq = [{ status: 503, corpo: {} }];
  roteiro.github = [ok('do github')];
  const r = await perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u', dadosPessoais: true });
  assert.equal(r.provedor, 'github');
  assert.ok(!chamadas.includes('gemini'), 'Gemini (camada gratuita) não deve receber dados pessoais');
});

test('sem nenhum provedor disponível, avisa com o motivo de cada um', async () => {
  roteiro.groq = [{ status: 401, corpo: {} }];
  roteiro.gemini = [{ status: 402, corpo: {} }];
  roteiro.github = [{ status: 500, corpo: {} }];
  await assert.rejects(perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u' }), (e: unknown) => {
    assert.ok(e instanceof IAIndisponivel);
    assert.equal(e.tentativas.length, 3);
    return true;
  });
});

test('respeita o limite diário configurado e pula para o próximo', async () => {
  salvarConfiguracoes({ ia: { ordem_provedores: ['groq', 'gemini', 'github'], privacidade_estrita: false, limites_diarios: { groq: 1 } } });
  roteiro.groq = [ok('1')];
  roteiro.gemini = [ok('2')];
  assert.equal((await perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u' })).provedor, 'groq');
  assert.equal((await perguntarIA({ tarefa: 't', sistema: 's', usuario: 'u' })).provedor, 'gemini');
});

test('JSON quebrado é pedido de novo; JSON cercado por ``` é aceito', async () => {
  roteiro.groq = [ok('isso não é json'), ok('```json\n{"a": 1}\n```')];
  const r = await perguntarJson<{ a: number }>({ tarefa: 't', sistema: 's', usuario: 'u' });
  assert.equal(r.a, 1);
});
