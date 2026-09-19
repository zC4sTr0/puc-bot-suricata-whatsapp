#!/usr/bin/env python3
"""Publica uma agenda Suricata validada no objeto ``agenda/manual.json`` do estado.

A entrada é fornecida por ``--arquivo``. O destino vem de
``SURICATA_ESTADO_URI`` (``gs://bucket`` ou caminho de diretório local);
não há bucket do Bot pessoal embutido.

Exemplo mínimo de arquivo de entrada::

    {
      "classe": "nota_pessoal",
      "itens": [
        {"id": "quiz-1", "tipo": "quiz", "titulo": "Quiz 1",
         "curso": "Matemática", "curso_id": "mat", "data": "2026-12-10"},
        {"id": "av-1", "tipo": "avaliacao", "titulo": "Prova final",
         "curso": "Física", "curso_id": "fis", "data": null}
      ]
    }

Modos:
- padrão: valida e publica (CAS, leitura de conferência após gravar);
- ``--validar``: valida e sai 0 sem publicar;
- ``--dry-run``: valida, imprime o que publicaria e sai 0 sem escrever nada.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

TIPOS = {"avaliacao", "quiz", "tarefa"}
OBJETO = "agenda/manual.json"


def validar(dados: dict) -> list[str]:
    erros: list[str] = []
    if dados.get("classe") != "nota_pessoal":
        erros.append("classe deve ser nota_pessoal")
    ids: set[object] = set()
    for n, item in enumerate(dados.get("itens") or []):
        rotulo = f"item {n}"
        item_id = item.get("id")
        if not item_id or item_id in ids:
            erros.append(f"{rotulo}: id ausente ou repetido")
        ids.add(item_id)
        if item.get("tipo") not in TIPOS:
            erros.append(f"{rotulo}: tipo inválido")
        if not item.get("titulo") or not item.get("curso"):
            erros.append(f"{rotulo}: titulo e curso são obrigatórios")
        if item.get("data") is not None:
            try:
                date.fromisoformat(item["data"])
            except (TypeError, ValueError):
                erros.append(f"{rotulo}: data deve ser AAAA-MM-DD ou null")
            if not item.get("curso_id"):
                erros.append(f"{rotulo}: item com data precisa de curso_id")
    return erros


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arquivo", type=Path, required=True)
    parser.add_argument("--validar", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="valida e imprime o que publicaria, sem escrever")
    args = parser.parse_args()
    bruto = args.arquivo.read_bytes()
    dados = json.loads(bruto)
    erros = validar(dados)
    print(f"agenda: {len(dados.get('itens') or [])} itens")
    if erros:
        print("\n".join("ERRO " + erro for erro in erros))
        return 2
    if args.validar:
        return 0
    if args.dry_run:
        for item in dados.get("itens") or []:
            print(f"publicaria {item.get('id')}: [{item.get('tipo')}] "
                  f"{item.get('titulo')} ({item.get('curso')}, data={item.get('data')})")
        print(f"dry-run: {OBJETO} não gravado")
        return 0
    destino = os.environ.get("SURICATA_ESTADO_URI")
    if not destino:
        print("ERRO SURICATA_ESTADO_URI ausente")
        return 2
    from suricata.storage.gcs import construir_objetos
    objetos = construir_objetos(destino)
    atual = objetos.ler(OBJETO)
    if atual.dados == bruto:
        print("agenda: já atualizada")
        return 0
    objetos.gravar(OBJETO, bruto, generation=atual.generation)
    conferido = objetos.ler(OBJETO)
    print(f"agenda: {'confere' if conferido.dados == bruto else 'READ-BACK DIVERGENTE'}")
    return 0 if conferido.dados == bruto else 1


if __name__ == "__main__":
    raise SystemExit(main())
