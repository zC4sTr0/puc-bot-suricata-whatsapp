"""Biblioteca de fakes/doubles da rodada (test doubles compartilhados).

Este módulo NÃO é um arquivo de teste — o nome sem prefixo ``test_`` faz o
pytest ignorá-lo na coleta. Ele concentra os doubles e helpers que a suíte
compartilha (``JID``, ``AGORA``, ``iso``, ``CanvasFalso``, ``PonteFalsa`` e
``quiz``). ``test_rodada.py`` importa e re-exporta esses símbolos para manter
a compatibilidade dos importadores existentes
(``from suricata.tests.test_rodada import ...``); novos testes podem importar
direto daqui.
"""
from __future__ import annotations

from datetime import datetime, timezone

from suricata.integracao.canvas import CanvasClient

JID = "120363000000000000-1700000000@g.us"
AGORA = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)  # 09:00 em Brasília


def iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class CanvasFalso:
    def __init__(self) -> None:
        self.cursos = [{"id": 292184, "name": "Computabilidade"}, {"id": 289837, "name": "Mentoria"},
                       {"id": 104959, "name": "Coordenação"}]
        self.assignments: dict[str, list] = {"292184": []}
        self.status_cursos = 200
        self.status_assignments = 200
        self.status_anuncios = 200
        self.anuncios: list[dict] = []
        self.urls: list[str] = []

    def transporte(self, method, url, headers, timeout):
        self.urls.append(url)
        if "/announcements" in url:
            return self.status_anuncios, {}, self.anuncios
        if "/assignments" in url:
            curso = url.split("/courses/")[1].split("/")[0]
            return self.status_assignments, {}, self.assignments.get(curso, [])
        return self.status_cursos, {}, self.cursos

    def cliente(self) -> CanvasClient:
        return CanvasClient(token="t", transport=self.transporte)


class PonteFalsa:
    def __init__(self, ack: bool = True) -> None:
        self.ack = ack
        self.lotes: list[list[dict]] = []

    def enviar_lote(self, grupo_jid, eventos):
        self.lotes.append(eventos)
        return {"sessao": "ok", "resultados": [
            {"event_id": e["event_id"], "message_id": e["message_id"], "ack": self.ack,
             "status": 2 if self.ack else None} for e in eventos]}


def quiz(i: int, *, abre: datetime | None, fecha: datetime | None, nome: str = "Quiz relâmpago") -> dict:
    return {"id": i, "name": nome, "points_possible": 3, "quiz_id": 900 + i,
            "unlock_at": iso(abre) if abre else None, "lock_at": iso(fecha) if fecha else None, "due_at": None,
            "html_url": f"https://canvas.example.test/courses/292184/assignments/{i}?fixture=synthetic"}
