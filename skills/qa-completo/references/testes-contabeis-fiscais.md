# Casos de teste para sistemas contábeis, fiscais e de folha

Use só os blocos que se aplicam ao programa. Calcule o resultado esperado à mão (ou numa planilha conferida) — nunca copie o valor que o próprio código devolve. Coloque no comentário do teste a norma usada e lembre o usuário de conferir a vigência para a competência em questão: alíquotas, faixas e limites mudam.

## Regras gerais de dinheiro
- Valores monetários em `Decimal` ou centavos inteiros; `0.1 + 0.2` não pode virar `0.30000000000000004`.
- Arredondamento: defina e teste a regra (meio para cima / bancário / truncamento) e onde ela acontece (por item ou no total). Teste um caso que dá diferença de 1 centavo entre as duas formas.
- Rateios: a soma das parcelas rateadas tem que bater exatamente com o total (sobra de centavo vai para alguma parcela).
- Entrada no formato brasileiro: `"1.234,56"` → 1234.56; valores negativos entre parênteses ou com sinal.

## Partidas dobradas e demonstrações
- Todo lançamento: soma dos débitos = soma dos créditos. Teste que um lançamento desbalanceado é rejeitado.
- Balancete: total devedor = total credor; saldo final = saldo inicial + débitos − créditos (contas de natureza devedora) e o inverso para natureza credora.
- Balanço: Ativo = Passivo + Patrimônio Líquido (NBC TG 26 / CPC 26).
- DRE: resultado do período transportado corretamente para o PL; encerramento de contas de resultado zera receitas e despesas.
- Conta sintética não recebe lançamento; só analítica.
- Período fechado não aceita lançamento retroativo (ou exige permissão).

## Conciliação bancária
- Saldo final do extrato (OFX) = saldo contábil da conta banco após os lançamentos.
- Lançamento duplicado (mesmo valor, data e histórico) é detectado, não importado duas vezes.
- OFX com encoding Latin-1 e com caracteres especiais no histórico.

## Simples Nacional (LC 123/2006)
- Alíquota efetiva = (RBT12 × alíquota nominal − parcela a deduzir) ÷ RBT12. Teste:
  - RBT12 exatamente no limite de uma faixa e R$ 0,01 acima;
  - empresa com menos de 12 meses de atividade (RBT12 proporcional — art. 18, §2º);
  - Fator R (folha 12 meses ÷ RBT12) exatamente 28%, um pouco abaixo e um pouco acima, para atividades sujeitas a Anexo III/V;
  - segregação de receitas monofásicas de PIS/COFINS e com ST de ICMS (valor do tributo deduzido da alíquota).
- Confira as tabelas dos Anexos no texto vigente da LC 123/2006.

## Retenções na fonte sobre serviços
- PIS/COFINS/CSLL retidos: 4,65% (0,65% + 3% + 1%) — Lei 10.833/2003, art. 30. Teste a dispensa quando o valor retido for de até R$ 10,00 (art. 31, §3º) e a não retenção para optantes do Simples.
- IRRF: 1,5% para serviços profissionais (RIR/2018) e 1% para limpeza, conservação, segurança e locação de mão de obra; teste a dispensa de DARF de valor inferior a R$ 10,00.
- INSS: 11% sobre cessão de mão de obra/empreitada (Lei 8.212/1991, art. 31), com dedução de materiais/equipamentos quando discriminados.
- ISS retido: município de incidência correto (LC 116/2003, art. 3º — regra geral e exceções), alíquota mínima de 2%.
- Valor líquido da nota = bruto − todas as retenções.

## Lucro Presumido
- Base de presunção por atividade (8% comércio/indústria, 32% serviços em geral para IRPJ; 12%/32% para CSLL — Lei 9.249/1995). Teste empresa com mais de uma atividade.
- Adicional de IRPJ de 10% sobre a parcela que exceder R$ 60.000,00 no trimestre.
- PIS 0,65% e COFINS 3% cumulativos.

## Folha de pagamento
- Tabelas progressivas de INSS e IRRF vigentes na competência (cálculo faixa a faixa no INSS; dedução por dependente e desconto simplificado no IRRF, o que for mais vantajoso).
- Teto do INSS; salário exatamente no limite de uma faixa.
- FGTS 8% (2% aprendiz).
- Férias com 1/3, 13º em duas parcelas, rescisão com aviso indenizado, proporcionais por avos (fração ≥ 15 dias conta como mês).
- Admissão e demissão no meio do mês (salário proporcional).

## Documentos fiscais e arquivos
- XML de NF-e/NFS-e/CT-e: leitura correta de CFOP, CST/CSOSN, NCM, valores e retenções; nota cancelada não entra no faturamento; nota de devolução reduz receita.
- Chave de acesso com 44 dígitos e dígito verificador válido.
- CNPJ/CPF: validação de dígitos verificadores; aceitar com e sem máscara; CNPJ alfanumérico (IN RFB 2.229/2024) se o sistema precisar estar pronto para ele.
- Arquivos SPED/layout de importação: tamanho de campos, separador `|`, encoding, quebra de linha, totalizadores de bloco batendo com a quantidade de registros.

## Datas e competência
- Competência ≠ data de emissão ≠ data de pagamento: teste nota emitida em um mês e paga no seguinte.
- Vencimento que cai em fim de semana/feriado (antecipa ou prorroga conforme o tributo).
- Fevereiro, ano bissexto, último dia do mês.
