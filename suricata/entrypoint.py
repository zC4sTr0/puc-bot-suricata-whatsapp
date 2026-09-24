"""Entrypoint fail-closed do runtime somente leitura do Suricata."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

# "rodada" é o caminho de produção (Cloud Run); "shadow" é a probe local
# sem efeitos; "demo" é a probe funcional offline (fixtures congeladas).
_MODES = {"shadow", "demo", "rodada"}

_AJUDA = """uso: python -m suricata --mode MODO

modos:
  shadow        probe local sem efeitos (zero-config)
  demo          rodada offline com fixtures congeladas; entrega desligada
  rodada        caminho canônico de produção (configuração via ambiente)

variáveis de ambiente: veja .env.example e docs/interno/CONFIGURATION.md
matriz de validação local: veja CONTRIBUTING.md
"""


def _emit(record: Mapping[str, Any]) -> None:
    print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def _parse_args(argv: Sequence[str]) -> tuple[str | None, str | None]:
    mode: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg != "--mode" or i + 1 >= len(argv):
            return None, "argumentos inválidos (use --mode MODO; veja --help)"
        if mode is not None:
            return None, "argumentos inválidos (use --mode MODO; veja --help)"
        mode = argv[i + 1]
        i += 2
    if mode is None:
        return None, "modo ausente (veja --help)"
    if mode not in _MODES:
        return None, "modo inválido (veja --help)"
    return mode, None


def main(argv: Sequence[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    # Windows com saída redirecionada (Git Bash, pipes) cai em cp1252 e quebra no emoji.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if {"--help", "-h"} & set(argumentos):
        print(_AJUDA)
        return 0
    mode, error = _parse_args(argumentos)
    if error:
        _emit({"status": "error", "error": error})
        return 2
    if mode == "demo":
        from .demo import main as demo_main
        return demo_main()
    if mode == "rodada":
        from .rodada import main as rodada_main
        return rodada_main()
    _emit({"mode": "shadow", "status": "ok", "adapter": "none"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
