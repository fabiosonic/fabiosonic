import { describe, expect, it } from "vitest";
import { inferInstrumentType, parsePositionsCsv, CSV_MAX_ROWS } from "@/lib/csv-positions";

const today = new Date("2026-10-08T12:00:00Z");

describe("importação CSV de posições", () => {
  it("aceita separador ';', vírgula decimal, BOM e cabeçalho com acentos", () => {
    const csv = "﻿Ticker;Quantidade;Preço Médio;Data Referência;Tipo\nPETR4;300;32,45;03/10/2026;ACAO\nbova11;50;120.10;2026-10-03;ETF\n";
    const r = parsePositionsCsv(csv, today);
    expect(r.fatal).toBeUndefined();
    expect(r.rows.map((x) => x.status)).toEqual(["valida", "valida"]);
    expect(r.rows[0]!.row).toMatchObject({ ticker: "PETR4", quantity: 300, averagePrice: "32.45", referenceDate: "2026-10-03", instrumentType: "ACAO" });
    expect(r.rows[1]!.row).toMatchObject({ ticker: "BOVA11", averagePrice: "120.10", instrumentType: "ETF" });
  });

  it("aceita separador ',' com ponto decimal", () => {
    const r = parsePositionsCsv("ticker,quantidade,preco_medio,data_referencia\nVALE3,100,61.2,2026-10-01\n", today);
    expect(r.rows[0]!.status).toBe("valida");
  });

  it("aponta erros por linha", () => {
    const csv = [
      "ticker;quantidade;preco_medio;data_referencia;tipo",
      "PE;100;10;01/10/2026;", // ticker inválido
      "ITUB4;0;10;01/10/2026;", // quantidade zero
      "ITUB3;1,5;10;01/10/2026;", // quantidade fracionária
      "BBAS3;100;abc;01/10/2026;", // preço inválido
      "ABEV3;100;10;31/02/2026;", // data inexistente
      "WEGE3;100;10;01/12/2026;", // data futura
      "RENT3;100;10;01/10/2026;XYZ", // tipo inválido
      "SUZB3;100;10,12345;01/10/2026;", // > 4 casas
    ].join("\n");
    const r = parsePositionsCsv(csv, today);
    expect(r.rows.every((x) => x.status === "erro")).toBe(true);
    expect(r.rows[0]!.errors.join()).toMatch(/Ticker/);
    expect(r.rows[1]!.errors.join()).toMatch(/Quantidade/);
    expect(r.rows[2]!.errors.join()).toMatch(/Quantidade/);
    expect(r.rows[3]!.errors.join()).toMatch(/Preço/);
    expect(r.rows[4]!.errors.join()).toMatch(/Data/);
    expect(r.rows[5]!.errors.join()).toMatch(/futuro/);
    expect(r.rows[6]!.errors.join()).toMatch(/Tipo/);
    expect(r.rows[7]!.errors.join()).toMatch(/casas/);
    expect(r.rows[0]!.line).toBe(2);
  });

  it("detecta ticker duplicado no mesmo arquivo", () => {
    const r = parsePositionsCsv("ticker;quantidade;preco_medio;data_referencia\nPETR4;1;1;01/10/2026\npetr4;2;2;01/10/2026\n", today);
    expect(r.rows.map((x) => x.status)).toEqual(["valida", "duplicada_no_arquivo"]);
    expect(r.rows[1]!.errors[0]).toMatch(/linha 2/);
  });

  it("aceita quantidade negativa (posição vendida)", () => {
    const r = parsePositionsCsv("ticker;quantidade;preco_medio;data_referencia\nPETRK360;-100;1,20;01/10/2026\n", today);
    expect(r.rows[0]!.row).toMatchObject({ quantity: -100, instrumentType: "OPCAO" });
  });

  it("erros fatais: colunas ausentes, vazio, excesso de linhas e tamanho", () => {
    expect(parsePositionsCsv("ticker;quantidade\nPETR4;1", today).fatal).toMatch(/preco_medio/);
    expect(parsePositionsCsv("   ", today).fatal).toMatch(/vazio/);
    expect(parsePositionsCsv("ticker;quantidade;preco_medio;data_referencia\n", today).fatal).toMatch(/Nenhuma linha/);
    const many = ["ticker;quantidade;preco_medio;data_referencia", ...Array.from({ length: CSV_MAX_ROWS + 1 }, (_, i) => `T${String(i).padStart(5, "0")};1;1;01/10/2026`)].join("\n");
    expect(parsePositionsCsv(many, today).fatal).toMatch(/Máximo/);
    expect(parsePositionsCsv("x".repeat(600 * 1024), today).fatal).toMatch(/512/);
  });

  it("infere o tipo de instrumento pelo código", () => {
    expect(inferInstrumentType("PETR4")).toBe("ACAO");
    expect(inferInstrumentType("PETRJ365")).toBe("OPCAO");
    expect(inferInstrumentType("BOVA11")).toBe("OUTRO");
  });
});
