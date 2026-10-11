// Catálogo de provedores de IA com camada gratuita, todos via API compatível com
// o formato "chat/completions". Basta definir a chave no .env para o provedor
// entrar no rodízio. Os modelos mudam com frequência: cada um pode ser trocado
// pela variável IA_MODELO_<ID> sem mexer no código.
//
// `podeTreinar`: true quando a camada gratuita pode usar os dados enviados para
// melhorar modelos, ou quando a política não foi confirmada. Com
// "privacidade estrita" ligada, esses provedores não recebem tarefas que
// contenham dados pessoais (nomes de sócios, conversas). Confira os termos
// vigentes de cada provedor antes de mudar essa marcação.

export type Provedor = {
  id: string;
  nome: string;
  urlBase: string;
  variavelChave: string;
  modeloPadrao: string;
  podeTreinar: boolean;
  local?: boolean;
  observacao: string;
};

export const PROVEDORES: Provedor[] = [
  {
    id: 'groq',
    nome: 'Groq',
    urlBase: 'https://api.groq.com/openai/v1',
    variavelChave: 'GROQ_API_KEY',
    modeloPadrao: 'llama-3.3-70b-versatile',
    podeTreinar: false,
    observacao: 'Camada gratuita com limite por minuto e por dia; muito rápido.',
  },
  {
    id: 'cerebras',
    nome: 'Cerebras',
    urlBase: 'https://api.cerebras.ai/v1',
    variavelChave: 'CEREBRAS_API_KEY',
    modeloPadrao: 'llama-3.3-70b',
    podeTreinar: true,
    observacao: 'Camada gratuita generosa; confirme a política de dados antes de liberar dados pessoais.',
  },
  {
    id: 'gemini',
    nome: 'Google Gemini',
    urlBase: 'https://generativelanguage.googleapis.com/v1beta/openai',
    variavelChave: 'GEMINI_API_KEY',
    modeloPadrao: 'gemini-2.5-flash',
    podeTreinar: true,
    observacao: 'Na camada gratuita o Google pode usar os dados para melhorar produtos.',
  },
  {
    id: 'openrouter',
    nome: 'OpenRouter (modelos :free)',
    urlBase: 'https://openrouter.ai/api/v1',
    variavelChave: 'OPENROUTER_API_KEY',
    modeloPadrao: 'meta-llama/llama-3.3-70b-instruct:free',
    podeTreinar: true,
    observacao: 'Modelos gratuitos podem registrar prompts conforme o provedor final.',
  },
  {
    id: 'sambanova',
    nome: 'SambaNova',
    urlBase: 'https://api.sambanova.ai/v1',
    variavelChave: 'SAMBANOVA_API_KEY',
    modeloPadrao: 'Meta-Llama-3.3-70B-Instruct',
    podeTreinar: true,
    observacao: 'Camada gratuita; confirme a política de dados.',
  },
  {
    id: 'mistral',
    nome: 'Mistral',
    urlBase: 'https://api.mistral.ai/v1',
    variavelChave: 'MISTRAL_API_KEY',
    modeloPadrao: 'mistral-small-latest',
    podeTreinar: true,
    observacao: 'Plano gratuito "Experiment" pode usar dados para treino (há opção de recusa no console).',
  },
  {
    id: 'github',
    nome: 'GitHub Models',
    urlBase: 'https://models.github.ai/inference',
    variavelChave: 'GITHUB_MODELS_TOKEN',
    modeloPadrao: 'openai/gpt-4.1-mini',
    podeTreinar: false,
    observacao: 'Gratuito com limites baixos por dia; bom como reserva de qualidade.',
  },
  {
    id: 'cloudflare',
    nome: 'Cloudflare Workers AI',
    urlBase: 'https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1',
    variavelChave: 'CLOUDFLARE_API_TOKEN',
    modeloPadrao: '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
    podeTreinar: false,
    observacao: 'Cota diária gratuita em "neurons"; exige também CLOUDFLARE_ACCOUNT_ID.',
  },
  {
    id: 'ollama',
    nome: 'Ollama (local)',
    urlBase: 'http://localhost:11434/v1',
    variavelChave: 'OLLAMA_URL',
    modeloPadrao: 'qwen2.5:7b-instruct',
    podeTreinar: false,
    local: true,
    observacao: 'Roda no seu servidor: sem custo e sem limite, dados não saem do escritório. Reserva final.',
  },
];

export function credencial(p: Provedor): string {
  return process.env[p.variavelChave] ?? '';
}

export function provedorConfigurado(p: Provedor): boolean {
  if (p.id === 'cloudflare') return Boolean(credencial(p) && process.env.CLOUDFLARE_ACCOUNT_ID);
  return Boolean(credencial(p));
}

export function urlDoProvedor(p: Provedor): string {
  if (p.local) return (credencial(p) || p.urlBase).replace(/\/$/, '').replace(/(\/v1)?$/, '/v1');
  return p.urlBase.replace('{CLOUDFLARE_ACCOUNT_ID}', process.env.CLOUDFLARE_ACCOUNT_ID ?? '');
}

export const modeloDoProvedor = (p: Provedor) => process.env[`IA_MODELO_${p.id.toUpperCase()}`] || p.modeloPadrao;
