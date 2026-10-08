import { describe, expect, it } from "vitest";
import { formatBRL, formatDate, parseDecimalInput, formatPct } from "@/lib/format";
import { parseDateInput, previousBusinessDay, todayBrasilia } from "@/lib/dates";
import { legSchema, simulationSchema, strategySchema, requestCreateSchema, userCreateSchema, lessonSchema } from "@/lib/schemas";

describe("formatação pt-BR", () => {
  it("moeda, percentuais e datas", () => {
    expect(formatBRL(1234.5).replace(/\s/g, " ")).toBe("R$ 1.234,50");
    expect(formatBRL(null)).toBe("—");
    expect(formatPct(10)).toBe("+10,0%");
    expect(formatDate("2026-10-03T00:00:00.000Z")).toBe("03/10/2026");
  });
  it("interpreta números digitados", () => {
    expect(parseDecimalInput("1.234,56")).toBe("1234.56");
    expect(parseDecimalInput("R$ 12,5")).toBe("12.5");
    expect(parseDecimalInput("12.5")).toBe("12.5");
    expect(parseDecimalInput("abc")).toBeNull();
  });
});

describe("datas", () => {
  it("dia útil anterior (D+1) pula fins de semana", () => {
    expect(previousBusinessDay(new Date("2026-10-12T15:00:00Z")).toISOString().slice(0, 10)).toBe("2026-10-09"); // segunda → sexta
    expect(previousBusinessDay(new Date("2026-10-08T15:00:00Z")).toISOString().slice(0, 10)).toBe("2026-10-07");
  });
  it("data de hoje no fuso de Brasília", () => {
    expect(todayBrasilia(new Date("2026-10-09T02:00:00Z")).toISOString().slice(0, 10)).toBe("2026-10-08");
  });
  it("valida datas digitadas", () => {
    expect(parseDateInput("29/02/2026")).toBeNull();
    expect(parseDateInput("2026-02-28")?.toISOString().slice(0, 10)).toBe("2026-02-28");
  });
});

describe("schemas de validação", () => {
  it("perna de opção exige strike; ação dispensa", () => {
    expect(legSchema.safeParse({ side: "BUY", instrument: "CALL", premium: "1", quantity: 100 }).success).toBe(false);
    expect(legSchema.safeParse({ side: "BUY", instrument: "STOCK", premium: "30", quantity: 100 }).success).toBe(true);
    expect(legSchema.safeParse({ side: "BUY", instrument: "CALL", strike: "36", premium: "1,5", quantity: 0 }).success).toBe(false);
    const ok = legSchema.parse({ side: "SELL", instrument: "PUT", strike: "26,00", premium: "0,48", quantity: "100" });
    expect(ok).toMatchObject({ strike: "26.00", premium: "0.48", quantity: 100 });
  });
  it("simulação: limites de pernas e cenários", () => {
    const base = { name: "Teste", mode: "CLASSICA", underlyingTicker: "PETR4", spotPrice: "36,5", legs: [] };
    expect(simulationSchema.safeParse(base).success).toBe(false);
    const legs = Array.from({ length: 13 }, () => ({ side: "BUY", instrument: "CALL", strike: "1", premium: "1", quantity: 1 }));
    expect(simulationSchema.safeParse({ ...base, legs }).success).toBe(false);
    expect(simulationSchema.safeParse({ ...base, legs: legs.slice(0, 1), scenarios: [{ label: "Alta", price: "40" }] }).success).toBe(true);
  });
  it("estratégia, pedido, usuário e aula", () => {
    expect(strategySchema.safeParse({ title: "x" }).success).toBe(false);
    expect(requestCreateSchema.safeParse({ subject: "Curto", question: "pequena" }).success).toBe(false);
    expect(userCreateSchema.safeParse({ name: "Ana", email: "invalido", role: "USER", password: "12345678" }).success).toBe(false);
    expect(lessonSchema.safeParse({ title: "Aula", content: "Conteúdo válido", videoUrl: "http://inseguro", durationMin: 5 }).success).toBe(false);
    expect(lessonSchema.safeParse({ title: "Aula", content: "Conteúdo válido", videoUrl: "javascript:alert(1)", durationMin: 5 }).success).toBe(false);
  });
});

describe("campos opcionais ausentes", () => {
  it("são aceitos e normalizados para null", () => {
    expect(legSchema.parse({ side: "BUY", instrument: "STOCK", premium: "30", quantity: 1 }).strike).toBeNull();
    expect(requestCreateSchema.parse({ subject: "Assunto válido", question: "Pergunta com mais de vinte caracteres." }).assetTicker).toBeNull();
    expect(lessonSchema.parse({ title: "Aula", content: "Conteúdo válido", durationMin: 5 }).videoUrl).toBeNull();
    const sim = simulationSchema.parse({ name: "Teste", mode: "RAPIDA", underlyingTicker: "PETR4", spotPrice: "36,5", legs: [{ side: "BUY", instrument: "STOCK", premium: "1", quantity: 1 }] });
    expect(sim.expiration).toBeNull();
    expect(simulationSchema.safeParse({ name: "Teste", mode: "RAPIDA", underlyingTicker: "PETR4", spotPrice: "36,5", expiration: "99/99/2026", legs: [{ side: "BUY", instrument: "STOCK", premium: "1", quantity: 1 }] }).success).toBe(false);
  });
});
