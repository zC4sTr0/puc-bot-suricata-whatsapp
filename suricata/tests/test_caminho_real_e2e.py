"""Caminho de produção de ponta a ponta (auditoria 2026-09-14).

Nasceu como armadilha: a suíte antiga ficava verde com o produto cego, porque
cada teste trocava uma costura por um double. Aqui só o transporte HTTP é falso;
o resto é o que o Cloud Run executa: ``python -m suricata --mode rodada`` →
``CanvasClient`` → ``rodada`` → armazenamento com CAS → relatório/exit code.

Não enfraqueça estas asserções para ficar verde. Ver
``docs/audits/suricata-auditoria-caminho-real-2026-09-14.md``.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import suricata.canvas as canvas
from suricata.__main__ import main

RAIZ = Path(__file__).resolve().parents[1]


def _quiz_sem_prazo(agora: datetime) -> dict:
    """Formato real (F04/F37): quiz sem ``due_at``, que o planner omite."""
    return {
        "id": 9001, "name": "Quiz relâmpago", "points_possible": 3, "quiz_id": 555, "due_at": None,
        "unlock_at": (agora + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lock_at": (agora + timedelta(hours=2, minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "submission_types": ["online_quiz"],
        "html_url": "https://pucminas.instructure.com/courses/292184/assignments/9001",
    }


class CaminhoRealTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.itens: list[dict] = []
        self.status = 200

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _transporte(self, method, url, headers, timeout):
        if "/assignments" in url:
            return self.status, {}, self.itens if "/courses/292184/" in url else []
        return 200, {}, [{"id": 292184, "name": "Computabilidade"}]

    def _rodar(self) -> tuple[int, dict]:
        ambiente = {"SURICATA_ESTADO_URI": self._tmp.name, "SURICATA_CANVAS_TOKEN": "falso",
                    "SURICATA_ENTREGA": "desligada"}
        saida = io.StringIO()
        with mock.patch.dict(os.environ, ambiente), \
                mock.patch.object(canvas, "_urllib_transport", self._transporte), \
                contextlib.redirect_stdout(saida):
            codigo = main(["--mode", "rodada"])
        return codigo, json.loads(saida.getvalue().strip().splitlines()[-1])

    def test_quiz_novo_gera_aviso_no_caminho_de_producao(self):
        """Medido 2026-09-14 no caminho antigo: 0 requisições, 'indisponivel', 0 avisos, exit 0."""
        self.assertEqual(self._rodar()[0], 0)  # linha de base
        self.itens = [_quiz_sem_prazo(datetime.now(timezone.utc))]
        codigo, relatorio = self._rodar()
        self.assertEqual(codigo, 0)
        self.assertEqual([e["tipo"] for e in relatorio["eventos"]], ["novo"], relatorio)

    def test_coleta_cega_nao_pode_sair_como_ok(self):
        self.status = 500
        codigo, relatorio = self._rodar()
        self.assertNotEqual(codigo, 0)
        self.assertEqual(relatorio["estado"], "coleta_indisponivel")

    def test_horario_do_aviso_em_brasilia(self):
        """Medido no caminho antigo: prazo 23:59 de Brasília virou 'Fecha: 16/09 02:59' (UTC)."""
        from suricata.publico import Atividade, texto_novo

        a = Atividade("292184", "Computabilidade", "1", "Quiz", "quiz", None, None,
                      datetime(2026, 9, 16, 2, 59, 59, tzinfo=timezone.utc), None, "")
        self.assertIn("ter 15/09 23:59", texto_novo(a))

    def test_producao_nao_depende_da_cli_gcloud_nem_de_lock_windows(self):
        """A imagem não tem ``gcloud``; o container é Linux e efêmero."""
        for modulo in ("rodada.py", "storage/gcs.py", "publico.py", "grupos.py"):
            fonte = (RAIZ / modulo).read_text(encoding="utf-8")
            self.assertNotIn("CreateMutexW", fonte, modulo)
            self.assertNotIn("storage.cas import SuricataSessionStorage", fonte, modulo)
        dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("tzdata", dockerfile)  # zoneinfo America/Sao_Paulo no container


if __name__ == "__main__":
    unittest.main()
