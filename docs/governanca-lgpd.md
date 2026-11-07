# Governança, LGPD e riscos

## 1. Responsabilidade técnica

A escrituração, as declarações e os pareceres continuam sob a **responsabilidade do profissional
contábil habilitado** (Decreto-Lei 9.295/1946 e NBC PG 01). Os agentes são ferramentas de apoio. Por isso:

- toda entrega passa pela revisão quatro olhos (Controller) **e** pela aprovação humana no Paperclip;
- transmissão de declarações, emissão de guias definitivas, protocolos e assinatura são feitas só por humanos;
- o Paperclip guarda o histórico de quem aprovou o quê. Esse histórico serve de evidência de supervisão.

## 2. Matriz de autonomia

Definida na skill `padroes-mo` (seção 1) e aplicada a todos os agentes. Mudanças só com aprovação do Conselho.
O Paperclip está configurado com `requireBoardApprovalForNewAgents: true`: nenhum agente contrata outro sozinho.

## 3. LGPD (Lei 13.709/2018)

| Tema | Decisão |
|---|---|
| Papel do escritório | Operador dos dados dos clientes (e controlador dos próprios dados) |
| Base legal | Execução de contrato e cumprimento de obrigação legal/regulatória |
| Minimização | Tickets usam código do cliente; CPF mascarado; dados de saúde só no DP |
| Provedor de IA | Usar plano empresarial com **retenção zero ou sem treino com os dados**; registrar no contrato/termo |
| Transferência internacional | Os modelos podem processar dados fora do Brasil: informar em contrato com o cliente e na política de privacidade |
| Segurança | Disco criptografado, backup, acesso por usuário, segredos no cofre do Paperclip (nunca em texto) |
| Incidentes | Plano de resposta com prazo de comunicação à ANPD e aos titulares |
| Contratos com clientes | Incluir cláusula de tratamento de dados com uso de ferramentas de IA sob supervisão profissional |

## 4. O que nunca entra no Paperclip

- Certificado digital (A1/A3) e as respectivas senhas.
- Senhas do gov.br/e-CAC, códigos de acesso do Simples, tokens de bancos.
- Procurações eletrônicas em si (só o controle de vencimento).

## 5. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Erro de cálculo ou de norma desatualizada | Revisão quatro olhos, calendário revisado todo mês, citação obrigatória de fonte |
| "Alucinação" de norma | Regra "fonte não localizada — confirmar"; consultor revisado por humano |
| Estouro de custo | Orçamento por agente com pausa automática; scripts no lugar de prompts repetitivos |
| Vazamento de dados | Minimização, máquina dedicada, plano de IA sem retenção, sem segredos em tickets |
| Dependência do fornecedor | Pacote em formato aberto (agentcompanies/v1), versionado neste repositório |
| Mensagem errada ao cliente | Tudo é rascunho até liberação do Conselho por categoria |
