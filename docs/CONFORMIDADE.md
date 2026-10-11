# Conformidade: CFC, LGPD e plataformas

Este documento explica **o que o sistema faz para proteger o escritório** e **o que continua sendo responsabilidade do responsável técnico**. Ele não é parecer jurídico. Confirme a vigência das normas nos sites oficiais antes de mudar as regras.

## Normas profissionais (CFC)

| Exigência | Fonte | Como o sistema aplica |
| --- | --- | --- |
| Identificação profissional nas peças | NBC PG 01, item 4(r); orientação do CFC sobre assinatura | Assinatura automática com nome, CNPJ, CRC da organização e responsável técnico. **Sem esses dados, os envios de prospecção ficam bloqueados.** |
| Publicidade informativa, moderada e sem exageros | NBC PG 01, itens 11 a 15 | O Revisor barra superlativos ("o melhor", "líder", "nº 1") e diferenciais que não estão em "diferenciais comprovados". |
| Não depreciar colegas | NBC PG 01, itens 15 a 18 | Regra determinística e revisão pela IA barram críticas ao contador atual. Roteiro: "falamos da nossa oferta". |
| Honorários justificados e proposta escrita | NBC PG 01, itens 7 a 10 | A IA nunca cita preço; quem negocia é você. O lead só vira "Cliente" com evidência de contrato formalizado. |
| Contrato escrito | Res. CFC 1.590/2020 | Fora do escopo automático. Use o roteiro `conferencia-contrato.md` da skill. |

Políticas internas adotadas a partir da skill. São escolhas do escritório, não proibições universais:
- sem promessa de economia tributária ou de resultado garantido;
- sem urgência ou escassez artificiais;
- sem usar o medo de multa ou fiscalização como gancho;
- sem diagnóstico tributário sem contratação.

## LGPD

| Ponto | Como o sistema trata |
| --- | --- |
| **Origem e finalidade** de cada dado | Todo contato guarda a origem (ex.: "QSA via BrasilAPI", "Site www…", "Formulário do site com consentimento") e a finalidade (`prospeccao_comercial_b2b`). |
| **Base legal** | B2B com dado público: legítimo interesse (art. 7º, IX). Formulário e WhatsApp receptivo: consentimento registrado. **Recomendação:** faça e guarde o teste de balanceamento (LIA), conforme o guia da ANPD. |
| **Direito de oposição** | Todo e-mail tem link de descadastro com um clique e cabeçalho `List-Unsubscribe`. "Parar", "sair" e "não quero receber" são detectados por regra, sem depender da IA. O bloqueio vale para todos os contatos da empresa. |
| **Minimização** | Mensagens usam só o primeiro nome e o papel do sócio. CPF nunca é usado; o Revisor barra menções. |
| **Dados enviados à IA** | Com "privacidade estrita", tarefas com dados pessoais só vão para provedores que não treinam com os dados ou para o Ollama local. |
| **Contador cadastral** | E-mail ou telefone que aparece em várias empresas, ou com cara de escritório contábil, é marcado e **não** recebe prospecção. Costuma ser o contador que abriu a empresa. |

**O que o sistema não faz, de propósito:** consultar CPF, comprar ou usar bases vazadas, raspar perfis pessoais (LinkedIn, Instagram) ou procurar telefone pessoal de sócios. Para conhecer melhor o sócio, o caminho legítimo é a conversa: o Atendente registra o que o próprio lead conta (número de funcionários, canais de venda, planos) e o Redator usa isso nas mensagens seguintes.

## WhatsApp (políticas da Meta)

- **API oficial:**
  - o primeiro contato iniciado pela empresa exige **modelo aprovado**;
  - texto livre só vale dentro de 24 horas após a última mensagem do lead.
  
  O sistema segue isso automaticamente.
- **Padrão recomendado (ligado):** só iniciar conversa no WhatsApp com quem autorizou ou já conversou. Mensagens frias geram denúncias, a nota de qualidade cai e o número é limitado ou banido.
- **Evolution API (não oficial):** viola os termos do WhatsApp. Se usar, faça isso em um número separado e com volumes baixos.

## Antes de ligar o modo automático

1. Preencha a identificação completa e os serviços reais.
2. Rode pelo menos duas semanas no modo **aprovação** e leia o que a IA escreve.
3. Configure SPF, DKIM e DMARC do domínio e comece com no máximo 20 e-mails por dia, aumentando aos poucos (veja `EMAIL.md`).
4. Registre o teste de legítimo interesse (LIA) e quem responde pelos dados no escritório.
