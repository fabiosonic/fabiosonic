"""Linha de comando do pipeline.

    python -m avatar_contabil.cli pautas           # 1-4: busca, tria, roteiriza e põe na fila
    python -m avatar_contabil.cli fila             # lista o que aguarda revisão
    python -m avatar_contabil.cli ver ID           # mostra o roteiro completo
    python -m avatar_contabil.cli revalidar ID     # reaplica as travas após editar o JSON
    python -m avatar_contabil.cli aprovar ID --revisor "Nome CRC"
    python -m avatar_contabil.cli rejeitar ID --motivo "..."
    python -m avatar_contabil.cli produzir         # 5-8: voz, avatar e montagem dos aprovados
    python -m avatar_contabil.cli publicar         # 9: publica os produzidos (respeita o limite diário)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import avatar, config, fila, montagem, pauta, publicar, roteiro, travas, voz
from .modelos import Roteiro


def cmd_pautas(cfg: dict, args) -> None:
    pautas = pauta.exemplo() if config.dry_run() else pauta.coletar(cfg)
    print(f"{len(pautas)} pautas novas.")
    escolhidas = roteiro.triar(cfg, pautas)
    pauta.marcar_vistas([p.id for p in pautas])
    for p, nota, motivo in escolhidas:
        r = roteiro.escrever(cfg, p)
        alertas = travas.validar_roteiro(cfg, r)
        item = fila.adicionar(p, r, nota, motivo, alertas)
        aviso = f"  ALERTAS: {'; '.join(alertas)}" if alertas else ""
        print(f"[{item['id']}] nota {nota} · {r.titulo}{aviso}")
    if escolhidas:
        print("\nRevise com `fila` e `ver ID`, depois `aprovar ID --revisor ...`.")


def cmd_fila(cfg: dict, args) -> None:
    itens = fila.listar(args.status)
    if not itens:
        print("Fila vazia.")
    for i in itens:
        print(f"[{i['id']}] {i['status']:<17} nota {i['nota']:>2} · {i['roteiro']['titulo']}")


def cmd_ver(cfg: dict, args) -> None:
    i = fila.carregar(args.id)
    r = i["roteiro"]
    print(f"{r['titulo']}\nStatus: {i['status']}\nFonte: {i['pauta']['link']}\n")
    print(f"NARRAÇÃO:\n{r['texto_narrado']}\n\nCTA (Instagram): {r['cta']}")
    print(f"\nBase legal: {', '.join(r['base_legal']) or '(nenhuma citada)'}")
    print("Conferir antes de aprovar:\n" + "\n".join(f"  - {p}" for p in r["pontos_a_verificar"]))
    if i["alertas_travas"]:
        print("ALERTAS DAS TRAVAS:\n" + "\n".join(f"  ! {a}" for a in i["alertas_travas"]))
    print(f"\nPara editar: {config.pasta('fila') / (i['id'] + '.json')}")


def cmd_revalidar(cfg: dict, args) -> None:
    i = fila.carregar(args.id)
    i["alertas_travas"] = travas.validar_roteiro(cfg, Roteiro(**i["roteiro"]))
    fila.mudar_status(i, i["status"], "roteiro revalidado")
    print("OK, sem alertas." if not i["alertas_travas"] else "Alertas: " + "; ".join(i["alertas_travas"]))


def cmd_aprovar(cfg: dict, args) -> None:
    fila.aprovar(args.id, args.revisor)
    print(f"{args.id} aprovado.")


def cmd_rejeitar(cfg: dict, args) -> None:
    fila.rejeitar(args.id, args.motivo)
    print(f"{args.id} rejeitado.")


def cmd_produzir(cfg: dict, args) -> None:
    for i in fila.listar(fila.APROVADO):
        r = Roteiro(**i["roteiro"])
        pasta = config.pasta(f"videos/{i['id']}")
        print(f"[{i['id']}] narração...")
        audio = voz.gerar(cfg, r.texto_narrado, pasta / "narracao.mp3")
        print(f"[{i['id']}] avatar...")
        video_avatar = avatar.gerar(cfg, audio, pasta / "avatar.mp4")
        print(f"[{i['id']}] montagem...")
        saidas = montagem.montar(cfg, video_avatar, r.texto_narrado, r.cta, pasta)
        i["arquivos"] = {k: str(v) for k, v in saidas.items()}
        fila.mudar_status(i, fila.PRODUZIDO, "vídeos montados")
        print(f"[{i['id']}] pronto: {', '.join(i['arquivos'].values())}")


def cmd_publicar(cfg: dict, args) -> None:
    opc = cfg["publicacao"]
    if not (opc["youtube"]["ativo"] or opc["instagram"]["ativo"]):
        print("Nenhuma rede ativa em publicacao (config.yaml). Os vídeos ficam em data/videos/ para postar à mão.")
        return
    for i in fila.listar(fila.PRODUZIDO):
        if not travas.pode_publicar(cfg):
            print(f"Limite diário de {opc['limite_diario']} vídeo(s) atingido. O restante fica para amanhã.")
            return
        if not i.get("revisor"):
            print(f"[{i['id']}] sem revisor registrado; pulando.")
            continue
        r = Roteiro(**i["roteiro"])
        destinos = {
            "youtube": (opc["youtube"]["ativo"], lambda: publicar.youtube(
                cfg, config.RAIZ / i["arquivos"]["youtube"], r.titulo, travas.legenda_final(cfg, r, False), r.hashtags)),
            "instagram": (opc["instagram"]["ativo"], lambda: publicar.instagram(
                cfg, config.RAIZ / i["arquivos"]["instagram"], travas.legenda_final(cfg, r, True))),
        }
        algum_ok = False
        for rede, (ativo, enviar) in destinos.items():
            if rede in i["publicacoes"] or not ativo:
                continue
            if config.dry_run():
                print(f"[{i['id']}] DRY_RUN: publicaria no {rede}.")
                continue
            try:
                url = enviar()
                i["publicacoes"][rede] = url
                travas.registrar(i["id"], rede, True, url)
                algum_ok = True
                print(f"[{i['id']}] {rede}: {url}")
            except Exception as e:  # registra e segue para a próxima rede
                travas.registrar(i["id"], rede, False, str(e))
                print(f"[{i['id']}] falha no {rede}: {e}", file=sys.stderr)
        if algum_ok:
            fila.mudar_status(i, fila.PUBLICADO, "publicado: " + json.dumps(i["publicacoes"], ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="avatar_contabil", description="Vídeos com avatar para escritório contábil")
    ap.add_argument("--config", help="caminho do config.yaml")
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("pautas")
    p = sub.add_parser("fila")
    p.add_argument("--status")
    for nome in ("ver", "revalidar"):
        sub.add_parser(nome).add_argument("id")
    p = sub.add_parser("aprovar")
    p.add_argument("id")
    p.add_argument("--revisor", required=True, help="nome e CRC do contador que revisou")
    p = sub.add_parser("rejeitar")
    p.add_argument("id")
    p.add_argument("--motivo", required=True)
    sub.add_parser("produzir")
    sub.add_parser("publicar")

    args = ap.parse_args(argv)
    cfg = config.carregar(args.config)
    if config.dry_run():
        print("(modo de teste: DRY_RUN=1, nenhuma API paga é chamada)\n")
    globals()[f"cmd_{args.comando}"](cfg, args)


if __name__ == "__main__":
    main()
