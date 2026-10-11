import './ambiente.ts';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cnpjValido, ehCelular, normalizarTelefone, pareceEmailDeContador, textoNovoDaResposta } from '../src/util/texto.ts';
import { segmentoPorCnae } from '../src/util/segmentos.ts';
import { regrasDeterministicas, verificarFormato } from '../src/agentes/revisor.ts';
import { intencaoPorRegras } from '../src/agentes/atendente.ts';
import { fatosInexistentes } from '../src/agentes/redator.ts';
import { classificarFalha } from '../src/ia/roteador.ts';
import { interpretarWebhookCloud, interpretarWebhookEvolution } from '../src/canais/whatsapp.ts';
import { dentroDaJanela } from '../src/util/tempo.ts';

test('valida CNPJ pelos dígitos verificadores', () => {
  assert.equal(cnpjValido('11.222.333/0001-81'), true);
  assert.equal(cnpjValido('11222333000182'), false);
  assert.equal(cnpjValido('00000000000000'), false);
});

test('normaliza telefones e reconhece celular', () => {
  assert.equal(normalizarTelefone('(11) 98765-4321'), '5511987654321');
  assert.equal(normalizarTelefone('011 3333-4444'), '551133334444');
  assert.equal(normalizarTelefone('123'), null);
  assert.equal(ehCelular('5511987654321'), true);
  assert.equal(ehCelular('551133334444'), false);
});

test('identifica e-mail de contador no cadastro', () => {
  assert.equal(pareceEmailDeContador('fiscal@contabilidadexyz.com.br'), true);
  assert.equal(pareceEmailDeContador('joao@padariadavila.com.br'), false);
});

test('extrai só o texto novo de uma resposta de e-mail', () => {
  const corpo = 'Tenho interesse sim!\n\nEm seg., 6 de out. de 2026 às 10:00, Comercial escreveu:\n> Olá, tudo bem?';
  assert.equal(textoNovoDaResposta(corpo), 'Tenho interesse sim!');
});

test('classifica segmento pela CNAE', () => {
  assert.equal(segmentoPorCnae('4791000'), 'Comércio e e-commerce');
  assert.equal(segmentoPorCnae('8630503'), 'Saúde');
  assert.equal(segmentoPorCnae('6201501'), 'Serviços profissionais e tecnologia');
  assert.equal(segmentoPorCnae('4120400'), 'Construção e imobiliário');
});

test('revisor barra promessas, preço, superlativo e crítica a colegas', () => {
  const casos = [
    'Garantimos redução de 30% nos impostos.',
    'Somos o melhor escritório da cidade.',
    'Nossos honorários começam em R$ 450.',
    'Seu contador atual comete erros que custam caro.',
    'Última chance: vagas limitadas!',
  ];
  for (const c of casos) assert.ok(regrasDeterministicas(c).length > 0, c);
  assert.deepEqual(regrasDeterministicas('Olá, Ana! Vi que a empresa começou há pouco tempo. Podemos conversar 15 minutos?'), []);
  assert.ok(verificarFormato('email', 'Olá [nome]', 'Texto').length > 0);
});

test('intenções críticas são detectadas sem depender da IA', () => {
  assert.equal(intencaoPorRegras('Quanto custa o serviço de vocês?'), 'preco');
  assert.equal(intencaoPorRegras('PARAR'), 'descadastro');
  assert.equal(intencaoPorRegras('Não quero mais receber essas mensagens'), 'descadastro');
  assert.equal(intencaoPorRegras('Prefiro falar com o contador responsável, pode me ligar?'), 'quer_humano');
  assert.equal(intencaoPorRegras('Podemos marcar uma reunião na quinta?'), 'reuniao');
  assert.equal(intencaoPorRegras('Já tenho contador, obrigado'), 'ja_tem_contador');
  assert.equal(intencaoPorRegras('Legal, me conta mais'), null);
});

test('redator não pode citar fato inexistente', () => {
  const fatos = ['[F1] Empresa: X', '[F2] Segmento: Saúde'];
  assert.deepEqual(fatosInexistentes(['F1', '[F2]'], fatos), []);
  assert.deepEqual(fatosInexistentes(['F7'], fatos), ['F7']);
});

test('roteador classifica falhas para decidir a pausa', () => {
  const diaria = classificarFalha(429, '{"error":"Rate limit reached ... tokens per day (TPD)"}', null);
  assert.equal(diaria.motivo, 'cota diária esgotada');
  assert.ok(diaria.ms > 60_000);
  assert.deepEqual(classificarFalha(429, 'rate limit per minute', '20'), { ms: 20_000, motivo: 'limite por minuto' });
  assert.equal(classificarFalha(402, '', null).motivo, 'créditos esgotados');
  assert.match(classificarFalha(401, '', null).motivo, /credencial/);
  assert.match(classificarFalha(503, '', null).motivo, /instabilidade/);
});

test('interpreta webhooks do WhatsApp (oficial e Evolution)', () => {
  const cloud = interpretarWebhookCloud({
    entry: [{ changes: [{ value: { contacts: [{ wa_id: '5511987654321', profile: { name: 'Ana' } }], messages: [{ from: '5511987654321', id: 'wamid.1', timestamp: '1760000000', type: 'text', text: { body: 'Oi!' } }], statuses: [{ id: 'wamid.0', status: 'read' }] } }] }],
  });
  assert.equal(cloud.length, 2);
  assert.deepEqual(cloud[0], { tipo: 'mensagem', de: '5511987654321', nome: 'Ana', texto: 'Oi!', idExterno: 'wamid.1', data: new Date(1760000000 * 1000) });
  assert.deepEqual(cloud[1], { tipo: 'status', idExterno: 'wamid.0', status: 'lida', erro: undefined });
  const evo = interpretarWebhookEvolution({ event: 'messages.upsert', data: { key: { remoteJid: '5511987654321@s.whatsapp.net', fromMe: false, id: 'ABC' }, pushName: 'Ana', message: { conversation: 'Olá' }, messageTimestamp: 1760000000 } });
  assert.equal(evo[0].tipo === 'mensagem' && evo[0].texto, 'Olá');
  assert.deepEqual(interpretarWebhookEvolution({ event: 'messages.upsert', data: { key: { remoteJid: '123@g.us', fromMe: false }, message: { conversation: 'grupo' } } }), []);
});

test('janela de envio respeita dias e horário de Brasília', () => {
  const janela = { dias_semana: [1, 2, 3, 4, 5], inicio: '08:30', fim: '18:00' };
  assert.equal(dentroDaJanela(janela, new Date('2026-10-13T13:00:00Z')), true); // terça 10h BRT
  assert.equal(dentroDaJanela(janela, new Date('2026-10-13T22:00:00Z')), false); // terça 19h BRT
  assert.equal(dentroDaJanela(janela, new Date('2026-10-11T13:00:00Z')), false); // domingo
});
