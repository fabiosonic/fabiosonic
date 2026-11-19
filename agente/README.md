# Agente coletor (lado do cliente)

Envia, sozinho e continuamente, os XMLs de NF-e/NFC-e que o ERP/PDV do cliente grava, para o
servidor do M&O XML Captador no escritório. **Sem CAPTCHA, sem login, sem intervenção** — o
emitente já possui o XML; o agente só o entrega ao escritório.

## Quando usar
- Quando as pastas de XML do cliente **não são acessíveis pela rede** do escritório (o caso comum:
  PDV na loja do cliente). Se a pasta já for acessível por rede, cadastre-a direto em
  **Configurações → Pastas monitoradas** no painel, sem precisar do agente.

## Instalação (no PC/servidor do cliente)
1. Copie a pasta `agente\` para o PC do cliente (ex.: `C:\MO-Agente`).
2. Execute `instalar-agente.bat`. Ele:
   - confere o Python 3 (o agente usa **só a biblioteca padrão**: nada a instalar);
   - cria `agente.ini` e abre para você preencher URL do servidor, token e pastas do ERP/PDV;
   - faz um ciclo de teste;
   - registra a tarefa agendada **"MO XML Agente Coletor"** (inicia com o Windows, roda sem console).

## Segurança
- O agente **só lê** as pastas; nunca altera ou apaga XML.
- O único segredo é o token do servidor, guardado em `agente.ini` com permissão restrita.
- Prefira HTTPS quando o servidor estiver fora da rede local. Em rede interna, `http://IP:8765`.

## Teste manual
```
py moxml_agente.py --uma-vez
```
