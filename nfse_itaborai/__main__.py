"""Linha de comando: python -m nfse_itaborai {conferir,emitir,cancelar,tela} ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import cliente, emissor
from .validacao import ErroValidacao


def _imprimir(resp: cliente.Resposta) -> int:
    for a in resp.alertas:
        print(f"ALERTA: {a}")
    if resp.sucesso:
        for n in resp.notas:
            print(f"NFS-e {n.numero_nfse} emitida | RPS {n.numero_rps} | verificação {n.codigo_verificacao}")
            if n.link:
                print(f"  {n.link}")
        if resp.situacao:
            print(f"Situação: {resp.situacao}")
    else:
        print("NÃO EMITIDA / NÃO PROCESSADA:")
        for e in resp.erros:
            print(f"  - {e}")
    print(f"Arquivos em: {resp.pasta}")
    return 0 if resp.sucesso else 1


def configurar() -> int:
    """Cria o .env na pasta do emissor, sem precisar editar arquivo à mão."""
    import getpass
    arq = emissor.RAIZ / ".env"
    atual: dict[str, str] = {}
    if arq.exists():
        for linha in arq.read_text(encoding="utf-8").splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                k, v = linha.split("=", 1)
                atual[k.strip()] = v.strip()
    padrao = {"ITABORAI_CNPJ": "", "ITABORAI_IM": "", "ITABORAI_SIMPLES": "S",
              "ITABORAI_AMBIENTE": "homologacao", "ITABORAI_CIENTE_IRREVERSIVEL": "NAO"} | atual

    def perguntar(chave: str, texto: str, oculto: bool = False) -> None:
        sugestao = padrao.get(chave, "")
        mostra = "(já preenchida)" if oculto and sugestao else sugestao
        entrada = (getpass.getpass if oculto else input)(f"{texto} [{mostra}]: ").strip()
        padrao[chave] = entrada or sugestao

    from . import config
    canal_atual = config.carregar()["emissao"].get("canal", "municipal") if (emissor.RAIZ / "dados" / "config.json").exists() else ""
    print(f"Configurando {arq}  (Enter mantém o valor entre colchetes)")
    print()
    print("Como a empresa emite a NFS-e?")
    print("  1 - Emissor Nacional (nfse.gov.br) - usa o certificado digital A1 da empresa")
    print("  2 - Webservice da Prefeitura de Itaboraí - usa a Chave Privada Webservice do portal da prefeitura")
    escolha = ""
    while escolha not in ("1", "2"):
        escolha = input(f"Opção [{'2' if canal_atual == 'municipal' else '1'}]: ").strip() or ("2" if canal_atual == "municipal" else "1")
    nacional = escolha == "1"
    perguntar("ITABORAI_CNPJ", "CNPJ do prestador")
    padrao["ITABORAI_CNPJ"] = "".join(ch for ch in padrao["ITABORAI_CNPJ"] if ch.isdigit())
    if len(padrao["ITABORAI_CNPJ"]) != 14:
        print("CNPJ inválido (precisa de 14 números): nada foi gravado.")
        return 2
    perguntar("ITABORAI_IM", "Inscrição municipal" + (" (se não tiver, deixe em branco)" if nacional else ""))
    municipio = ""
    if nacional:
        sugestao = config.carregar()["emissao"].get("municipio_emissor", "") if canal_atual == "nacional" else ""
        while len(municipio) != 7:
            municipio = "".join(ch for ch in (input(f"Código IBGE do município da empresa (7 números, ex.: 3304557 Rio de "
                                                    f"Janeiro; consulte em ibge.gov.br) [{sugestao}]: ").strip() or sugestao)
                                if ch.isdigit())
            if len(municipio) != 7:
                print("  O código do IBGE tem 7 números.")
        perguntar("ITABORAI_SIMPLES", "Optante do Simples Nacional? (S/N)")
    else:
        perguntar("ITABORAI_CHAVE", "Chave Privada Webservice (não aparece ao digitar/colar)", oculto=True)
        perguntar("ITABORAI_PROXIMO_RPS", "Próximo número de RPS")
        perguntar("ITABORAI_SIMPLES", "Optante do Simples Nacional? (S/N)")
        if not padrao.get("ITABORAI_CHAVE"):
            print("Chave não informada: nada foi gravado. (Se a empresa emite pelo nfse.gov.br, escolha a opção 1.)")
            return 2
        padrao.setdefault("ITABORAI_PROXIMO_LOTE", "1")
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text("".join(f"{k}={v}\n" for k, v in padrao.items() if v != "" or k == "ITABORAI_IM"), encoding="utf-8")
    emissao = {"canal": "nacional", "municipio_emissor": municipio} if nacional else {"canal": "municipal"}
    config.salvar({"emissao": emissao})
    print()
    print(f"OK: {arq} gravado.")
    if nacional:
        print("Próximo passo: na tela do sistema, em Configurações > Empresa emissora e credenciais, selecione o")
        print("certificado digital A1 (.pfx) da empresa e informe a senha. Ele assina as notas do Emissor Nacional.")
    print("Produção continua bloqueada até você ligar em Configurações (ou mudar ITABORAI_AMBIENTE=producao e")
    print("ITABORAI_CIENTE_IRREVERSIVEL=SIM nesse arquivo).")
    return 0


def importar_clientes(pasta: Path | None = None) -> int:
    """Importação completa pelos XML (IMPORTAR_CLIENTES.bat), com o resumo do que foi preenchido."""
    from . import importador, licenca
    if not licenca.liberado():
        print("Licença: " + licenca.situacao()["mensagem"])
        return 3
    res = importador.importar_tudo(pasta)
    if not res:
        print(f"Nenhum XML de NFS-e na pasta {importador.caixa()}.")
        return 1
    for r in res:
        print()
        print(f"== {r['nome'] or 'Prestador'} (CNPJ {r['cnpj']}) — {r['notas']} nota(s)")
        if r.get("erro"):
            print(f"   NÃO IMPORTADO: {r['erro']}")
            continue
        print(f"   Clientes: {r['clientes_novos']} novo(s), {r['clientes_total']} no cadastro"
              + (f", {r['clientes_com_servico']} ligado(s) ao serviço habitual" if r.get("clientes_com_servico") else ""))
        from . import empresas, servicos
        emp = next(e for e in empresas.listar() if e["cnpj"] == r["cnpj"])
        with emissor.usar_empresa(empresas.pasta(emp)):
            for s in servicos.listar():
                print(f"   Serviço{' PADRÃO' if s.get('padrao') else ''}: {s['nome']} — item {s['item_lista_servico']}, "
                      f"desdobro {s['codigo_desdobro']}, NBS {s['codigo_nbs'] or '-'}, cód. municipal "
                      f"{s.get('codigo_tributacao_municipio') or '-'}, ISS {s['aliquota_iss'] or '-'}%, carga {s['ibpt_percentual'] or '-'}%")
        for f in r.get("empresa_completada") or []:
            print(f"   Empresa: {f}")
        fiscais = [importador.NOMES_FISCAIS.get(k, k) for k in r.get("regra_geral") or []]
        if fiscais:
            print("   Regras fiscais do regime lidas das notas: " + ", ".join(fiscais))
        if r.get("regras_tomadores"):
            print(f"   {r['regras_tomadores']} tomador(es) com regra fiscal própria (retenções, ISS retido, órgão público)")
    print()
    print("Pronto. Confira em Configurações > Serviços e Regras fiscais antes de emitir em produção.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="nfse_itaborai", description="Emissor de NFS-e de Itaboraí/RJ via webservice")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("conferir", help="valida o RPS e mostra o XML, sem enviar")
    c.add_argument("arquivo", type=Path)

    e = sub.add_parser("emitir", help="envia o RPS e converte em NFS-e")
    e.add_argument("arquivo", type=Path)
    e.add_argument("--producao", action="store_true", help="envia em produção (padrão: homologação)")

    x = sub.add_parser("cancelar", help="cancela uma NFS-e")
    x.add_argument("numero_nfse")
    x.add_argument("justificativa")
    x.add_argument("--producao", action="store_true")

    sub.add_parser("configurar", help="cria/atualiza o arquivo .env perguntando os dados")

    ic = sub.add_parser("importar-clientes", help="importa dos XML de NFS-e: clientes, serviços, empresa e regras fiscais")
    ic.add_argument("pasta", type=Path, nargs="?", help="pasta com os XML (padrão: IMPORTAR XML)")

    sub.add_parser("robo", help="roda a rotina financeira (para o Agendador do Windows)")

    sub.add_parser("ja-aberto", help="se esta versão já estiver rodando, só abre o navegador (sai com 0)")

    t = sub.add_parser("tela", help="abre a tela de emissão no navegador (http://127.0.0.1:8765)")
    t.add_argument("--porta", type=int, default=8765)

    a = ap.parse_args(argv)
    from . import empresas
    empresas.aplicar_ativa()
    try:
        if a.cmd == "conferir":
            rps = emissor.rps_de_dict(json.loads(a.arquivo.read_text(encoding="utf-8")))
            xml, lote, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
            for al in alertas:
                print(f"ALERTA: {al}", file=sys.stderr)
            print(xml)
            print(f"\nOK: RPS {rps.numero} válido | serviços {rps.valor_servicos} | ISS {rps.valor_iss} "
                  f"| líquido {rps.valor_liquido}", file=sys.stderr)
            return 0
        if a.cmd == "emitir":
            rps = emissor.rps_de_dict(json.loads(a.arquivo.read_text(encoding="utf-8")))
            return _imprimir(emissor.emitir(rps, producao=a.producao))
        if a.cmd == "cancelar":
            return _imprimir(emissor.cancelar(a.numero_nfse, a.justificativa, producao=a.producao))
        if a.cmd == "configurar":
            return configurar()
        if a.cmd == "importar-clientes":
            return importar_clientes(a.pasta)
        if a.cmd == "robo":
            from . import automacao
            r = automacao.rodar_todas()
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
            return 0
        if a.cmd == "ja-aberto":
            from .tela import abrir_se_ja_aberto
            return 0 if abrir_se_ja_aberto() else 1
        if a.cmd == "tela":
            from .tela import servir
            servir(a.porta)
            return 0
    except ErroValidacao as ex:
        print("RPS com pendências (nada foi enviado):")
        for err in ex.erros:
            print(f"  - {err}")
        return 2
    except (emissor.ErroConfiguracao, ValueError, KeyError) as ex:
        print(f"Erro: {ex}")
        return 2
    except OSError as ex:
        print(f"Falha de comunicação com o webservice: {ex}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
