"""Composition root for the canonical ``rodada`` runtime.

Business rules remain in ``execucao``, ``coleta`` and the planning modules. This
module only translates process environment into concrete adapters and delegates
to the existing use-case functions.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from typing import Any


def run_from_environment(
    *,
    canvas_factory: Callable[[], Any],
    destinations_factory: Callable[[], Sequence[Any]],
    objects_factory: Callable[[str], Any],
    session_factory: Callable[[Any], Any],
    bridge_factory: Callable[[Any], Any],
    single_runner: Callable[..., tuple[int, Any]],
    multi_runner: Callable[..., tuple[int, Any]],
    print_fn: Callable[[str], Any] = print,
) -> int:
    """Build the production graph and run one rodada.

    Factories are explicit so composition can be exercised with local fakes;
    no business rule or transport contract belongs here.
    """
    uri = os.environ.get("SURICATA_ESTADO_URI", "")
    if not uri:
        print_fn(json.dumps({"estado": "erro", "erro": "SURICATA_ESTADO_URI ausente"}))
        return 5
    if not os.environ.get("SURICATA_CANVAS_TOKEN"):
        print_fn(json.dumps({"estado": "erro", "erro": "SURICATA_CANVAS_TOKEN ausente"}))
        return 3

    objetos = objects_factory(uri)
    entrega = os.environ.get("SURICATA_ENTREGA", "desligada") == "ligada"
    ponte = None
    if entrega:
        ponte = bridge_factory(session_factory(objetos))

    try:
        destinos = list(destinations_factory())
    except ValueError as exc:
        print_fn(json.dumps({"estado": "erro", "erro": str(exc)}, ensure_ascii=False))
        return 5

    canvas = canvas_factory()
    if len(destinos) == 1:
        codigo, relatorio = single_runner(
            objetos=objetos,
            canvas=canvas,
            entrega_ligada=entrega,
            grupo_jid=destinos[0].jid,
            ponte=ponte,
        )
        print_fn(json.dumps({**relatorio, "codigo": codigo}, ensure_ascii=False))
        return codigo

    codigo, relatorios = multi_runner(
        objetos=objetos,
        canvas=canvas,
        entrega_ligada=entrega,
        ponte=ponte,
        destinos=destinos,
    )
    print_fn(json.dumps({"relatorios": relatorios, "codigo": codigo}, ensure_ascii=False))
    return codigo


__all__ = ["run_from_environment"]
