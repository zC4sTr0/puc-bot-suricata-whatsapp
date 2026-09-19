#!/usr/bin/env python
"""Bootstrap do Suricata: um comando, zero pip install.

Verifica Python >=3.11 e Node >=20 (aviso, não aborta), instala a dependência
Node da ponte (se aplicável), roda compileall, a suíte pytest e a probe shadow.
Exit 0 se o pytest passar; não-zero caso contrário.

Uso: python scripts/bootstrap.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NODE_MODULES = REPO / "suricata" / "whatsapp" / "node_modules"
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def titulo(texto: str) -> None:
    print(f"\n=== {texto} ===")


def _versao(cmd: list[str], padrao: str) -> tuple[int, ...] | None:
    """Roda o comando e extrai a versão major.minor (ex.: 'v22.11.0')."""
    try:
        saida = subprocess.run(
            cmd, capture_output=True, text=True, check=True, env=ENV
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    m = re.search(r"(\d+)\.(\d+)", saida or padrao)
    return (int(m.group(1)), int(m.group(2))) if m else None


def checar_python() -> None:
    titulo("Verificando Python")
    print(f"Python {sys.version.split()[0]} em {sys.executable}")
    if sys.version_info < (3, 11):
        print(
            "AVISO: Python < 3.11 (o pyproject exige >=3.11). "
            "A suíte pode passar mesmo assim, mas não é a versão suportada."
        )
    else:
        print("OK: Python >= 3.11.")


def checar_node() -> tuple[int, ...] | None:
    titulo("Verificando Node")
    if shutil.which("node") is None:
        print("AVISO: Node nao encontrado; testes .mjs da ponte ficam de fora.")
        return None
    versao = _versao(["node", "--version"], "")
    if versao is None:
        print("AVISO: nao consegui ler a versao do Node; seguindo mesmo assim.")
        return versao
    print(f"Node {versao[0]}.{versao[1]}")
    if versao < (20, 0):
        print("AVISO: Node < 20 (o pacote WhatsApp exige >=20).")
    else:
        print("OK: Node >= 20.")
    return versao


def instalar_node_deps() -> None:
    titulo("Dependencia Node da ponte (Baileys)")
    if shutil.which("npm") is None:
        print("AVISO: npm nao encontrado; pulei o npm ci.")
        return
    if NODE_MODULES.exists():
        print("node_modules ja existe; pulando npm ci (apague para reinstalar).")
        return
    print("npm ci --prefix suricata/whatsapp --ignore-scripts ...")
    try:
        subprocess.run(
            ["npm", "ci", "--prefix", "suricata/whatsapp", "--ignore-scripts"],
            cwd=REPO, env=ENV, check=True,
        )
        print("OK: dependencia Node instalada.")
    except subprocess.CalledProcessError as exc:
        print(
            f"AVISO: npm ci falhou (exit {exc.returncode}). A dependencia Git "
            "(libsignal) pode exigir rede. Veja docs/troubleshooting.md. "
            "Os testes .mjs ficam de fora ate resolver; o resto do bootstrap "
            "continua."
        )


def rodar(descricao: str, cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO, env=ENV)
    return proc.returncode


def main() -> int:
    print("Suricata bootstrap — std lib pura, zero pip install.")
    checar_python()
    tem_node = checar_node() is not None or shutil.which("node") is not None
    if tem_node:
        instalar_node_deps()
    else:
        print("(sem Node, a etapa de dependencia foi pulada)")

    titulo("Compileall")
    rc_compile = rodar("compileall", [sys.executable, "-m", "compileall", "-q", "suricata"])
    print("OK: todos os .py compilam." if rc_compile == 0
          else "FALHA: algum modulo nao compila.")

    titulo("Pytest")
    rc_pytest = rodar("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    print("OK: suíte Python passou." if rc_pytest == 0
          else "FALHA: suíte Python nao passou (rode o arquivo isolado se suspeitar de flaky).")

    titulo("Shadow")
    rc_shadow = rodar("shadow", [sys.executable, "-m", "suricata", "--mode", "shadow"])
    print("OK: probe shadow respondeu." if rc_shadow == 0
          else "FALHA: probe shadow nao respondeu.")

    titulo("Resumo")
    passou = rc_pytest == 0
    for nome, rc in [("compileall", rc_compile == 0),
                     ("pytest", rc_pytest == 0),
                     ("shadow", rc_shadow == 0)]:
        print(f"  {'[ok]' if rc else '[FALHA]'} {nome}")
    if sys.version_info < (3, 11):
        print("  [aviso] Python < 3.11 (nao aborta; pyproject exige >=3.11)")
    if not passou:
        print("\nBootstrap terminou com pytest VERMELHO: veja a saida acima.")
        return 1
    print(
        "\nTudo verde por aqui. Proximos passos:\n"
        "  - Continue com o guia: docs/guia.md\n"
        "  - Modo demo offline: python -m suricata --mode demo\n"
        "  - Para contribuir: CONTRIBUTING.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
