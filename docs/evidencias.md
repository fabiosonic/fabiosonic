# Evidências e rastreabilidade

## Fonte de referência

| Item | Valor |
| --- | --- |
| Vídeo | “LIVE: TIRE DÚVIDAS SOBRE O RCO DASH !” — https://www.youtube.com/live/xzTffvHW6h0 |
| Canal | Jimmy Carvalho |
| Sistema apresentado | RCO Dash (plataforma ligada a opções, carteira, conteúdo educacional e ferramentas de análise) |

### Como a inspeção foi feita e limitações

- **Acesso direto ao vídeo falhou** neste ambiente: `youtube.com` é bloqueado pela política de rede (HTTP 403 no proxy de saída; `WebFetch` retornou `EGRESS_BLOCKED`). Não foi possível assistir aos trechos, extrair quadros nem baixar a transcrição.
- Uma busca na web por “RCO Dash” não retornou material público adicional sobre o produto (apenas entrevistas sobre o autor).
- Portanto, **todas as evidências abaixo vêm da descrição/capítulos e de trechos da transcrição fornecidos no pedido do projeto**, e não de observação visual. Nenhum detalhe de interface, regra de cálculo, permissão ou integração do sistema original foi confirmado.
- Este MVP **não declara equivalência** com o RCO Dash. Usa identidade visual própria (“Opções Lab”) e conteúdo original; não reproduz logotipo, marca, aulas ou análises.

Legenda da coluna “Classificação”: **V** = funcionalidade verificada como *mencionada* na fonte; **D** = decisão de projeto deste MVP; **F** = funcionalidade futura/pendente.

## Tabela de evidências

| Funcionalidade | Fonte e timestamp | O que foi efetivamente mencionado | Limitações da evidência | Comportamento proposto no MVP | Classificação |
| --- | --- | --- | --- | --- | --- |
| Visão geral da plataforma (painel) | Capítulo 09:00 “overview da plataforma” (descrição) | Existência de uma visão geral da plataforma | Somente título de capítulo; conteúdo da tela não observado | Painel inicial com resumo da carteira, distribuição por ativo, últimas análises/operações, próximas lives, situação da sincronização e origem/data dos dados | V (tema) / D (conteúdo) |
| Autorização B3 / conexão da carteira | Capítulo 12:00 “autorização B3” (descrição) | Fluxo de autorização junto à B3 | Mecanismo, telas e escopo de dados desconhecidos | Conexão **demonstrativa** (sem senha, sem acesso real), estados desconectado/conectado/sincronizando/erro, adaptador `PositionsProvider` para integração oficial futura | V (tema) / D (implementação) |
| Posições consolidadas em D+1 pela B3 | Transcrição (sem timestamp preciso informado) | Posições consolidadas em D+1 pela B3 | Não se sabe como a data-base é exibida nem a frequência de atualização | Data-base = dia útil anterior (fins de semana; feriados pendentes), histórico de sincronizações | V (menção) / D |
| Curso | Capítulo 14:00 “curso” (descrição); transcrição menciona conteúdos educacionais | Existência de curso e conteúdo educacional | Estrutura (módulos, aulas, progresso) não observada | Cursos → módulos → aulas com progresso por usuário; conteúdo demonstrativo **original** | V (tema) / D |
| “Somos uma corretora?” | Capítulo 22:00 (descrição) | Discussão sobre a natureza da empresa | Conteúdo da resposta não disponível | Avisos permanentes: ambiente demonstrativo, nenhuma ordem real é enviada, conteúdo educacional e não recomendação | V (tema) / D |
| Operações prontas | Capítulo 33:00 (descrição); transcrição menciona recomendações | Operações/estratégias prontas disponibilizadas aos usuários | Formato, campos, regras de publicação não observados | Estratégias com pernas, premissas, riscos, métricas calculadas; rascunho/publicação/arquivamento; histórico; filtros | V (tema) / D |
| Boletas rápidas | Capítulo 48:00 (descrição) | Existência de “boletas rápidas” | Não se sabe se enviam ordens reais | **Simulação** de uma perna (compra/venda, CALL/PUT/ação) — nunca envia ordens | V (tema) / D |
| Boletas previsões | Capítulo 55:00 (descrição) | Existência de “boletas previsões” | Lógica de previsão desconhecida (pode envolver modelos/probabilidades) | Cenários de preço definidos pelo usuário, resultado no vencimento; **sem probabilidades** | V (tema) / D |
| Boleta clássica (multiperna) | Requisito do pedido do projeto | — | Não comprovada na fonte | Editor multiperna com payoff, equilíbrios, limites de ganho/perda | D |
| Simuladores | Transcrição (menção) | Existência de simuladores | Tipo de simulação não detalhado | Motor de payoff no vencimento com tabela de cenários e gráfico | V (menção) / D |
| Lives do curso | Capítulo 01:08:00 (descrição) | Lives associadas ao curso | Agenda/formato não observados | Agenda de lives e aulas ao vivo, vínculo opcional com curso, notificação de novos eventos | V (tema) / D |
| Tela mercado | Capítulo 01:17:00 (descrição) | Existência de uma tela de mercado | Dados, colunas e fonte não observados | Lista de ativos e grade de opções com pesquisa, filtros, ordenação e paginação; dados **demonstrativos** identificados | V (tema) / D |
| Opções diárias | Capítulo 01:35:00 (descrição) | Existência de “opções diárias” | Significado exato não confirmado (vencimentos diários? lista do dia?) | Interpretação: contratos agrupados por **data de vencimento**, com atalhos para próximos vencimentos e envio ao simulador | V (tema) / D (interpretação) |
| Pedidos de análises | Capítulo 01:40:00 (descrição) | Usuários pedem análises | Fluxo, prazos e responsáveis não observados | Pedido do usuário, histórico, resposta do analista, status aberto/em análise/respondido/encerrado, notificações | V (tema) / D |
| Recomendações | Transcrição (menção) | Recomendações | Natureza regulatória desconhecida | Tratadas como “operações prontas” educacionais, com aviso de que não são recomendação de investimento | V (menção) / D |
| Perfis (admin/analista/usuário), auditoria | Requisito do pedido do projeto | — | Não comprovado na fonte | Implementado conforme especificação | D |
| Dados de mercado reais, integração B3 oficial, envio de ordens, e-mail transacional | — | — | Exigem contratos/credenciais | Adaptadores prontos; implementações reais pendentes | F |

## Funcionalidades futuras (não implementadas)

Ver `docs/implementado-e-pendente.md`.
