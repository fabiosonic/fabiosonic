# Testes

## Como executar

```bat
windows\testar.bat
```
ou
```bash
cd backend && python -m pytest tests
```

Os testes usam **somente** o laboratório SIMULADO (`moxml/simulador`): certificados autoassinados de teste, NF-e/NFC-e assinadas e uma SEFAZ/portal falsos que reproduzem as regras do MOC. **Nenhuma chamada fiscal real é feita.**

## Resultado nesta entrega

- **65 testes, 65 aprovados**, em **CPython 3.14.6** (Linux, 19/11/2026). Versões das dependências fixadas em `backend/requirements.txt`.
- O build do frontend (`tsc --noEmit && vite build`) passou.
- O painel foi aberto em Chromium headless (Playwright) nas páginas principais, sem erros de console.
- Não executado: testes em Windows real, PostgreSQL real e chamadas reais à SEFAZ/SVRS/Drive. Ver LIMITACOES.md.

## Cobertura dos cenários obrigatórios (seção 16)

| Cenário | Teste |
|---|---|
| Certificado válido | `test_seguranca_certificados.py::test_certificado_valido_identifica_cnpj` |
| Certificado vencido | `::test_certificado_vencido` |
| Senha incorreta | `::test_senha_incorreta`, `test_integracoes_api.py::test_api_fluxo_basico` |
| CNPJ incompatível | `::test_cnpj_incompativel`, `test_motor.py::test_xml_de_outro_cnpj_rejeitado` |
| Nenhuma nota encontrada | `test_motor.py::test_nenhuma_nota_sem_serie`, `test_conectores.py::test_descoberta_562_devolve_chave` (217) |
| Uma nota encontrada | `test_motor.py::test_uma_nota_alem_da_semente` |
| Milhares de notas / paginação | `test_conectores.py::test_sae_paginacao_milhares` (2.500 chaves, páginas de 1.000), `::test_apisimples_paginacao_e_base64` |
| XML duplicado | `test_motor.py::test_duplicidade_e_reexecucao_idempotente` |
| XML cancelado | `test_motor.py::test_nfe_e_nfce_independentes_e_cancelamento`, `test_conectores.py::test_situacao_cancelada_traz_evento` |
| Evento posterior | `test_motor.py::test_evento_posterior_capturado_na_reverificacao` (cancelamento e CC-e após a captura) |
| Falha de rede | `test_conectores.py::test_falha_de_rede_com_retentativa` |
| Timeout | `::test_timeout_esgota_retentativas` |
| Limite de consultas | `::test_consumo_indevido_bloqueia` (656 → bloqueio de 1 h), `::test_limitador_local` |
| Resposta inválida | `::test_resposta_invalida` |
| Falha no Google Drive | `test_integracoes_api.py::test_drive_falha_em_um_arquivo_nao_interrompe`, `::test_drive_sem_confirmacao_nao_marca_sincronizado` |
| Reinício durante captura / recuperação após interrupção | `test_motor.py::test_reinicio_durante_captura_retoma_sem_perda` |
| Isolamento entre empresas | `test_motor.py::test_isolamento_de_falhas_entre_empresas` |
| NF-e e NFC-e testadas separadamente | `test_motor.py::test_nfe_e_nfce_independentes_e_cancelamento` (contagens por modelo) |
| Lacunas sem presumir omissão | `test_motor.py::test_lacunas_classificadas_sem_presumir_omissao` (217 → NAO_CONSTA_NA_SEFAZ; inutilização) |
| CAPTCHA no portal | `test_conectores.py::test_portal_com_captcha_interrompe`, `test_motor.py::test_sem_fonte_de_xml_integral_mantem_pendente` |
| SVRS sem concatenar a chave | `test_conectores.py::test_descoberta_impossivel_sem_concatenacao` |
| Modo REAL sem certificado | `test_motor.py::test_modo_real_sem_certificado_nao_consulta` (zero chamadas) |
| Pastas: incremental, incompleto, zip, inválido | `test_motor.py::test_pasta_emissor_incremental_incompleto_zip` |
| XML adulterado / XXE / incompleto | `test_fiscal.py::test_xml_adulterado_detectado`, `::test_xml_invalido_incompleto` |
| XSD oficial PL_010g | `test_fiscal.py::test_validacao_xsd_oficial_registra_aviso_sem_rejeitar` |
| Domínio sem alterar XML | `test_integracoes_api.py::test_exportacao_dominio_preserva_xml` (SHA-256 byte a byte) |
| Segurança (TLS, cofre, logs, token) | `test_seguranca_certificados.py::*`, `test_integracoes_api.py::test_api_token` |

## Teste de produção (aceitação real)

Exige CNPJ autorizado e uma chave real já conhecida, separadamente para cada modelo:

```bat
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
rem com MOXML_MODO=REAL no moxml.env
backend\.venv\Scripts\python -m moxml teste-real --empresa 1 --chave <CHAVE_NFE_55_CONHECIDA> --autorizado-por "Nome / cargo"
backend\.venv\Scripts\python -m moxml teste-real --empresa 1 --chave <CHAVE_NFCE_65_CONHECIDA> --autorizado-por "Nome / cargo"
```

O comando avalia os 10 critérios da seção 17 e grava `evidencias\teste_real_<cnpj>_<modelo>_<data>.json`. O critério 10 (execução automática) passa a OK depois de uma execução AGENDADA com sucesso.
