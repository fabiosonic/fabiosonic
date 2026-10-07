# Base normativa — esquema

Cada arquivo `*.yaml` desta pasta (e subpastas, ex.: `icms/RJ.yaml`) contém uma lista de normas:

```yaml
- id: TABELA_CFOP                # identificador único, usado pelas regras
  titulo: Tabela de CFOP (Convênio s/nº de 1970 e ajustes SINIEF)
  area: fiscal                   # fiscal | contabil | dp | cadastro | societario | reforma
  status: PENDENTE               # PENDENTE | FONTE_LOCALIZADA | CONFERIDO | REVOGADA
  fonte_url:                     # URL oficial conferida (https, *.gov.br/*.jus.br/*.leg.br/cfc/cpc)
  fonte_url_sugerida:            # sugestão a conferir — NÃO vale como fonte
  conferido_por:                 # nome da PESSOA que conferiu (nunca "Claude"/"IA")
  conferido_em:                  # AAAA-MM-DD
  hash_texto:                    # sha256 do texto oficial salvo (monitor de mudança)
  dispositivos: []               # artigos/itens que sustentam os parâmetros
  aplica_se:                     # filtros de perfil (todos opcionais)
    regimes: [SIMPLES, MEI]      # SIMPLES | MEI | PRESUMIDO | REAL | IMUNE | ISENTA
    ufs: [RJ]
    municipios: ["3304557"]      # código IBGE
    naturezas_juridicas: ["2062"]
    cnae_prefixos: ["4120"]
  vigencia: {inicio: , fim: }
  parametros: {}                 # SÓ são usados quando status = CONFERIDO
  decisao_judicial:              # opcional; exige transito_em_julgado e modulacao
  observacao:
```

Regras:
- O sistema **recusa carregar** norma CONFERIDO sem `fonte_url` oficial, `conferido_por`
  humano e `conferido_em`.
- `parametros` de norma não conferida podem ficar escritos como PROPOSTA, mas nenhuma regra
  os enxerga (`Catalogo.parametro` devolve `None`) — a regra fica INATIVA.
- Marcar CONFERIDO é ato humano: abra a fonte oficial, confira o dispositivo, preencha
  `conferido_por`/`conferido_em` e o `hash_texto`.
