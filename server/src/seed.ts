// Dados de DEMONSTRAÇÃO, 100% fictícios, para visualizar o painel antes de
// conectar as fontes reais. Todos os contatos usam o domínio reservado
// ".invalid" e números inexistentes, então nada pode ser enviado a pessoas reais.
// Uso: npm run seed  (apaga e recria o banco de demonstração)
import { rmSync } from 'node:fs';
import { config } from './config.ts';
import { banco, executar, transacao } from './banco.ts';
import { salvarConfiguracoes } from './configuracoes.ts';
import { segmentoPorCnae } from './util/segmentos.ts';

for (const sufixo of ['', '-wal', '-shm']) rmSync(config.caminhoBanco + sufixo, { force: true });
banco();

let semente = 42;
const aleatorio = () => ((semente = (semente * 16807) % 2147483647) - 1) / 2147483646;
const escolher = <T>(lista: T[]) => lista[Math.floor(aleatorio() * lista.length)];

function cnpjFicticio(i: number) {
  const base = String(90000000 + i * 7919).slice(0, 8) + '0001';
  const dv = (b: string, pesos: number[]) => {
    const r = b.split('').reduce((s, d, k) => s + Number(d) * pesos[k], 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  const d1 = dv(base, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const d2 = dv(base + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  return `${base}${d1}${d2}`;
}

const sql = (d: Date) => d.toISOString().slice(0, 19).replace('T', ' ');
const diasAtras = (n: number, horas = 0) => sql(new Date(Date.now() - n * 86_400_000 - horas * 3600_000));

const EMPRESAS = [
  ['Ateliê Ponto Firme', '4781400', 'Comércio varejista de artigos do vestuário'],
  ['Nuvem Clara Software', '6201501', 'Desenvolvimento de programas de computador sob encomenda'],
  ['Clínica Bem Viver', '8630503', 'Atividade médica ambulatorial restrita a consultas'],
  ['Forno da Vila Padaria', '1091102', 'Fabricação de produtos de padaria e confeitaria'],
  ['Construtora Horizonte Sul', '4120400', 'Construção de edifícios'],
  ['LojaFácil Online', '4791000', 'Comércio varejista por internet'],
  ['Rota Certa Transportes', '4930202', 'Transporte rodoviário de carga intermunicipal'],
  ['Studio Pixel Design', '7410202', 'Design de interiores'],
  ['Odonto Sorriso Pleno', '8630504', 'Atividade odontológica'],
  ['Metalúrgica Aço Forte', '2512800', 'Fabricação de esquadrias de metal'],
  ['Café Grão Nobre', '5611203', 'Lanchonetes, casas de chá, de sucos e similares'],
  ['Escola Pequenos Passos', '8512100', 'Educação infantil — pré-escola'],
  ['AgroVerde Insumos', '4683400', 'Comércio atacadista de defensivos agrícolas'],
  ['Pet & Cia Banho e Tosa', '9609208', 'Higiene e embelezamento de animais domésticos'],
  ['Consultoria Prisma', '7020400', 'Atividades de consultoria em gestão empresarial'],
  ['Auto Peças Avenida', '4530703', 'Comércio a varejo de peças para veículos'],
  ['Imobiliária Casa Nova', '6821801', 'Corretagem na compra e venda de imóveis'],
  ['Laboratório Vida Lab', '8640202', 'Laboratórios clínicos'],
  ['Moda Viva Atacado', '4642701', 'Comércio atacadista de artigos do vestuário'],
  ['DataPonto Tecnologia', '6204000', 'Consultoria em tecnologia da informação'],
  ['Mercadinho Bom Preço', '4712100', 'Minimercados e mercearias'],
  ['Fisio Movimento', '8650004', 'Atividades de fisioterapia'],
  ['Gráfica Impressão Já', '1813001', 'Impressão de material para uso publicitário'],
  ['Hotel Recanto Serra', '5510801', 'Hotéis'],
  ['Engenharia Traço Fino', '7112000', 'Serviços de engenharia'],
  ['Doce Encanto Confeitaria', '1091101', 'Fabricação de produtos de panificação'],
  ['Academia Corpo Ativo', '9313100', 'Atividades de condicionamento físico'],
  ['Logística Expressa Norte', '5211701', 'Armazéns gerais'],
  ['Ótica Visão Clara', '4774100', 'Comércio varejista de artigos de óptica'],
  ['Marketing Lume Digital', '7319002', 'Promoção de vendas'],
  ['Farmácia Saúde Já', '4771701', 'Comércio varejista de produtos farmacêuticos'],
  ['Móveis Arte Madeira', '3101200', 'Fabricação de móveis com predominância de madeira'],
  ['Instituto Educar Mais', '8599604', 'Treinamento em desenvolvimento profissional'],
  ['Barbearia Navalha de Ouro', '9602501', 'Cabeleireiros, manicure e pedicure'],
  ['Eletro Center Comércio', '4753900', 'Comércio de eletrodomésticos e equipamentos de áudio e vídeo'],
  ['Clínica Vet Amigo Fiel', '7500100', 'Atividades veterinárias'],
  ['Solar Brasil Energia', '4321500', 'Instalação e manutenção elétrica'],
  ['Restaurante Sabor Caseiro', '5611201', 'Restaurantes e similares'],
  ['Contábil Apoio Treinamentos', '8599603', 'Treinamento em informática'],
  ['Vidraçaria Cristal', '4744099', 'Comércio varejista de materiais de construção'],
  ['Tech Repair Assistência', '9511800', 'Reparação de computadores'],
  ['Papelaria Ponto Escolar', '4761003', 'Comércio varejista de artigos de papelaria'],
];
const NOMES = ['ANA PAULA DEMO', 'CARLOS EDUARDO DEMO', 'MARIANA DEMO', 'RAFAEL DEMO', 'JULIANA DEMO', 'PEDRO HENRIQUE DEMO', 'FERNANDA DEMO', 'LUCAS DEMO', 'BEATRIZ DEMO', 'THIAGO DEMO', 'CAMILA DEMO', 'GUSTAVO DEMO'];
const CIDADES = [['CAMPINAS', 'SP'], ['SAO PAULO', 'SP'], ['SOROCABA', 'SP'], ['JUNDIAI', 'SP'], ['RIBEIRAO PRETO', 'SP'], ['SANTOS', 'SP']];
const PORTES = ['MICRO EMPRESA', 'MICRO EMPRESA', 'EMPRESA DE PEQUENO PORTE', 'DEMAIS'];

// Distribuição do funil de demonstração
const ETAPAS_DEMO = [
  ...Array(5).fill('mapeada'), ...Array(4).fill('enriquecida'), ...Array(6).fill('qualificada'), ...Array(9).fill('em_contato'),
  ...Array(4).fill('respondeu'), ...Array(4).fill('com_voce'), 'proposta', 'proposta', 'negociacao', 'cliente', ...Array(3).fill('pausada'),
  'descartada', 'perdida',
];

transacao(() => {
  EMPRESAS.forEach(([fantasia, cnae, descricao], i) => {
    const etapa = ETAPAS_DEMO[i] ?? 'mapeada';
    const [cidade, uf] = escolher(CIDADES);
    const abertura = diasAtras(Math.floor(aleatorio() * 110) + 5).slice(0, 10);
    const enriquecida = etapa !== 'mapeada';
    const criado = diasAtras(Math.floor(aleatorio() * 25) + 1);
    const emp = executar(
      `INSERT INTO empresas (cnpj, razao_social, nome_fantasia, cnae_principal, cnae_descricao, natureza_juridica, porte, capital_social, data_abertura,
         situacao, optante_simples, optante_mei, municipio, uf, segmento, site_resumo, origem, origem_detalhe, enriquecida_em, criado_em)
       VALUES (?, ?, ?, ?, ?, 'Sociedade Empresária Limitada', ?, ?, ?, 'ATIVA', ?, 0, ?, ?, ?, ?, 'demonstracao', 'Dados fictícios de demonstração', ?, ?)`,
      cnpjFicticio(i),
      `${fantasia.toUpperCase()} LTDA [DEMO]`,
      fantasia,
      cnae,
      descricao,
      escolher(PORTES),
      Math.round(aleatorio() * 20) * 10000 + 5000,
      abertura,
      aleatorio() > 0.3,
      cidade,
      uf,
      enriquecida ? segmentoPorCnae(cnae) : null,
      enriquecida && aleatorio() > 0.4 ? JSON.stringify({ resumo: `${fantasia} atua com ${descricao.toLowerCase()} na região de ${cidade.toLowerCase()}.`, sinais: aleatorio() > 0.5 ? ['Atende pelo site e redes sociais'] : [] }) : null,
      enriquecida ? criado : null,
      criado,
    );
    const pontuacao = ['mapeada', 'enriquecida'].includes(etapa) ? null : etapa === 'descartada' ? 38 : 55 + Math.floor(aleatorio() * 40);
    const lead = executar(
      `INSERT INTO leads (empresa_id, etapa, pontuacao, pontuacao_motivos, temperatura, necessidades, resumo_ia, passo_cadencia, proxima_acao, proxima_acao_em, motivo_perda, criado_em, atualizado_em)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      emp.id,
      etapa,
      pontuacao,
      JSON.stringify(pontuacao ? ['+20 segmento prioritário', '+15 empresa recém-aberta', '+10 canal de contato utilizável'] : []),
      pontuacao ? escolher(['fria', 'morna', 'quente']) : null,
      JSON.stringify(pontuacao ? ['Como está organizada hoje a emissão de notas?', 'Já existe definição de pró-labore?', 'Quando pretendem estruturar a contabilidade?'] : []),
      pontuacao ? 'Empresa recém-aberta estruturando a rotina contábil e fiscal. (demonstração)' : null,
      etapa === 'em_contato' ? 1 + Math.floor(aleatorio() * 3) : 0,
      etapa === 'em_contato' ? 'acompanhamento' : etapa === 'qualificada' ? 'primeiro_contato' : null,
      etapa === 'em_contato' || etapa === 'qualificada' ? diasAtras(-Math.floor(aleatorio() * 4)) : null,
      etapa === 'perdida' ? 'ja_tem_contador' : null,
      criado,
      diasAtras(Math.floor(aleatorio() * 3), Math.floor(aleatorio() * 20)),
    );
    if (!enriquecida) return;
    const nSocios = 1 + Math.floor(aleatorio() * 2);
    for (let s = 0; s < nSocios; s++) {
      executar(
        `INSERT OR IGNORE INTO socios (empresa_id, nome, qualificacao, faixa_etaria, data_entrada, outras_empresas, origem) VALUES (?, ?, ?, ?, ?, ?, 'demonstracao')`,
        emp.id,
        escolher(NOMES),
        s === 0 ? 'Sócio-Administrador' : 'Sócio',
        escolher(['21 a 30 anos', '31 a 40 anos', '41 a 50 anos']),
        abertura,
        JSON.stringify(aleatorio() > 0.7 ? [{ cnpj_basico: '00000000', razao_social: 'OUTRA EMPRESA DEMO LTDA', porte: 'MICRO EMPRESA' }] : []),
      );
    }
    const email = `contato${i}@empresa-demo.invalid`;
    executar("INSERT INTO contatos (empresa_id, tipo, valor, origem) VALUES (?, 'email', ?, 'demonstração')", emp.id, email);
    executar("INSERT INTO contatos (empresa_id, tipo, valor, origem, optin) VALUES (?, 'whatsapp', ?, 'demonstração', ?)", emp.id, `55119000000${String(i).padStart(2, '0')}`, aleatorio() > 0.5);

    const contatoId = Number((banco().prepare('SELECT id FROM contatos WHERE empresa_id = ? AND tipo = ?').get(emp.id, 'email') as { id: number }).id);
    const enviar = (dias: number, canal: string, corpo: string, assunto: string | null, status = 'enviada') =>
      executar(
        `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, assunto, corpo, status, agente, revisao, enviada_em, criado_em)
         VALUES (?, ?, ?, 'saida', ?, ?, ?, 'redator', ?, ?, ?)`,
        lead.id, contatoId, canal, assunto, corpo, status,
        JSON.stringify({ aprovado: true, problemas: [], etapas: ['regras', 'ia:demonstracao'], tipo: 'primeiro_contato', fatos_usados: ['F1', 'F3'] }),
        status === 'aguardando_aprovacao' ? null : diasAtras(dias, 2), diasAtras(dias, 3),
      );
    const receber = (dias: number, corpo: string, intencao: string) =>
      executar(
        `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, corpo, status, intencao, enviada_em, criado_em) VALUES (?, ?, 'email', 'entrada', ?, 'processada', ?, ?, ?)`,
        lead.id, contatoId, corpo, intencao, diasAtras(dias), diasAtras(dias),
      );
    const primeiro = `Olá, tudo bem?\n\nVi que a ${fantasia} começou as atividades há pouco tempo. Nessa fase, muitas empresas de ${descricao.toLowerCase()} ainda estão definindo como organizar notas, impostos e pró-labore.\n\nSomos um escritório de contabilidade e gostaríamos de entender como vocês estão organizando essa rotina hoje. Faz sentido uma conversa rápida de 15 minutos nesta semana?`;

    if (etapa === 'qualificada' && i % 2 === 0) enviar(0, 'email', primeiro, `Primeiros meses da ${fantasia}`, 'aguardando_aprovacao');
    if (['em_contato', 'respondeu', 'com_voce', 'proposta', 'negociacao', 'cliente', 'pausada', 'perdida'].includes(etapa)) {
      const d0 = 3 + Math.floor(aleatorio() * 18);
      enviar(d0, 'email', primeiro, `Primeiros meses da ${fantasia}`);
      if (etapa === 'pausada' || aleatorio() > 0.5) enviar(Math.max(d0 - 3, 0), 'whatsapp', `Olá, tudo bem? Falo sobre a ${fantasia}. Somos um escritório de contabilidade — posso te fazer duas perguntas rápidas sobre como vocês organizam a parte fiscal hoje?`, null);
    }
    if (etapa === 'respondeu') receber(Math.floor(aleatorio() * 2), 'Oi! Temos interesse sim, ainda estamos organizando tudo. Como funciona o atendimento de vocês?', 'interesse');
    if (etapa === 'perdida') receber(2, 'Obrigado, mas já temos contador.', 'ja_tem_contador');
    if (etapa === 'com_voce') {
      const [texto, motivo] = escolher([
        ['Quanto custaria a contabilidade para uma empresa como a nossa?', 'preco'],
        ['Podemos marcar uma conversa na quinta à tarde?', 'reuniao'],
        ['Vale a pena sair do Simples para o Presumido no nosso caso?', 'tecnico'],
        ['Prefiro falar com o contador responsável, pode me ligar?', 'quer_humano'],
      ] as const);
      const m = receber(Math.floor(aleatorio() * 2), texto, motivo);
      executar('INSERT INTO atendimentos_humanos (lead_id, motivo, resumo, mensagem_id, notificado, criado_em) VALUES (?, ?, ?, ?, 1, ?)', lead.id, motivo, `${fantasia}: "${texto}"`, m.id, diasAtras(0, Math.floor(aleatorio() * 30)));
    }
    if (etapa === 'cliente') executar("INSERT INTO eventos (lead_id, tipo, agente, detalhe, criado_em) VALUES (?, 'mudanca_etapa', 'humano', ?, ?)", lead.id, JSON.stringify({ de: 'negociacao', para: 'cliente', evidencia: 'Contrato de demonstração' }), diasAtras(4));
    for (const tipo of ['enriquecimento', 'qualificacao', 'mensagem_redigida']) {
      executar('INSERT INTO eventos (lead_id, tipo, agente, detalhe, criado_em) VALUES (?, ?, ?, ?, ?)', lead.id, tipo, tipo === 'enriquecimento' ? 'enriquecedor' : tipo === 'qualificacao' ? 'qualificador' : 'redator', JSON.stringify(tipo === 'qualificacao' ? { pontos: pontuacao ?? 40 } : tipo === 'enriquecimento' ? { fontes: ['demonstração'] } : { canal: 'email', tipo: 'primeiro_contato' }), diasAtras(Math.floor(aleatorio() * 5), Math.floor(aleatorio() * 20)));
    }
  });

  // Uso de IA nas últimas 24 h, com um provedor esgotando a cota (para ver o rodízio)
  const provs = ['groq', 'cerebras', 'gemini', 'github', 'ollama'];
  for (let h = 0; h < 24; h++) {
    for (const p of provs) {
      const n = p === 'groq' ? (h < 14 ? 6 : 0) : p === 'cerebras' ? (h >= 14 ? 5 : 1) : Math.floor(aleatorio() * 3);
      for (let k = 0; k < n; k++) {
        executar(
          'INSERT INTO uso_ia (provedor, modelo, tarefa, sucesso, status_http, duracao_ms, criado_em) VALUES (?, ?, ?, 1, 200, ?, ?)',
          p, 'demonstracao', escolher(['redacao', 'revisao', 'qualificacao', 'intencao']), 400 + Math.floor(aleatorio() * 2500), diasAtras(0, 23 - h),
        );
      }
    }
  }
  executar("INSERT INTO uso_ia (provedor, modelo, tarefa, sucesso, status_http, erro, criado_em) VALUES ('groq', 'demonstracao', 'redacao', 0, 429, 'cota diária esgotada | rate limit reached (tokens per day)', ?)", diasAtras(0, 10));
});

salvarConfiguracoes({
  escritorio: {
    nome: 'Moraes & Oliveira Contabilidade',
    razao_social: '',
    cnpj: '',
    crc_organizacao: '',
    responsavel_tecnico: { nome: '', categoria: 'Contador', crc: '' },
    telefone: '',
    site: '',
    cidade: 'Campinas/SP',
    cargo_assinatura: 'Equipe comercial',
  },
});
console.log(`Banco de demonstração criado em ${config.caminhoBanco} com ${EMPRESAS.length} empresas fictícias.`);
