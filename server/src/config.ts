// Configuração de infraestrutura lida do ambiente (.env). As regras de negócio
// editáveis pelo painel (perfil de cliente ideal, cadência, limites, autonomia)
// ficam na tabela `configuracoes` — ver src/configuracoes.ts.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function carregarDotEnv(caminho: string) {
  if (!existsSync(caminho)) return;
  for (const bruta of readFileSync(caminho, 'utf8').split('\n')) {
    const linha = bruta.trim();
    if (!linha || linha.startsWith('#')) continue;
    const igual = linha.indexOf('=');
    if (igual < 0) continue;
    const chave = linha.slice(0, igual).trim();
    let valor = linha.slice(igual + 1).trim();
    if ((valor.startsWith('"') && valor.endsWith('"')) || (valor.startsWith("'") && valor.endsWith("'"))) valor = valor.slice(1, -1);
    if (process.env[chave] === undefined) process.env[chave] = valor;
  }
}

carregarDotEnv(resolve(process.cwd(), '.env'));
carregarDotEnv(resolve(process.cwd(), '..', '.env'));

const texto = (k: string, padrao = '') => process.env[k] ?? padrao;
const numero = (k: string, padrao: number) => (process.env[k] ? Number(process.env[k]) : padrao);
const logico = (k: string, padrao = false) =>
  process.env[k] ? ['1', 'true', 'sim', 'yes'].includes(process.env[k]!.toLowerCase()) : padrao;

export const config = {
  porta: numero('PORTA', 3333),
  urlPublica: texto('URL_PUBLICA', 'http://localhost:3333').replace(/\/$/, ''),
  caminhoBanco: texto('CAMINHO_BANCO', resolve(process.cwd(), 'dados', 'comercial.db')),
  senhaAdmin: texto('SENHA_ADMIN'),
  segredoSessao: texto('SEGREDO_SESSAO', 'troque-este-segredo'),
  agendadorLigado: !logico('AGENDADOR_DESLIGADO'),

  smtp: {
    host: texto('SMTP_HOST'),
    porta: numero('SMTP_PORTA', 587),
    seguro: logico('SMTP_SEGURO'),
    usuario: texto('SMTP_USUARIO'),
    senha: texto('SMTP_SENHA'),
    remetente: texto('SMTP_REMETENTE'),
  },
  imap: {
    host: texto('IMAP_HOST'),
    porta: numero('IMAP_PORTA', 993),
    seguro: logico('IMAP_SEGURO', true),
    usuario: texto('IMAP_USUARIO') || texto('SMTP_USUARIO'),
    senha: texto('IMAP_SENHA') || texto('SMTP_SENHA'),
  },

  whatsapp: {
    // 'cloud' = API oficial da Meta (recomendado); 'evolution' = Evolution API
    // (não oficial, risco de banimento do número); '' = desligado
    provedor: texto('WHATSAPP_PROVEDOR') as '' | 'cloud' | 'evolution',
    cloudToken: texto('WA_CLOUD_TOKEN'),
    cloudIdNumero: texto('WA_CLOUD_ID_NUMERO'),
    cloudTokenVerificacao: texto('WA_CLOUD_TOKEN_VERIFICACAO'),
    cloudSegredoApp: texto('WA_CLOUD_SEGREDO_APP'),
    cloudVersaoApi: texto('WA_CLOUD_VERSAO_API', 'v21.0'),
    nomeModelo: texto('WA_NOME_MODELO'),
    idiomaModelo: texto('WA_IDIOMA_MODELO', 'pt_BR'),
    evolutionUrl: texto('EVOLUTION_URL').replace(/\/$/, ''),
    evolutionChave: texto('EVOLUTION_CHAVE_API'),
    evolutionInstancia: texto('EVOLUTION_INSTANCIA'),
    evolutionTokenWebhook: texto('EVOLUTION_TOKEN_WEBHOOK'),
  },

  // Para onde o sistema avisa quando um lead precisa de você
  responsavel: {
    nome: texto('RESPONSAVEL_NOME', 'Responsável comercial'),
    email: texto('RESPONSAVEL_EMAIL'),
    whatsapp: texto('RESPONSAVEL_WHATSAPP'),
  },

  ia: {
    simulada: logico('IA_SIMULADA'),
    tempoLimiteMs: numero('IA_TEMPO_LIMITE_MS', 45000),
  },

  receita: {
    urlDadosAbertos: texto('RF_URL_DADOS_ABERTOS', 'https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj'),
  },
};

export type Config = typeof config;
