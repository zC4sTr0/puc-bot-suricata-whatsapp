"""Regressões contratuais offline: falhar fechado e nunca enviar por acidente."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suricata.dominio.publico import BRASILIA
from suricata.integracao.canvas import CanvasClient
from suricata.rodada import (
    Coleta,
    Evento,
    OutboxSincronizado,
    destinos_do_ambiente,
    entregar,
    executar,
)
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, CanvasFalso


class PonteQueNaoPodeSerChamada:
    def __init__(self) -> None:
        self.chamadas = 0

    def enviar_lote(self, *_args, **_kwargs):
        self.chamadas += 1
        raise AssertionError("ponte chamada durante simulação ou bloqueio")


class ColetaParcialCanvas:
    """Canvas local com uma oferta válida e outra falhando, sem rede."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def transporte(self, method, url, headers, timeout):
        self.urls.append(url)
        if "/assignments" in url:
            if "/courses/2/" in url:
                return 503, {}, []
            return 200, {}, []
        return 200, {}, [{"id": 1, "name": "Oferta OK"}, {"id": 2, "name": "Oferta falha"}]

    def cliente(self) -> CanvasClient:
        return CanvasClient(token="offline", transport=self.transporte)


class OperacaoFailClosedTests(unittest.TestCase):
    @staticmethod
    def agora() -> datetime:
        return datetime(2026, 9, 15, 13, 0, tzinfo=timezone.utc)

    def test_simulacao_com_evento_nunca_chama_ponte_nem_cria_outbox(self):
        ponte = PonteQueNaoPodeSerChamada()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            coleta = Coleta(atividades=[], ofertas=1, falhas=[], anuncios=[])
            codigo, relatorio = executar(
                objetos=objetos,
                canvas=CanvasFalso().cliente(),
                entrega_ligada=False,
                grupo_jid=JID,
                ponte=ponte,
                agora=self.agora,
                coleta_pronta=coleta,
            )
            self.assertEqual(codigo, 0)
            self.assertEqual(relatorio["modo"], "sombra")
            self.assertEqual(ponte.chamadas, 0)
            self.assertIsNone(objetos.ler("grupo/outbox.json").dados)

    def test_coleta_parcial_e_explicitamente_reportada(self):
        canvas = ColetaParcialCanvas()
        with tempfile.TemporaryDirectory() as tmp:
            codigo, relatorio = executar(
                objetos=ObjetosLocais(Path(tmp)),
                canvas=canvas.cliente(),
                entrega_ligada=False,
                grupo_jid=None,
                ponte=None,
                agora=self.agora,
            )
            self.assertEqual(codigo, 0)
            self.assertEqual(relatorio["estado"], "parcial")
            self.assertEqual(relatorio["ofertas"], 2)
            self.assertEqual(relatorio["ofertas_com_falha"], ["2"])

    def test_memoria_invalida_interrompe_antes_de_planejar_ou_enviar(self):
        ponte = PonteQueNaoPodeSerChamada()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            objetos.gravar("grupo/memoria.json", b"{ memoria quebrada", generation=None)
            codigo, relatorio = executar(
                objetos=objetos,
                canvas=CanvasFalso().cliente(),
                entrega_ligada=False,
                grupo_jid=None,
                ponte=ponte,
                agora=self.agora,
                coleta_pronta=Coleta([], 1, [], []),
            )
            self.assertEqual(codigo, 5)
            self.assertEqual(relatorio["estado"], "memoria_invalida")
            self.assertEqual(ponte.chamadas, 0)

    def test_outbox_invalido_interrompe_entrega_sem_chamar_ponte(self):
        ponte = PonteQueNaoPodeSerChamada()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            objetos.gravar("grupo/outbox.json", json.dumps([{"estado": "unknown"}]).encode(), generation=None)
            codigo, relatorio = executar(
                objetos=objetos,
                canvas=CanvasFalso().cliente(),
                entrega_ligada=True,
                grupo_jid=JID,
                ponte=ponte,
                agora=self.agora,
                coleta_pronta=Coleta([], 1, [], []),
            )
            self.assertEqual(codigo, 5)
            self.assertEqual(relatorio["estado"], "falha_armazenamento")
            self.assertEqual(ponte.chamadas, 0)

    def test_configuracao_de_destinos_rejeita_formas_ambigua_ou_inseguras(self):
        casos = [
            {"SURICATA_DESTINOS_JSON": "não-json"},
            {"SURICATA_DESTINOS_JSON": json.dumps({"id": "fora-da-lista"})},
            {"SURICATA_DESTINOS_JSON": json.dumps([{"id": "grupo", "jid": "duplicado@g.us"}])},
            {"SURICATA_DESTINOS_JSON": json.dumps([{"id": "../escape", "jid": "escape@g.us"}])},
            {"SURICATA_DESTINOS_JSON": json.dumps([{"id": "sem-jid"}])},
            {"SURICATA_DESTINOS_JSON": json.dumps([{"id": "horario", "jid": "x@g.us", "janela_brt": "25:99"}])},
            {"SURICATA_DESTINOS_JSON": "[]"},
        ]
        for ambiente in casos:
            with self.subTest(ambiente=ambiente):
                with self.assertRaises(ValueError):
                    destinos_do_ambiente(ambiente)

    def test_fronteira_21h_brt_bloqueia_ponte_no_minuto_exato(self):
        ponte = PonteQueNaoPodeSerChamada()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            fila = OutboxSincronizado(objetos, Path(tmp))
            evento = Evento("mudou", "grupo:mudou:limite", "mudança")
            momento = datetime(2026, 9, 15, 21, 0, tzinfo=BRASILIA)
            resumo = entregar(fila, ponte, JID, [evento], momento)
            self.assertEqual(resumo["pendentes_enviados"], 0)
            self.assertEqual(ponte.chamadas, 0)

    def test_contrato_documenta_janela_diaria_e_configuracao_atual(self):
        raiz = Path(__file__).resolve().parents[2]
        guia = (raiz / "docs" / "guia.md").read_text(encoding="utf-8")
        configuracao = (raiz / "docs" / "configuracao.md").read_text(encoding="utf-8")
        deploy = (raiz / "docs" / "deploy-gcp.md").read_text(encoding="utf-8")
        self.assertIn("07:00", guia)
        self.assertIn("SURICATA_DESTINOS_JSON", configuracao)
        self.assertIn("canário", deploy.lower())


if __name__ == "__main__":
    unittest.main()
