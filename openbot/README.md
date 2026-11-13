# Equipe OpenBot — Moraes e Oliveira Contabilidade

Coworkers para o [OpenBot (CopilotKit)](https://github.com/CopilotKit/OpenBot).

| Arquivo | Papel |
|---|---|
| `agents/gestor-contabil-mo.yaml` | **Gestor M&O**: coordena tudo e delega |
| `agents/conferente-portal-mo.yaml` | Conferência de documentos do Portal M&O |
| `agents/conciliador-bancario-mo.yaml` | Conciliação bancária |
| `agents/analista-fiscal-mo.yaml` | Fiscal/tributário e Reforma Tributária |
| `agents/analista-dp-mo.yaml` | Departamento pessoal |
| `agents/analista-societario-mo.yaml` | Societário e legalização |
| `agents/marketing-contabil-mo.yaml` | Marketing com compliance CFC |

## Instalação
1. Copie a pasta `agents/` para o pacote de tenant do OpenBot (ao lado de `agents.yaml`).
2. Reinicie o servidor e confira se os 7 bots aparecem.
3. Em **Setup → Bots it can ask** do *Gestor M&O*, autorize os 6 especialistas
   (sem isso o Gestor não consegue delegar).
4. Limites de delegação (`.env`): `BOT_HANDOFF_MAX_DEPTH=1` e
   `BOT_HANDOFF_MAX_PER_RUN=3` (padrões). Aumente o segundo se o Gestor precisar
   acionar mais especialistas na mesma execução.
5. Conceda ferramentas mínimas: navegador apenas ao Conferente do Portal;
   Google Drive a todos; ative o modo *Extra vigilant* (aprovação antes de gravar).
6. Crie o usuário próprio do bot no Portal M&O e cadastre a credencial no OpenBot
   (criptografada por `KEY_ENCRYPTION_KEY`).

> O OpenBot está em versão 0.x/alpha: confira os nomes dos campos na
> documentação da versão instalada antes de subir.
