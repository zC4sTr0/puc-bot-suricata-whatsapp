"""Contrato da dead-letter da rodada (``rodada/falhas.py``, contrato aditivo).

A dead-letter é um JSONL em ``falhas/falhas.jsonl`` no estado, com linhas
``{momento, event_id?, etapa, erro_curto}`` — SEM payload, token, JID ou
texto de mensagem. Escrever a dead-letter nunca derruba a rodada: erro de
escrita é silencioso para o resultado (a linha simplesmente não existe).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone

from suricata.rodada.falhas import NOME_FALHAS, registrar_falhas, sanitizar_erro
from suricata.storage.gcs import ObjetosLocais

AGORA = datetime(2026, 9, 18, 13, 0, tzinfo=timezone.utc)


class FalhasPurasTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="suricata-falhas-")
        self.objetos = ObjetosLocais(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _linhas(self) -> list[dict]:
        obj = self.objetos.ler(NOME_FALHAS)
        bruto = obj.dados.decode() if obj.dados else ""
        return [json.loads(linha) for linha in bruto.splitlines() if linha.strip()]

    def test_registra_linha_sanitizada_com_campos_allowlist(self):
        ok = registrar_falhas(self.objetos, [{"etapa": "entrega", "event_id": "grupo:novo:292184:1",
                                              "erro": "sessao=timeout", "texto": "MENSAGEM SECRETA",
                                              "message_id": "3EB0ABC", "grupo_jid": "1203@g.us"}], AGORA)
        self.assertTrue(ok)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(set(linhas[0]), {"momento", "event_id", "etapa", "erro_curto"})
        self.assertEqual(linhas[0]["erro_curto"], "sessao=timeout")

    def test_sanitizacao_remove_jid_token_e_url(self):
        erro = "falha no envio p/ 120363000000000000-1700000000@g.us token=abc123 https://wa.me/x"
        limpo = sanitizar_erro(erro)
        self.assertNotIn("@g.us", limpo)
        self.assertNotIn("abc123", limpo)
        self.assertNotIn("https://", limpo)
        self.assertIn("<jid>", limpo)

    def test_erro_curto_tem_limite_de_tamanho(self):
        self.assertLessEqual(len(sanitizar_erro("x" * 5000)), 200)

    def test_erro_de_escrita_nunca_derruba_nem_levanta(self):
        class ObjetoQuebrado:
            def ler(self, nome):
                raise RuntimeError("boom")

            def gravar(self, *a, **k):
                raise RuntimeError("boom")

        self.assertFalse(registrar_falhas(ObjetoQuebrado(), [{"etapa": "entrega", "erro": "x"}], AGORA))

    def test_duas_falhas_fazem_append_de_duas_linhas(self):
        registrar_falhas(self.objetos, [{"etapa": "entrega", "event_id": "a", "erro": "primeira"}], AGORA)
        registrar_falhas(self.objetos, [{"etapa": "entrega", "event_id": "b", "erro": "segunda"}], AGORA)
        linhas = self._linhas()
        self.assertEqual([linha["event_id"] for linha in linhas], ["a", "b"])
        self.assertTrue(all(linha["momento"] == AGORA.isoformat() for linha in linhas))

    def test_sem_falhas_nao_cria_arquivo(self):
        registrar_falhas(self.objetos, [], AGORA)
        self.assertIsNone(self.objetos.ler(NOME_FALHAS).dados)


class FalhasNaRodadaTests(unittest.TestCase):
    """Integração mínima: os pontos que falhavam em silêncio deixam rastro."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="suricata-falhas-rodada-")
        self.objetos = ObjetosLocais(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _linhas(self) -> list[dict]:
        obj = self.objetos.ler(NOME_FALHAS)
        bruto = obj.dados.decode() if obj.dados else ""
        return [json.loads(linha) for linha in bruto.splitlines() if linha.strip()]

    def _rodada(self, ponte, *, status_assignments: int = 200, objetos=None, canvas=None) -> tuple[int, dict]:
        from suricata.rodada import executar
        from suricata.tests._fakes import AGORA as RODADA_AGORA
        from suricata.tests._fakes import CanvasFalso

        canvas = canvas or CanvasFalso()
        canvas.status_assignments = status_assignments
        canvas.assignments["292184"] = [{
            "id": 9001, "name": "Quiz relâmpago", "points_possible": 3, "quiz_id": 555, "due_at": None,
            "unlock_at": "2026-09-14T13:00:00Z", "lock_at": "2026-09-14T13:30:00Z",
            "submission_types": ["online_quiz"],
            "html_url": "https://pucminas.instructure.com/courses/292184/assignments/9001",
        }]
        objetos = objetos or self.objetos
        memoria = {"linha_de_base_em": RODADA_AGORA.isoformat()}
        objetos.gravar("grupo/memoria.json", json.dumps(memoria).encode(), generation=None)
        # executar DEVOLVE (codigo, relatorio.json()); quem imprime é rodada.main.
        return executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                        grupo_jid="120363000000000000-1700000000@g.us", ponte=ponte,
                        agora=lambda: RODADA_AGORA)

    def test_falha_de_ponte_escreve_linha_sanitizada(self):
        class PonteQuebrada:
            def enviar_lote(self, grupo_jid, eventos):
                raise RuntimeError("falha p/ 120363000000000000-1700000000@g.us token=segredo9")

        codigo, relatorio = self._rodada(PonteQuebrada())
        self.assertEqual(codigo, 6)
        self.assertEqual(relatorio["entrega"]["sem_ack"], 1)
        linhas = self._linhas()
        self.assertEqual(len(linhas), 1)
        linha = linhas[0]
        self.assertEqual(set(linha), {"momento", "event_id", "etapa", "erro_curto"})
        self.assertEqual(linha["etapa"], "entrega")
        self.assertEqual(linha["event_id"], "grupo:novo:292184:9001")
        bruto = json.dumps(linha, ensure_ascii=False)
        self.assertNotIn("@g.us", bruto)
        self.assertNotIn("segredo9", bruto)
        self.assertNotIn("Quiz relâmpago", bruto)  # sem texto de mensagem

    def test_sucesso_nao_escreve_nada(self):
        from suricata.tests._fakes import PonteFalsa

        codigo, _ = self._rodada(PonteFalsa(ack=True))
        self.assertEqual(codigo, 0)
        self.assertEqual(self._linhas(), [])

    def test_coleta_parcial_registra_falha_da_oferta(self):
        from suricata.tests._fakes import CanvasFalso, PonteFalsa

        class CanvasParcial(CanvasFalso):
            # 289837 falha; o resto coleta normal → coleta PARCIAL (exit 0).
            def transporte(self, method, url, headers, timeout):
                if "/courses/289837/" in url:
                    return 500, {}, []
                return super().transporte(method, url, headers, timeout)

        codigo, relatorio = self._rodada(PonteFalsa(ack=True), canvas=CanvasParcial())
        self.assertEqual(codigo, 0)
        self.assertEqual(relatorio["estado"], "parcial")
        linhas = self._linhas()
        self.assertEqual([linha["etapa"] for linha in linhas], ["coleta"])
        self.assertIn("289837", linhas[0]["erro_curto"])
        self.assertEqual(len(linhas), 1)

    def test_erro_de_escrita_da_dead_letter_nao_afeta_a_rodada(self):
        class ObjetoFragil(ObjetosLocais):
            def gravar(self, nome, dados, *, generation, tipo="application/json"):
                if str(nome).startswith("falhas/"):
                    raise RuntimeError("disco cheio")
                return super().gravar(nome, dados, generation=generation, tipo=tipo)

        from suricata.tests._fakes import PonteFalsa

        frageis = ObjetoFragil(self._tmp.name)
        codigo, relatorio = self._rodada(PonteFalsa(ack=True), objetos=frageis)

        self.assertEqual(codigo, 0)
        self.assertEqual(relatorio["estado"], "concluida")
        self.assertIsNone(frageis.ler(NOME_FALHAS).dados)


if __name__ == "__main__":
    unittest.main()
