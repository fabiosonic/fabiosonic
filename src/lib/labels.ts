export const ROLE_LABEL = { ADMIN: "Administrador", ANALYST: "Analista", USER: "Usuário" } as const;

export const CONTENT_STATUS_LABEL = { DRAFT: "Rascunho", PUBLISHED: "Publicado", ARCHIVED: "Arquivado" } as const;

export const REQUEST_STATUS_LABEL = { OPEN: "Aberto", IN_ANALYSIS: "Em análise", ANSWERED: "Respondido", CLOSED: "Encerrado" } as const;

export const CONNECTION_STATUS_LABEL = {
  DISCONNECTED: "Desconectado",
  CONNECTED: "Conectado",
  SYNCING: "Sincronizando",
  ERROR: "Erro",
} as const;

export const SYNC_STATUS_LABEL = { RUNNING: "Em andamento", SUCCESS: "Concluída", ERROR: "Falhou" } as const;

export const DATA_SOURCE_LABEL = { DEMO: "Demonstrativo", DELAYED: "Atrasado", REALTIME: "Tempo real" } as const;

export const SIDE_LABEL = { BUY: "Compra", SELL: "Venda" } as const;
export const INSTRUMENT_LABEL = { CALL: "CALL", PUT: "PUT", STOCK: "Ação" } as const;

export const SIM_MODE_LABEL = { RAPIDA: "Boleta rápida", CLASSICA: "Boleta clássica", PREVISOES: "Previsões" } as const;

export const LIVE_KIND_LABEL = { LIVE: "Live", AULA: "Aula ao vivo" } as const;
export const LIVE_STATUS_LABEL = { SCHEDULED: "Agendada", CANCELED: "Cancelada", DONE: "Realizada" } as const;

export const POSITION_SOURCE_LABEL = { B3_DEMO: "B3 (demonstração)", CSV: "Importação CSV" } as const;
export const INSTRUMENT_TYPE_LABEL = { ACAO: "Ação", OPCAO: "Opção", FII: "FII", ETF: "ETF", OUTRO: "Outro" } as const;

export const STRATEGY_TYPES = {
  COMPRA_CALL: "Compra de CALL",
  COMPRA_PUT: "Compra de PUT",
  VENDA_COBERTA: "Venda coberta",
  VENDA_PUT: "Venda de PUT",
  TRAVA_ALTA: "Trava de alta",
  TRAVA_BAIXA: "Trava de baixa",
  BORBOLETA: "Borboleta",
  STRADDLE: "Straddle",
  STRANGLE: "Strangle",
  COLLAR: "Collar (financiamento com proteção)",
  OUTRA: "Outra",
} as const;
export type StrategyType = keyof typeof STRATEGY_TYPES;
