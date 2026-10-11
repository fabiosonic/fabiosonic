import './ambiente.ts';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { dividirLinha, filtrarEstabelecimento, percorrerZip } from '../src/fontes/receita-dados-abertos.ts';

// Linha no layout oficial de Estabelecimentos (30 colunas)
const linha = (o: { cnpj?: string; matriz?: string; situacao?: string; abertura?: string; cnae?: string; uf?: string; mun?: string }) =>
  [
    o.cnpj ?? '11222333', '0001', '81', o.matriz ?? '1', 'PADARIA SÃO JOÃO', o.situacao ?? '02', '20260901', '00', '', '',
    o.abertura ?? '20260901', o.cnae ?? '1091102', '', 'RUA', 'DAS FLORES', '100', '', 'CENTRO', '13010000', o.uf ?? 'SP', o.mun ?? '6291',
    '19', '999998888', '', '', '', '', 'CONTATO@PADARIA.COM.BR', '', '',
  ].map((c) => `"${c}"`).join(';');

const filtro = { ufs: new Set(['SP']), municipios: null, cnaesPrefixos: ['10'], aberturaMinima: '20260801' };

test('divide linhas do CSV da Receita respeitando aspas', () => {
  assert.deepEqual(dividirLinha('"A";"B; C";"D ""x"""'), ['A', 'B; C', 'D "x"']);
});

test('filtra só matriz ativa, no perfil e aberta recentemente', () => {
  const ok = filtrarEstabelecimento(dividirLinha(linha({})), filtro)!;
  assert.equal(ok.cnpj, '11222333000181');
  assert.equal(ok.data_abertura, '2026-09-01');
  assert.equal(ok.email, 'contato@padaria.com.br');
  assert.equal(filtrarEstabelecimento(dividirLinha(linha({ matriz: '2' })), filtro), null, 'filial');
  assert.equal(filtrarEstabelecimento(dividirLinha(linha({ situacao: '08' })), filtro), null, 'baixada');
  assert.equal(filtrarEstabelecimento(dividirLinha(linha({ abertura: '20200101' })), filtro), null, 'antiga');
  assert.equal(filtrarEstabelecimento(dividirLinha(linha({ cnae: '4711302' })), filtro), null, 'CNAE fora');
  assert.equal(filtrarEstabelecimento(dividirLinha(linha({ uf: 'RJ' })), filtro), null, 'UF fora');
});

test('lê o .zip oficial decodificando latin1', async () => {
  const pasta = mkdtempSync(join(tmpdir(), 'rf-teste-'));
  const csv = join(pasta, 'K3241.K03200Y0.D60913.ESTABELE');
  writeFileSync(csv, Buffer.from(linha({}) + '\n' + linha({ cnpj: '99887766' }) + '\n', 'latin1'));
  const zip = join(pasta, 'Estabelecimentos0.zip');
  execFileSync('python3', ['-I', '-c', 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1],"w",zipfile.ZIP_DEFLATED); z.write(sys.argv[2],"estab.csv"); z.close()', zip, csv]);
  const lidas: string[][] = [];
  await percorrerZip(zip, (c) => lidas.push(c));
  assert.equal(lidas.length, 2);
  assert.equal(lidas[0][4], 'PADARIA SÃO JOÃO');
});
