/**
 * Schemas Zod compartilhados entre cliente (feedback imediato) e servidor (validação definitiva).
 */
import { z } from "zod";
import { parseDecimalInput } from "./format";
import { parseDateInput } from "./dates";
import { STRATEGY_TYPES } from "./labels";

const MAX_MONEY = 1_000_000_000;

/** Valor decimal não negativo, aceitando "1.234,56", "1234.56" ou número. Saída: string canônica. */
export const decimalString = (label: string, opts: { positive?: boolean } = {}) =>
  z
    .union([z.string(), z.number()])
    .transform((v) => (typeof v === "number" ? (Number.isFinite(v) ? String(v) : "") : (parseDecimalInput(v) ?? "")))
    .refine((s) => /^\d+(\.\d+)?$/.test(s), `${label}: informe um número válido (não negativo).`)
    .refine((s) => Number(s) <= MAX_MONEY, `${label}: valor muito alto.`)
    .refine((s) => !opts.positive || Number(s) > 0, `${label}: deve ser maior que zero.`)
    .refine((s) => (s.split(".")[1]?.length ?? 0) <= 4, `${label}: use no máximo 4 casas decimais.`);

export const optionalDecimalString = (label: string) =>
  z
    .union([z.string(), z.number(), z.null(), z.undefined()])
    .transform((v) => (v === null || v === undefined || v === "" ? null : v))
    .pipe(z.union([z.null(), decimalString(label, { positive: true })]));

/** Data "aaaa-mm-dd" ou "dd/mm/aaaa" → Date (meia-noite UTC). */
export const dateInput = (label: string) =>
  z
    .string()
    .transform((s) => parseDateInput(s))
    .refine((d): d is Date => d !== null, `${label}: data inválida.`)
    .transform((d) => d as Date);

export const tickerSchema = z
  .string()
  .trim()
  .toUpperCase()
  .regex(/^[A-Z0-9]{4,12}$/, "Código de ativo inválido (use letras e números, ex.: PETR4).");

const text = (label: string, min: number, max: number) =>
  z
    .string()
    .trim()
    .min(min, `${label}: mínimo de ${min} caracteres.`)
    .max(max, `${label}: máximo de ${max} caracteres.`);

export const legSchema = z
  .object({
    side: z.enum(["BUY", "SELL"], "Selecione compra ou venda."),
    instrument: z.enum(["CALL", "PUT", "STOCK"], "Selecione CALL, PUT ou ação."),
    strike: optionalDecimalString("Strike")
      .optional()
      .transform((v) => v ?? null),
    premium: decimalString("Prêmio/preço"),
    quantity: z.coerce
      .number("Quantidade inválida.")
      .int("Quantidade deve ser inteira.")
      .min(1, "Quantidade mínima: 1.")
      .max(1_000_000, "Quantidade máxima: 1.000.000."),
    optionSymbol: z.string().trim().toUpperCase().max(20).optional().nullable(),
  })
  .superRefine((leg, ctx) => {
    if (leg.instrument !== "STOCK" && !leg.strike) {
      ctx.addIssue({ code: "custom", path: ["strike"], message: "Strike obrigatório para opções." });
    }
  });
export type LegForm = z.input<typeof legSchema>;
export type LegData = z.output<typeof legSchema>;

export const scenarioSchema = z.object({
  label: text("Nome do cenário", 1, 40),
  price: decimalString("Preço do cenário"),
});

export const simulationSchema = z.object({
  name: text("Nome", 2, 120),
  mode: z.enum(["RAPIDA", "CLASSICA", "PREVISOES"]),
  underlyingTicker: tickerSchema,
  spotPrice: decimalString("Preço de referência", { positive: true }),
  multiplier: z.coerce.number().int().min(1, "Multiplicador mínimo: 1.").max(10_000).default(1),
  fees: decimalString("Custos").default("0"),
  expiration: z
    .string()
    .nullish()
    .transform((v, ctx) => {
      if (!v) return null;
      const d = parseDateInput(v);
      if (!d) {
        ctx.addIssue({ code: "custom", message: "Vencimento inválido." });
        return z.NEVER;
      }
      return d;
    }),
  scenarios: z.array(scenarioSchema).max(10, "Máximo de 10 cenários.").default([]),
  notes: z.string().trim().max(2000).optional().nullable(),
  sourceStrategyId: z.string().max(40).optional().nullable(),
  legs: z.array(legSchema).min(1, "Inclua ao menos uma perna.").max(12, "Máximo de 12 pernas."),
});
export type SimulationInput = z.input<typeof simulationSchema>;

export const strategyTypeSchema = z.enum(Object.keys(STRATEGY_TYPES) as [keyof typeof STRATEGY_TYPES, ...(keyof typeof STRATEGY_TYPES)[]]);

export const strategySchema = z.object({
  title: text("Título", 3, 160),
  strategyType: strategyTypeSchema,
  assetTicker: tickerSchema,
  summary: text("Resumo", 10, 600),
  assumptions: text("Premissas", 10, 4000),
  riskNotes: text("Riscos", 10, 2000),
  referencePrice: decimalString("Preço de referência", { positive: true }),
  expiration: dateInput("Vencimento"),
  legs: z.array(legSchema).min(1, "Inclua ao menos uma perna.").max(8, "Máximo de 8 pernas."),
});
export type StrategyInput = z.input<typeof strategySchema>;

export const analysisSchema = z.object({
  title: text("Título", 3, 160),
  assetTicker: z
    .union([tickerSchema, z.literal(""), z.null()])
    .optional()
    .transform((v) => v || null),
  summary: text("Resumo", 10, 600),
  body: text("Conteúdo", 20, 20000),
});

export const contentStatusActionSchema = z.object({
  action: z.enum(["publish", "archive", "unarchive"]),
});

export const requestCreateSchema = z.object({
  subject: text("Assunto", 5, 160),
  assetTicker: z
    .union([tickerSchema, z.literal(""), z.null()])
    .optional()
    .transform((v) => v || null),
  question: text("Descrição", 20, 4000),
});

export const requestMessageSchema = z.object({ body: text("Mensagem", 2, 4000) });

export const requestStatusSchema = z.object({
  status: z.enum(["OPEN", "IN_ANALYSIS", "ANSWERED", "CLOSED"]),
});

export const userCreateSchema = z.object({
  name: text("Nome", 2, 120),
  email: z.string().trim().toLowerCase().pipe(z.email("E-mail inválido.")),
  role: z.enum(["ADMIN", "ANALYST", "USER"]),
  password: z.string().min(8, "Senha: mínimo de 8 caracteres.").max(128),
});

export const userUpdateSchema = z
  .object({
    role: z.enum(["ADMIN", "ANALYST", "USER"]).optional(),
    active: z.boolean().optional(),
  })
  .refine((v) => v.role !== undefined || v.active !== undefined, "Nada a alterar.");

export const courseSchema = z.object({
  title: text("Título", 3, 160),
  slug: z
    .string()
    .trim()
    .toLowerCase()
    .regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, "Identificador: use letras minúsculas, números e hífens."),
  description: text("Descrição", 10, 2000),
  status: z.enum(["DRAFT", "PUBLISHED", "ARCHIVED"]).default("DRAFT"),
});

export const moduleSchema = z.object({ title: text("Título", 2, 160) });

const httpsUrl = z
  .union([z.string().trim(), z.null()])
  .optional()
  .transform((v) => v || null)
  .refine((v) => v === null || /^https:\/\/[^\s]+$/.test(v), "Use um link https autorizado.");

export const lessonSchema = z.object({
  title: text("Título", 2, 160),
  content: text("Conteúdo", 10, 20000),
  videoUrl: httpsUrl,
  durationMin: z.coerce.number().int().min(1).max(600),
});

export const liveSchema = z.object({
  title: text("Título", 3, 160),
  description: text("Descrição", 5, 2000),
  kind: z.enum(["LIVE", "AULA"]),
  status: z.enum(["SCHEDULED", "CANCELED", "DONE"]).default("SCHEDULED"),
  startsAt: z.coerce.date("Data/hora inválida."),
  durationMin: z.coerce.number().int().min(10).max(600),
  link: httpsUrl,
  courseId: z.string().max(40).optional().nullable(),
});

export const pageQuery = z.object({
  page: z.coerce.number().int().min(1).catch(1).default(1),
  pageSize: z.coerce.number().int().min(5).max(100).catch(20).default(20),
});
