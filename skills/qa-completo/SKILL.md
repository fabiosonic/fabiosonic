---
name: qa-completo
description: Esteira completa e sequencial de qualidade para programas criados pelo Claude (ou por qualquer pessoa) — prepara o ambiente de testes, revisa o código atrás de bugs, faz auditoria de segurança/LGPD, cria e roda testes automatizados (com casos contábeis e fiscais reais quando o sistema for de contabilidade), executa o app de verdade, simplifica o código e entrega um relatório final com o que foi encontrado e corrigido. Use sempre que o usuário pedir para "testar o programa", "achar erros", "revisar o código", "ver se está funcionando", "fazer QA", "auditar o sistema", "rodar tudo", "conferir antes de entregar/publicar", ou disser que o Claude acabou de criar um programa e quer saber se está certo — mesmo que cite só uma das etapas (review, segurança, testes, rodar o app), porque as etapas dependem umas das outras.
---

# QA Completo — esteira sequencial de qualidade

Esta skill junta, em uma única passada ordenada, o trabalho de várias ferramentas:

| Etapa | Equivale a | Objetivo |
|---|---|---|
| 0 | `session-start-hook` | Ambiente capaz de rodar testes e lint |
| 1 | — | Entender o que o programa deve fazer |
| 2 | `/code-review` + QA Bug Hunter | Achar bugs de lógica |
| 3 | `/security-review` | Achar falhas de segurança e LGPD |
| 4 | code-review-harness | Criar e rodar testes que **provam** o comportamento |
| 5 | `/run` + qa-quest | Executar o app real e ver funcionando |
| 6 | `/simplify` | Limpar o código sem mudar o comportamento |
| 7 | — | Relatório final |

A ordem importa: não adianta simplificar código com bug (o bug muda de lugar), nem rodar o app antes de ter testes (você não sabe o que é "certo"). Por isso cada etapa só começa quando a anterior terminou, e qualquer correção feita numa etapa é revalidada pelos testes antes de seguir.

## Como executar cada etapa

Se a skill equivalente estiver disponível na sessão (`code-review`, `security-review`, `simplify`, `run`, `session-start-hook`), **invoque-a pela ferramenta Skill** — ela traz a receita mais atualizada. Se não estiver, execute a etapa você mesmo seguindo as instruções abaixo. Nos dois casos, registre o resultado da etapa para o relatório final.

Use uma lista de tarefas (TaskCreate/TodoWrite, se existir) com as 8 etapas, marcando cada uma ao concluir. Isso evita pular etapas em projetos longos.

### Etapa 0 — Preparar o ambiente

1. Identifique a stack: `package.json` (Node), `pyproject.toml`/`requirements.txt` (Python), `*.csproj` (C#/.NET), `pom.xml`/`build.gradle` (Java), `composer.json` (PHP), `go.mod`, arquivos `.html` soltos etc.
2. Instale dependências com a ferramenta do próprio projeto (`npm ci`, `pip install -r`, `dotnet restore`…).
3. Descubra os comandos de teste, lint e typecheck. Se não existirem, escolha o padrão da stack (pytest, vitest/jest, xUnit, JUnit, PHPUnit) e configure o mínimo.
4. Rode os testes existentes **antes** de mudar qualquer coisa e anote o resultado — é a linha de base. Teste que já falhava não é culpa sua, mas deve ir para o relatório.
5. Se o usuário usa Claude Code na web e quer isso automático em toda sessão, ofereça a skill `session-start-hook`.

### Etapa 1 — Entender a intenção

Antes de procurar erro, saiba o que é "certo". Leia README, comentários, nomes de funções e o histórico da conversa. Escreva em 3–6 linhas: o que o programa recebe, o que devolve, e as regras de negócio. Se uma regra de negócio crítica for ambígua (ex.: "arredonda ou trunca o imposto?"), pergunte ao usuário — chutar aqui contamina todas as etapas seguintes.

### Etapa 2 — Revisão de código (bugs)

Leia o código inteiro relevante (não só trechos) procurando:

- Lógica errada: condições invertidas, `<` vs `<=`, laço que pula o primeiro/último item, divisão por zero, `null`/`undefined`/`None` não tratado.
- Números: uso de `float` para dinheiro (use `Decimal`/centavos inteiros), arredondamento no lugar errado, soma de valores arredondados vs arredondar a soma.
- Datas: fuso horário, competência vs data de emissão, último dia do mês, ano bissexto.
- Entradas: arquivo vazio, encoding (UTF-8 vs Latin-1 em arquivos de banco/SPED), separador decimal vírgula vs ponto, CNPJ/CPF com ou sem máscara.
- Erros silenciados: `try/except` que engole exceção, retorno de valor padrão escondendo falha.
- Código morto, variáveis nunca usadas, funções duplicadas.

Para cada achado, registre: arquivo:linha, o problema, um cenário concreto que quebra, e a gravidade (crítico / alto / médio / baixo). Só registre o que você consegue justificar com um cenário — palpite vago gera ruído.

Corrija os críticos e altos já nesta etapa, com a menor mudança possível. Os demais vão para o relatório com a sugestão.

### Etapa 3 — Segurança e LGPD

Leia `references/seguranca-lgpd.md` e passe pelo checklist. Sistemas contábeis guardam CPF, CNPJ, salários, certificado digital A1 e senhas de portais — vazamento é problema legal (LGPD, sigilo profissional da NBC PG 01), não só técnico. Corrija o que for crítico; o resto vai para o relatório.

### Etapa 4 — Testes automatizados

Revisão lê o código; teste **prova** que ele funciona. Aqui está a maior parte do valor.

1. Escreva testes para cada regra de negócio da Etapa 1 e para cada bug corrigido na Etapa 2 (teste de regressão: deve falhar no código antigo e passar no novo).
2. Cubra: caso normal, limites (zero, valor máximo, faixa exata), entrada inválida, arquivo vazio.
3. **Se o sistema envolve contabilidade, folha ou tributos**, leia `references/testes-contabeis-fiscais.md` e inclua os casos aplicáveis. Use valores calculados à mão, não valores tirados do próprio código (senão o teste só confirma o bug).
4. Rode tudo. Teste falhando = investigue a causa raiz e corrija o código (ou o teste, se o teste estava errado — diga qual dos dois e por quê). Nunca apague nem desative teste para ficar verde.
5. Repita até ficar verde. Rode também lint e typecheck.

### Etapa 5 — Executar o app de verdade

Testes passam e mesmo assim o app pode não abrir. Execute:

- **CLI/script**: rode com uma entrada real de exemplo e confira a saída.
- **Servidor/API**: suba, faça requisições (`curl`) aos endpoints principais, confira status e corpo.
- **Web/HTML**: abra com Playwright (Chromium já instalado em ambientes remotos — não rode `playwright install`), navegue pelo fluxo principal, tire screenshot, verifique erros no console.
- **Desktop/planilha/macro**: rode o que for possível; o que não for, descreva o passo a passo para o usuário testar.

Anote o que viu funcionando e o que quebrou. Bug encontrado aqui → volte à Etapa 4: escreva o teste que o reproduz, corrija, rode de novo.

### Etapa 6 — Simplificar

Com testes verdes protegendo o comportamento, melhore o código: remova duplicação, funções gigantes, código morto, nomes confusos, cálculos repetidos. Mudança de qualidade, não de comportamento. Rode os testes depois de cada simplificação; se algo ficar vermelho, desfaça.

### Etapa 7 — Relatório final

Entregue exatamente nesta estrutura (em português):

```
# Relatório de QA — <nome do programa>

## Resumo
<2–4 linhas: estado geral, se está pronto para uso, riscos principais>

## Placar
| Etapa | Resultado |
|---|---|
| Ambiente | ... |
| Bugs encontrados / corrigidos | X / Y |
| Segurança / LGPD | ... |
| Testes | N criados, N passando, cobertura se disponível |
| Execução real | funcionou / falhou em ... |
| Simplificação | ... |

## Corrigido nesta rodada
- arquivo:linha — problema — o que foi feito

## Pendências (não corrigidas)
- [gravidade] arquivo:linha — problema — sugestão — por que não foi corrigido

## Como rodar os testes
<comando exato>
```

Seja honesto: se uma etapa não pôde ser feita (ex.: app desktop sem tela), diga isso no placar em vez de marcar como ok.

Se estiver em um repositório git, faça commit das correções e testes com mensagem descritiva (e push para o branch de trabalho, se houver um definido). Ofereça salvar o relatório como arquivo.

## Escopo e limites

- Corrija só o necessário para os achados — não reescreva o programa nem acrescente funcionalidades que ninguém pediu.
- Regra tributária muda com frequência. Quando um teste depender de alíquota, faixa ou prazo, cite a norma no comentário do teste e avise o usuário para conferir a vigência na competência analisada.
- Se o usuário pediu só uma etapa explicitamente ("só revisa a segurança"), faça aquela etapa bem feita e ofereça as demais em uma linha.
