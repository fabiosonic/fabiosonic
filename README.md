# Portal Contábil · Importação e Auditoria Fiscal

Motor do portal do cliente: o cliente envia **tudo de uma vez** (uma pasta ou um ZIP com XMLs, extratos e folha) e o portal **importa, classifica, cruza e audita**. Ele devolve um relatório com riscos, não conformidades e tributos recuperáveis, cada um com a base legal e a ação recomendada.

## O que o portal importa

| Formato | Conteúdo |
|---|---|
| XML NF-e (mod. 55) e NFC-e (mod. 65) | `nfeProc` com protocolo, inclusive grupo IBS/CBS (NT 2025.002) |
| XML de eventos de NF-e | cancelamento (110111) e cancelamento por substituição (110112) |
| XML NFS-e Padrão Nacional | NFS-e do ADN/Sefin Nacional e eventos de cancelamento |
| XML NFS-e ABRASF | layouts municipais (histórico e municípios em transição) |
| OFX | extratos bancários SGML/XML, com deduplicação de extratos sobrepostos |
| CSV de folha | `competencia;salarios;pro_labore;encargos` (para o Fator R) |
| ZIP | inclusive ZIP dentro de ZIP, com pastas, até 50 mil arquivos |

Os documentos são deduplicados pela chave de acesso. A empresa auditada e o regime são detectados automaticamente. O portal aceita **CNPJ alfanumérico** (IN RFB 2.229/2024).

## O que o portal audita

| Código | Regra | Base legal |
|---|---|---|
| DOC001–011 | XML sem protocolo, uso denegado, chave inválida (DV), CNPJ/CPF inválido, numeração duplicada, **lacunas de numeração**, documentos de terceiros no lote (LGPD), cancelamentos | Ajuste SINIEF 07/2005 |
| NFE001–002 | Soma dos itens x vProd; recálculo do vNF | MOC NF-e |
| NFE003–004 | CFOP x tipo de operação; CFOP x UF de destino | Tabela CFOP |
| NFE005 | CRT x CST/CSOSN (enquadramento errado no emissor) | Ajuste SINIEF 07/2005 |
| NFE006 | NCM ausente ou inválido | TIPI |
| NFE007 | **Reforma Tributária**: NF-e de 2026 do regime regular sem o grupo IBS/CBS | LC 214/2025, arts. 343–348 |
| NFS001 | **Retenção de IRRF/CSRF sobre optante do Simples** (indevida, recuperável) | LC 123/2006, art. 13, §3º |
| NFS002 | Alíquotas de IRRF (1%/1,5%), CSRF (4,65%) e INSS (11%/3,5%) | RIR/2018; Lei 10.833/2003 |
| NFS003 | ISS fora da faixa de 2% a 5% | LC 116/2003, art. 8º-A |
| NFS004 | Valor líquido x retenções | — |
| NFS005 | Serviço tomado sem retenção (responsabilidade do tomador) | Lei 10.833/2003, art. 30 |
| SN001–004 | **Limites do MEI, do Simples e do sublimite**, com a regra dos 20% | LC 123/2006, arts. 3º, 18-A e 20 |
| SN005 | **Fator R** mês a mês e a folha que falta para chegar a 28% | LC 123/2006, art. 18, §5º-J |
| SN006 | Histórico insuficiente para o RBT12 | LC 123/2006, art. 18, §1º |
| SN010 | **Receita monofásica de PIS/COFINS a segregar** (recuperação) | LC 123/2006, art. 18, §4º-A |
| SN011 | **Receita com ICMS-ST (CSOSN 500) a segregar** (recuperação) | LC 123/2006, art. 18, §4º-A |
| SN012 | **ISS retido**: evita pagar o ISS duas vezes no DAS | LC 123/2006, art. 21, §4º |
| CON001 | **Créditos bancários sem nota** (risco de omissão de receita) | Lei 9.430/1996, art. 42 |
| CON002–006 | Créditos não operacionais sem lastro, adquirentes x NFC-e (DIMP), notas sem recebimento, tarifas, notas ainda no prazo | — |

Achados repetidos em vários documentos são consolidados num único item, com o detalhe nota a nota no Excel. O **índice de conformidade (0–100)** pondera os achados pela severidade.

A receita bruta é apurada por CFOP de venda e prestação de serviço, deduzidas as devoluções. Remessas, transferências e vendas de ativo imobilizado ficam fora.

## Como usar

```bash
pip install -e ".[web,dev]"

# Linha de comando: pastas, ZIPs ou arquivos soltos
python -m portal_contabil auditar /caminho/dos/arquivos --cnpj 12.345.678/0001-95 --regime simples
#   -> relatorio_auditoria/auditoria.html | auditoria.xlsx | auditoria.json
#   código de saída 2 quando há achado crítico (útil em rotinas automáticas)

# Portal web (upload por arrastar e soltar)
PORTAL_USUARIO=escritorio PORTAL_SENHA='troque-esta-senha' python -m portal_contabil web --porta 8000

# Demonstração com dados fictícios
python exemplos/gerar_demo.py
python -m portal_contabil auditar exemplos/demo/lote_demo.zip --saida exemplos/demo/relatorio

# Testes
python -m pytest
```

## Segurança e LGPD

- Os XMLs são lidos com `defusedxml`, que bloqueia entidades maliciosas e XXE.
- Os ZIPs são lidos em memória, sem extração para disco (o que evita *zip-slip*). Há limite de 1 GiB descompactado, 50 MB por arquivo e profundidade máxima de 3 níveis de ZIP aninhado.
- O portal web não grava os arquivos enviados. Só os relatórios ficam no disco, e são apagados após `PORTAL_RETENCAO_HORAS` (24 h por padrão).
- O login HTTP Basic é ativado por `PORTAL_USUARIO`/`PORTAL_SENHA`. Em produção, publique atrás de HTTPS e de um provedor de identidade com um perfil por empresa.
- Documentos de terceiros misturados no lote geram um alerta específico (DOC008).

## Limites conhecidos

- A lista de NCM monofásicos (`auditoria/tabelas.py`) é uma referência inicial por prefixo. Valide o NCM completo e os "Ex" da TIPI antes de retificar o PGDAS-D.
- O Fator R depende do CSV de folha. O portal não sabe quais atividades da empresa estão sujeitas a ele, por isso o achado é condicional.
- No leiaute nacional de NFS-e, o campo `tpRetPisCofins` mudou de tabela entre versões. Confira a versão em uso.
- O CT-e é reconhecido, mas ainda não é auditado. A conciliação de cartões é feita por totais (os relatórios das adquirentes ainda não são importados).
- Os achados são **indícios** gerados por regras automáticas. Pela NBC PG 01, cabe ao contador responsável validar cada um antes de qualquer retificação.

## Próximas etapas sugeridas

1. Captura automática de documentos: Distribuição DF-e (NF-e recebidas) e a API do ADN (NFS-e), usando o certificado do cliente.
2. Importação do relatório das adquirentes (Cielo, Stone, Rede) para conciliar cartões venda a venda.
3. Exportação dos lançamentos já auditados para o ERP do escritório (Domínio, Alterdata, Questor).
4. CT-e, EFD-Reinf e cruzamento com o PGDAS-D transmitido (arquivo da declaração).
5. Banco de dados multiempresa, com histórico das auditorias e um painel da carteira de clientes.
