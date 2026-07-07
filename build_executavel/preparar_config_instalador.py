"""Aplica senha de suporte do barquiboboriginal no config.ini do instalador."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config_app_os import ler_senha_suporte_build, preparar_config_instalador


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python preparar_config_instalador.py <caminho_config.ini>")
    destino = Path(sys.argv[1]).resolve()
    senha = ler_senha_suporte_build(RAIZ)
    preparar_config_instalador(destino, senha)
    print(f"config.ini preparado com hash da senha de suporte: {destino}")


if __name__ == "__main__":
    main()
