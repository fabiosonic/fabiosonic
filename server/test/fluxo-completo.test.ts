// Fluxo ponta a ponta com IA simulada e serviços externos falsos:
// lead → enriquecimento (CNPJ + QSA + site) → qualificação → redação + revisão →
// aprovação → envio → resposta "quanto custa?" → chama o responsável.
import './ambiente.ts';
import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { reiniciarBanco, todos, um } from '../src/banco.ts';
import { salvarConfiguracoes } from '../src/configuracoes.ts';
import { definirFetchCnpj } from '../src/fontes/cnpj.ts';
import { definirFetchSite } from '../src/fontes/site.ts';
import { definirTransporte } from '../src/canais/email.ts';
import { criarLead } from '../src/leads.ts';
import { enriquecerLead } from '../src/agentes/enriquecedor.ts';
import { qualificarLead } from '../src/agentes/qualificador.ts';
import { avancarCadencia } from '../src/agentes/acompanhamento.ts';
import { dispararPendentes } from '../src/agentes/disparador.ts';
import { processarEntrada, registrarEntrada } from '../src/agentes/atendente.ts';
import { higienizar } from '../src/agentes/operacoes.ts';

const CNPJ = '11222333000181';
const enviados: any[] = [];

before(() => {
  reiniciarBanco();
  salvarConfiguracoes({
    escritorio: {
      nome: 'Moraes & Oliveira Contabilidade',
      razao_social: 'Moraes e Oliveira Serviços Contábeis Ltda',
      cnpj: '00.000.000/0001-00',
      crc_organizacao: 'SP-000000/O-0',
      responsavel_tecnico: { nome: 'Responsável Teste', categoria: 'Contador', crc: 'SP-000000/O-1' },
      telefone: '',
      site: '',
      cidade: 'Campinas/SP',
      cargo_assinatura: 'Equipe comercial',
    },
    servicos: ['Contabilidade para empresas do Simples Nacional'],
    horario_envio: { dias_semana: [0, 1, 2, 3, 4, 5, 6], inicio: '00:00', fim: '24:00' },
    limites: { emails_dia: 100, emails_hora: 100, whatsapp_dia: 100, intervalo_min_segundos: 0 },
  });
  const abertura = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10);
  definirFetchCnpj((async () =>
    new Response(
      JSON.stringify({
        cnpj: CNPJ, razao_social: 'PADARIA DA VILA LTDA', nome_fantasia: 'PADARIA DA VILA', cnae_fiscal: 1091102,
        cnae_fiscal_descricao: 'Fabricação de produtos de padaria e confeitaria', cnaes_secundarios: [{ codigo: 0, descricao: '' }],
        natureza_juridica: 'Sociedade Empresária Limitada', porte: 'MICRO EMPRESA', capital_social: 50000, data_inicio_atividade: abertura,
        descricao_situacao_cadastral: 'ATIVA', opcao_pelo_simples: true, opcao_pelo_mei: false, municipio: 'CAMPINAS', uf: 'SP',
        email: 'contato@padariadavila.com.br', ddd_telefone_1: '19999998888',
        qsa: [{ nome_socio: 'MARIA DA SILVA', qualificacao_socio: 'Sócio-Administrador', faixa_etaria: 'Entre 31 a 40 anos', data_entrada_sociedade: abertura, cnpj_cpf_do_socio: '***123456**' }],
      }),
      { status: 200 },
    )) as typeof fetch);
  definirFetchSite((async (url: string | URL | Request) => {
    if (String(url).endsWith('robots.txt')) return new Response('User-agent: *\nAllow: /', { status: 200 });
    return new Response('<html><title>Padaria da Vila</title><meta name="description" content="Pães artesanais e encomendas para eventos em Campinas"><body>Peça pelo nosso e-commerce. Fale: vendas@padariadavila.com.br</body></html>', {
      status: 200,
      headers: { 'content-type': 'text/html' },
    });
  }) as typeof fetch);
  definirTransporte({ sendMail: async (m: any) => (enviados.push(m), { messageId: `<msg-${enviados.length}@teste>` }) } as any);
});

test('fluxo completo até chamar o responsável', async () => {
  const { leadId } = criarLead({ cnpj: CNPJ, origem: 'cadastro_manual', origemDetalhe: 'Indicação de cliente' });

  await enriquecerLead(leadId);
  let lead = um<any>('SELECT * FROM leads WHERE id = ?', leadId)!;
  assert.equal(lead.etapa, 'enriquecida');
  const socios = todos<any>('SELECT * FROM socios');
  assert.equal(socios[0].nome, 'MARIA DA SILVA');
  const contatos = todos<any>('SELECT tipo, valor, origem FROM contatos ORDER BY id');
  assert.ok(contatos.some((c) => c.valor === 'vendas@padariadavila.com.br' && c.origem.startsWith('Site')), 'e-mail corporativo do site');
  assert.ok(contatos.some((c) => c.tipo === 'whatsapp' && c.valor === '5519999998888'));
  assert.equal(um<any>('SELECT segmento FROM empresas')!.segmento, 'Indústria');

  await qualificarLead(leadId);
  lead = um<any>('SELECT * FROM leads WHERE id = ?', leadId)!;
  assert.equal(lead.etapa, 'qualificada');
  assert.ok(lead.pontuacao >= 55, `pontuação ${lead.pontuacao}`);

  await avancarCadencia(leadId);
  const rascunho = um<any>("SELECT * FROM mensagens WHERE direcao = 'saida'")!;
  assert.equal(rascunho.status, 'aguardando_aprovacao', 'modo padrão é aprovação humana');
  assert.equal(rascunho.canal, 'email');
  assert.match(rascunho.corpo, /Maria/);
  assert.equal(JSON.parse(rascunho.revisao).aprovado, true);

  // Sem aprovação, nada sai
  assert.equal(await dispararPendentes(), 0);
  // Aprovado por você → sai com assinatura, CRC e descadastro
  const { executar } = await import('../src/banco.ts');
  executar("UPDATE mensagens SET status = 'aprovada' WHERE id = ?", rascunho.id);
  assert.equal(await dispararPendentes(), 1);
  assert.equal(enviados.length, 1);
  assert.match(enviados[0].text, /CRC SP-000000\/O-0/);
  assert.match(enviados[0].text, /descadastro/);
  assert.ok(enviados[0].headers['List-Unsubscribe']);
  assert.equal(um<any>('SELECT etapa FROM leads WHERE id = ?', leadId)!.etapa, 'em_contato');

  // Lead responde perguntando preço → a IA não responde o mérito e chama você
  const idEntrada = registrarEntrada({
    canal: 'email', de: 'vendas@padariadavila.com.br', idExterno: '<resp-1@lead>', assunto: 'Re: Primeiros meses',
    texto: 'Oi! Quanto custa a contabilidade de vocês?\n\nEm seg., Comercial escreveu:\n> texto antigo', emRespostaA: '<msg-1@teste>',
  })!;
  await processarEntrada(idEntrada);
  assert.equal(um<any>('SELECT etapa FROM leads WHERE id = ?', leadId)!.etapa, 'com_voce');
  const atendimento = um<any>('SELECT * FROM atendimentos_humanos')!;
  assert.equal(atendimento.motivo, 'preco');
  const resposta = um<any>("SELECT * FROM mensagens WHERE direcao = 'saida' AND agente = 'atendente'")!;
  assert.match(resposta.corpo, /Fábio/);
  assert.doesNotMatch(resposta.corpo, /R\$/);
  assert.equal(resposta.em_resposta_a, '<resp-1@lead>');
});

test('pedido de descadastro bloqueia todos os contatos e encerra o lead', async () => {
  const { leadId } = criarLead({ cnpj: '11444777000161', whatsapp: '11987654321', email: 'socio@lojaexemplo.com.br', origem: 'importacao', origemDetalhe: 'teste' });
  const id = registrarEntrada({ canal: 'whatsapp', de: '5511987654321', texto: 'PARAR', idExterno: 'wamid.parar' })!;
  await processarEntrada(id);
  assert.equal(um<any>('SELECT etapa, motivo_perda FROM leads WHERE id = ?', leadId)!.motivo_perda, 'descadastro');
  assert.ok(um("SELECT 1 FROM bloqueios WHERE valor = 'socio@lojaexemplo.com.br'"));
  assert.ok(um("SELECT 1 FROM bloqueios WHERE valor = '5511987654321'"));
});

test('WhatsApp de número desconhecido vira lead receptivo e o CNPJ informado é aproveitado', async () => {
  const id = registrarEntrada({ canal: 'whatsapp', de: '5519911112222', nome: 'João', texto: 'Olá, quero abrir uma empresa', idExterno: 'wamid.novo' })!;
  const lead = um<any>('SELECT l.*, e.cnpj FROM mensagens m JOIN leads l ON l.id = m.lead_id JOIN empresas e ON e.id = l.empresa_id WHERE m.id = ?', id)!;
  assert.equal(lead.etapa, 'respondeu');
  assert.match(lead.cnpj, /^pendente-/);
  assert.equal(um<any>("SELECT optin FROM contatos WHERE valor = '5519911112222'")!.optin, 1);
});

test('contato repetido em 3 empresas é marcado como do contador cadastral', () => {
  for (const c of ['11222333000262', '11222333000343', '11222333000424']) {
    criarLead({ cnpj: c, email: 'fiscal@escritorioqualquer.com.br', origem: 'importacao' });
  }
  higienizar();
  const n = um<{ n: number }>("SELECT COUNT(*) n FROM contatos WHERE valor = 'fiscal@escritorioqualquer.com.br' AND provavel_contador = 1")!.n;
  const total = um<{ n: number }>("SELECT COUNT(*) n FROM contatos WHERE valor = 'fiscal@escritorioqualquer.com.br'")!.n;
  assert.equal(total, 3);
  assert.equal(n, total);
});
