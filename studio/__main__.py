"""Studio Contábil.

    python -m studio [--porta 8000] [--publico]   inicia o aplicativo web
    python -m studio rotina                       roda o piloto automático uma vez (para usar no cron)
"""
import argparse

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="studio")
    ap.add_argument("comando", nargs="?", choices=["servidor", "rotina"], default="servidor")
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--publico", action="store_true", help="aceita conexões de outros computadores da rede")
    args = ap.parse_args()

    if args.comando == "rotina":
        from . import automacao

        criados = automacao.gerar_automatico()
        publicados = automacao.publicar_vencidos()
        for perfil, n in criados.items():
            print(f"{perfil}: {n} conteúdo(s) criado(s) e enviado(s) para revisão")
        print(f"{publicados} publicação(ões) feita(s) no Instagram")
        return

    host = "0.0.0.0" if args.publico else "127.0.0.1"
    print(f"Studio Contábil em http://{'localhost' if host == '127.0.0.1' else host}:{args.porta}")
    uvicorn.run("studio.app:app", host=host, port=args.porta)


if __name__ == "__main__":
    main()
