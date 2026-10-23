"""Inicia o Studio Contábil:  python -m studio  [--porta 8000] [--publico]"""
import argparse

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="studio")
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--publico", action="store_true", help="aceita conexões de outros computadores da rede")
    args = ap.parse_args()
    host = "0.0.0.0" if args.publico else "127.0.0.1"
    print(f"Studio Contábil em http://{'localhost' if host == '127.0.0.1' else host}:{args.porta}")
    uvicorn.run("studio.app:app", host=host, port=args.porta)


if __name__ == "__main__":
    main()
