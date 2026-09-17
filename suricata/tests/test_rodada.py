"""Rodada de produção, ponta a ponta, sem rede (objetos locais + Canvas e ponte falsos)."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from suricata.canvas import CanvasClient
from suricata.message_id import message_id
from suricata.publico import classificar_tipo
from suricata.rodada import LEASE, MEMORIA, OUTBOX, Relatorio, executar
from suricata.storage.gcs import ObjetosLocais

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
            "html_url": f"https://pucminas.instructure.com/courses/292184/assignments/{i}?token=segredo"}


class RodadaTests(unittest.TestCase):
    def test_relatorio_json_tem_contrato_estavel_e_copia_defensiva(self):
        relatorio = Relatorio(
            iniciado_em="2026-09-14T12:00:00+00:00", modo="sombra", estado="parcial",
            ofertas=2, ofertas_com_falha=["anuncios"], atividades=3, linha_de_base=True,
            eventos=[{"tipo": "novo", "meta": {"origem": "canvas"}}],
            entrega={"estado": "pending", "detalhes": {"tentativas": 1}},
            agenda_manual={"estado": "ok"}, coleta={"ofertas": 2}, erro=None,
        )

        snapshot = relatorio.json()

        self.assertEqual(list(snapshot), [
            "iniciado_em", "modo", "estado", "ofertas", "ofertas_com_falha",
            "atividades", "linha_de_base", "eventos", "entrega", "agenda_manual",
            "coleta", "erro",
        ])
        self.assertEqual(snapshot, {
            "iniciado_em": "2026-09-14T12:00:00+00:00", "modo": "sombra", "estado": "parcial",
            "ofertas": 2, "ofertas_com_falha": ["anuncios"], "atividades": 3,
            "linha_de_base": True, "eventos": [{"tipo": "novo", "meta": {"origem": "canvas"}}],
            "entrega": {"estado": "pending", "detalhes": {"tentativas": 1}},
            "agenda_manual": {"estado": "ok"}, "coleta": {"ofertas": 2}, "erro": None,
        })

        snapshot["ofertas_com_falha"].append("coleta")
        snapshot["eventos"][0]["meta"]["origem"] = "mutado"
        snapshot["entrega"]["detalhes"]["tentativas"] = 99

        self.assertEqual(relatorio.ofertas_com_falha, ["anuncios"])
        self.assertEqual(relatorio.eventos[0]["meta"], {"origem": "canvas"})
        self.assertEqual(relatorio.entrega["detalhes"], {"tentativas": 1})

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.objetos = ObjetosLocais(Path(self._tmp.name))
        self.canvas = CanvasFalso()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def rodar(self, agora=AGORA, *, entrega=False, ponte=None):
        return executar(objetos=self.objetos, canvas=self.canvas.cliente(), entrega_ligada=entrega,
                        grupo_jid=JID, ponte=ponte, agora=lambda: agora)

    def outbox(self) -> dict[str, dict]:
        obj = self.objetos.ler(OUTBOX)
        return {r["event_id"]: r for r in json.loads(obj.dados)} if obj.dados else {}

    def test_linha_de_base_nao_anuncia_o_que_ja_existe(self):
        self.canvas.assignments["292184"] = [quiz(1, abre=AGORA + timedelta(days=2), fecha=AGORA + timedelta(days=2, minutes=15))]
        codigo, rel = self.rodar()
        self.assertEqual((codigo, rel["linha_de_base"], rel["eventos"]), (0, True, []))
        self.assertIsNotNone(self.objetos.ler(MEMORIA).dados)

    def test_sombra_nao_consume_item_antes_de_outbox_duravel(self):
        self.rodar()
        abre = AGORA + timedelta(hours=3)
        self.canvas.assignments["292184"] = [quiz(7, abre=abre, fecha=abre + timedelta(hours=1))]

        self.rodar(AGORA + timedelta(minutes=10))
        ponte = PonteFalsa()
        _, rel = self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=ponte)

        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["novo"])
        self.assertEqual(len(ponte.lotes), 1)

    def test_falha_de_publicacao_nao_consume_item(self):
        self.rodar()
        abre = AGORA + timedelta(hours=3)
        self.canvas.assignments["292184"] = [quiz(8, abre=abre, fecha=abre + timedelta(hours=1))]

        class Falha(PonteFalsa):
            def enviar_lote(self, grupo_jid, eventos):
                raise RuntimeError("ponte indisponível")

        self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=Falha())
        ponte = PonteFalsa()
        _, rel = self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=ponte)

        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["novo"])
        self.assertEqual(len(ponte.lotes), 1)

    def test_corte_21h_descartando_evento_de_hoje_nao_consume_item(self):
        self.rodar(AGORA - timedelta(days=1))
        inicio = AGORA.replace(hour=20, minute=0)
        self.canvas.assignments["292184"] = [quiz(9, abre=inicio, fecha=inicio + timedelta(minutes=15))]

        # Após o corte, o evento de hoje é descartado e não vira "visto".
        self.rodar(AGORA.replace(hour=21, minute=1), entrega=True, ponte=PonteFalsa())
        self.canvas.assignments["292184"] = []
        _, rel = self.rodar(AGORA.replace(hour=10, minute=10), entrega=True, ponte=PonteFalsa())
        self.assertEqual(rel["eventos"], [])

    def test_quiz_sem_prazo_novo_gera_aviso_em_brasilia_e_cobre_mentoria(self):
        self.rodar()
        abre = datetime(2026, 9, 14, 13, 10, tzinfo=timezone.utc)  # 10:10 Brasília
        self.canvas.assignments["292184"] = [quiz(7, abre=abre, fecha=abre + timedelta(minutes=15))]
        codigo, rel = self.rodar(AGORA + timedelta(minutes=10))
        self.assertEqual(codigo, 0)
        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["novo"])
        texto = rel["eventos"][0]["texto"]
        self.assertIn("🚨 🎓 *PUC Bot*: quiz hoje no Canvas!", texto)
        self.assertIn("📚 Computabilidade — Quiz relâmpago · 3 pts", texto)
        self.assertIn("🔓 seg 14/09 10:10 → 🔒 10:25 (15 min)", texto)
        self.assertNotIn("esteja", texto)  # D36: só constata, nunca manda
        self.assertNotIn("token", texto)  # query de URL nunca vai ao grupo
        self.assertTrue(any("/courses/289837/assignments" in url for url in self.canvas.urls))
        self.assertFalse(any("/104959/" in u for u in self.canvas.urls))
        self.assertEqual(self.objetos.ler(OUTBOX).dados, None)  # sombra não enfileira

    def test_entrega_confirmada_nao_repete(self):
        self.rodar()
        self.canvas.assignments["292184"] = [quiz(7, abre=AGORA + timedelta(hours=3), fecha=AGORA + timedelta(hours=4))]
        ponte = PonteFalsa()
        self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=ponte)
        self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=ponte)
        self.assertEqual(len(ponte.lotes), 1)
        (registro,) = self.outbox().values()
        self.assertEqual(registro["estado"], "sent")
        self.assertEqual(registro["message_id"], message_id(JID, registro["event_id"]))

    def test_sem_ack_reenvia_mesmo_message_id_ate_confirmar_e_nunca_unknown(self):
        self.rodar()
        self.canvas.assignments["292184"] = [quiz(7, abre=AGORA + timedelta(hours=3), fecha=AGORA + timedelta(hours=4))]
        falha = PonteFalsa(ack=False)
        self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=falha)
        self.assertEqual(next(iter(self.outbox().values()))["estado"], "pending")
        ok = PonteFalsa()
        self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=ok)
        self.assertEqual(falha.lotes[0][0]["message_id"], ok.lotes[0][0]["message_id"])
        self.assertEqual(falha.lotes[0][0]["texto"], ok.lotes[0][0]["texto"])
        self.assertEqual({r["estado"] for r in self.outbox().values()}, {"sent"})

    def test_crash_com_evento_in_flight_reenvia_na_rodada_seguinte(self):
        self.rodar()
        self.canvas.assignments["292184"] = [quiz(7, abre=AGORA + timedelta(hours=3), fecha=AGORA + timedelta(hours=4))]

        class Morre(PonteFalsa):
            def enviar_lote(self, grupo_jid, eventos):
                raise KeyboardInterrupt  # processo morto depois de publicar in_flight

        with self.assertRaises(KeyboardInterrupt):
            self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=Morre())
        self.assertEqual(next(iter(self.outbox().values()))["estado"], "in_flight")
        ponte = PonteFalsa()
        self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=ponte)
        self.assertEqual(len(ponte.lotes), 1)
        self.assertEqual({r["estado"] for r in self.outbox().values()}, {"sent"})

    def test_evento_expira_em_vez_de_sair_atrasado(self):
        self.rodar()
        abre = AGORA + timedelta(minutes=30)
        self.canvas.assignments["292184"] = [quiz(7, abre=abre, fecha=abre + timedelta(minutes=15))]
        self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=PonteFalsa(ack=False))
        self.canvas.assignments["292184"] = []
        self.rodar(AGORA + timedelta(hours=2), entrega=True, ponte=PonteFalsa())
        self.assertEqual({r["estado"] for r in self.outbox().values()}, {"expirado"})

    def test_coleta_cega_nunca_sai_com_zero(self):
        self.canvas.status_cursos = 401
        self.assertEqual(self.rodar()[0], 3)
        self.canvas.status_cursos, self.canvas.status_assignments = 200, 500
        codigo, rel = self.rodar()
        self.assertEqual((codigo, rel["estado"]), (3, "coleta_indisponivel"))

    def test_lease_ocupado_nao_toca_canvas_e_lease_abandonado_e_retomado(self):
        dados = json.dumps({"dono": "outro", "inicio": AGORA.isoformat()}).encode()
        self.objetos.gravar(LEASE, dados, generation=None)
        codigo, rel = self.rodar(AGORA + timedelta(minutes=2))
        self.assertEqual((codigo, rel["estado"], self.canvas.urls), (0, "lease_ocupado", []))
        # ObjetosLocais usa o relógio real em ``updated``: simule um lease velho no conteúdo e no metadado.
        gen = Path(self._tmp.name) / (LEASE + ".gen")
        meta = json.loads(gen.read_text())
        meta["updated"] = (AGORA - timedelta(minutes=10)).isoformat()
        gen.write_text(json.dumps(meta))
        self.assertEqual(self.rodar()[1]["estado"], "concluida")

    def test_lembrete_quinze_minutos_antes_uma_vez_e_nao_duplica_com_novo(self):
        """D32: lembrete antes de um quiz já conhecido abrir; uma vez só."""
        abre = AGORA + timedelta(hours=2)
        self.canvas.assignments["292184"] = [quiz(1, abre=abre, fecha=abre + timedelta(minutes=15))]
        self.rodar(entrega=True, ponte=PonteFalsa())  # linha de base durável
        self.assertEqual(self.rodar(abre - timedelta(minutes=30))[1]["eventos"], [])
        _, rel = self.rodar(abre - timedelta(minutes=12), entrega=True, ponte=PonteFalsa())
        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["lembrete"])
        self.assertIn("o quiz abre às 11:00 e fecha 11:15!", rel["eventos"][0]["texto"])
        self.assertEqual(self.rodar(abre - timedelta(minutes=2))[1]["eventos"], [])
        # quiz publicado já dentro da janela: só o aviso de publicação
        self.canvas.assignments["292184"].append(quiz(2, abre=abre, fecha=abre + timedelta(minutes=15)))
        _, rel = self.rodar(abre - timedelta(minutes=5))
        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["novo"])

    def test_mudanca_de_horario_so_avisa_quando_envolve_hoje_ou_amanha_sem_vespera(self):
        hoje = AGORA + timedelta(hours=3)          # 12:00 de hoje
        amanha = AGORA + timedelta(days=1)         # 09:00 de amanhã
        longe = AGORA + timedelta(days=40)
        self.canvas.assignments["292184"] = [quiz(1, abre=hoje, fecha=hoje + timedelta(minutes=15)),
                                             quiz(2, abre=amanha, fecha=amanha + timedelta(minutes=15)),
                                             quiz(3, abre=longe, fecha=longe + timedelta(minutes=15))]
        self.rodar(entrega=True, ponte=PonteFalsa())
        mover = lambda i, d: quiz(i, abre=d + timedelta(hours=1), fecha=d + timedelta(hours=1, minutes=15))  # noqa: E731
        self.canvas.assignments["292184"] = [mover(1, hoje), mover(2, amanha), mover(3, longe)]
        _, rel = self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=PonteFalsa())  # 09:10
        self.assertEqual([e["event_id"].split(":")[3] for e in rel["eventos"]], ["1", "2"])
        self.canvas.assignments["292184"] = [mover(1, hoje), mover(2, amanha + timedelta(hours=2)), mover(3, longe)]
        _, rel = self.rodar(AGORA + timedelta(hours=10), entrega=True, ponte=PonteFalsa())  # 19:00
        self.assertEqual([e["event_id"].split(":")[3] for e in rel["eventos"] if e["tipo"] == "mudou"], ["2"])


def _anuncio(i: int, titulo: str, mensagem: str = "", curso: int = 292184) -> dict:
    return {"id": i, "title": titulo, "message": f"<p>{mensagem}</p>", "context_code": f"course_{curso}",
            "posted_at": "2026-09-14T11:00:00Z", "html_url": f"https://pucminas.instructure.com/courses/{curso}/discussion_topics/{i}"}


class AnuncioRodadaTests(unittest.TestCase):
    setUp = RodadaTests.setUp
    tearDown = RodadaTests.tearDown
    rodar = RodadaTests.rodar

    def test_anuncio_de_prova_avisa_e_antigo_ou_irrelevante_nao(self):
        self.canvas.assignments["292184"] = [quiz(1, abre=None, fecha=AGORA + timedelta(days=9))]
        self.canvas.anuncios = [_anuncio(50, "Prova 1 remarcada", "já existia")]
        self.assertEqual(self.rodar(entrega=True, ponte=PonteFalsa())[1]["eventos"], [])  # linha de base também dos anúncios
        self.canvas.anuncios += [_anuncio(51, "Slides da aula 5", "material"),
                                 _anuncio(52, "Aviso", "Teremos <b>quiz</b> amanhã no início da aula")]
        _, rel = self.rodar(AGORA + timedelta(minutes=10), entrega=True, ponte=PonteFalsa())
        self.assertEqual([e["tipo"] for e in rel["eventos"]], ["anuncio"])
        texto = rel["eventos"][0]["texto"]
        self.assertTrue(texto.startswith("📣 🎓 *PUC Bot* repassa o recado de Computabilidade:"))
        self.assertIn("Teremos quiz amanhã", texto)
        self.assertNotIn("<b>", texto)
        self.assertEqual(self.rodar(AGORA + timedelta(minutes=20), entrega=True, ponte=PonteFalsa())[1]["eventos"], [])

    def test_falha_nos_anuncios_nao_bloqueia_quiz(self):
        self.rodar()
        self.canvas.status_anuncios = 500
        self.canvas.assignments["292184"] = [quiz(7, abre=AGORA + timedelta(hours=3), fecha=AGORA + timedelta(hours=4))]
        codigo, rel = self.rodar(AGORA + timedelta(minutes=10))
        self.assertEqual((codigo, rel["estado"], [e["tipo"] for e in rel["eventos"]]), (0, "parcial", ["novo"]))


class TextoTests(unittest.TestCase):
    def test_nome_curto_da_oferta_e_data_unica_quando_abre_e_fecha_juntos(self):
        from suricata.canvas import PublicAssignment
        from suricata.publico import atividade_de, texto_novo

        momento = "2026-11-26T13:30:00Z"
        a = atividade_de(PublicAssignment(id="1", name="Avaliação II", points_possible=25.0, unlock_at=momento,
                                          lock_at=momento, submission_types=("none",)),
                         "292185", "Fundamentos de Ciência de Dados - Campus Lourdes - PLU - Manhã - 2026/2")
        texto = texto_novo(a)
        self.assertEqual(texto.splitlines()[:3], ["🚨 🎓 *PUC Bot*: prova no Canvas!",
                                                  "📚 Fundamentos de Ciência de Dados — Avaliação II · 25 pts",
                                                  "📅 qui 26/11 10:30"])
        self.assertNotIn("Tudo indica", texto)  # D37


class PonteRealTests(unittest.TestCase):
    def test_todo_texto_da_rodada_passa_na_validacao_da_ponte_real(self):
        """Medido 2026-09-14 na nuvem: a ponte recusava '\\n' e nenhum aviso multilinha saía."""
        from suricata.bridge import BridgeError, WhatsAppBridge
        from suricata.publico import Atividade, texto_anuncio, texto_lembrete, texto_mudou, texto_novo

        abre = AGORA + timedelta(hours=1)
        a = Atividade("292184", "Computabilidade", "1", "Quiz", "quiz", abre, None, abre + timedelta(minutes=15), 3.0,
                      "https://pucminas.instructure.com/courses/292184/assignments/1")
        textos = [texto_novo(a), texto_lembrete(a), texto_mudou(a), texto_anuncio("C", "Prova", "linha", "")]
        eventos = [{"event_id": f"e{i}", "message_id": message_id(JID, f"e{i}"), "texto": t} for i, t in enumerate(textos)]
        self.assertTrue(all("\n" in t for t in textos))
        self.assertEqual(len(WhatsAppBridge._validar_entrada(JID, eventos)), 4)
        for ruim in ({"texto": "a\x00b"}, {"texto": "a\rb"}, {"event_id": "e\n1"}):
            evento = {**eventos[0], **ruim}
            evento["message_id"] = message_id(JID, evento["event_id"])
            with self.assertRaises(BridgeError):
                WhatsAppBridge._validar_entrada(JID, [evento])


class PonteCrashTests(unittest.TestCase):
    def test_crash_do_node_depois_do_ack_conta_como_entregue_e_grava_credenciais(self):
        """Medido 2026-09-14 na nuvem: acks=True/2 com exit=1 ('Node.js v22' no stderr)."""
        from unittest.mock import Mock
        from suricata.bridge import WhatsAppBridge
        from suricata.storage.cas import AuthSnapshot

        evento = {"event_id": "e1", "message_id": message_id(JID, "e1"), "texto": "a\nb"}

        class Sessao:
            gravado = None

            def read_auth(self):
                return AuthSnapshot({"creds.json": "{}"}, "7")

            def write_auth(self, value, *, expected_generation):
                Sessao.gravado = (value, expected_generation)

        def run(argv, input, **kw):
            auth_dir = Path(json.loads(input)["auth_dir"])
            (auth_dir / "creds.json").write_text('{"atualizado": true}', encoding="utf-8")
            saida = {"sessao": "ok", "resultados": [{**{k: evento[k] for k in ("event_id", "message_id")},
                                                     "ack": True, "status": 2, "timeout": False, "erro": None}]}
            return Mock(stdout=(json.dumps(saida) + "\n").encode(), stderr=b"Error\nNode.js v22.23.2", returncode=1)

        resposta = WhatsAppBridge(Sessao(), run=run).enviar_lote(JID, [evento])
        self.assertEqual(resposta["sessao"], "ok")
        self.assertEqual(Sessao.gravado, ({"creds.json": '{"atualizado": true}'}, "7"))

        def run_sem_ack(argv, input, **kw):
            saida = {"sessao": "ok", "resultados": [{**{k: evento[k] for k in ("event_id", "message_id")},
                                                     "ack": False, "status": None, "timeout": True, "erro": None}]}
            return Mock(stdout=json.dumps(saida).encode(), stderr=b"", returncode=1)

        from suricata.bridge import BridgeError
        with self.assertRaises(BridgeError):
            WhatsAppBridge(Sessao(), run=run_sem_ack).enviar_lote(JID, [evento])


class ClassificacaoTests(unittest.TestCase):
    def test_classificacao_usa_campos_do_canvas_e_nao_so_o_titulo(self):
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=True, submission_types=("external_tool",), titulo="Cinema em Dados"), "quiz")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False, submission_types=("none",), titulo="Prova 2"), "avaliacao")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False, submission_types=("online_upload",),
                                          titulo="Exercícios de Revisão - Prova Teórica 1"), "tarefa")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False, submission_types=("none",),
                                          titulo="Exercícios na plataforma Khan Academy"), "tarefa")


if __name__ == "__main__":
    unittest.main()


class VesperaTests(unittest.TestCase):
    """Mensagem das 18:00: agrupada por matéria; antecedência para matéria pesada."""

    def _atividade(self, titulo, tipo, abre=None, fecha=None, curso="Introdução à Computação", curso_id="292189",
                   pontos=None, estudo=""):
        from suricata.publico import Atividade

        return Atividade(curso_id, curso, titulo, titulo, tipo, abre, None, fecha, pontos, "", "canvas", estudo)

    @staticmethod
    def _brt(ano, mes, dia, h=0, m=0):
        from suricata.publico import BRASILIA

        return datetime(ano, mes, dia, h, m, tzinfo=BRASILIA)

    def test_so_sai_na_vespera_de_dia_de_aula_depois_das_18_e_uma_vez(self):
        from suricata.rodada import planejar_vespera

        prova = self._atividade("Prova 1", "avaliacao", self._brt(2026, 9, 16, 0), self._brt(2026, 9, 16, 23, 59))
        memoria: dict = {}
        self.assertIsNone(planejar_vespera([prova], memoria, self._brt(2026, 9, 15, 17, 50)))  # antes das 18h
        evento = planejar_vespera([prova], memoria, self._brt(2026, 9, 15, 18, 0))
        self.assertEqual(evento.event_id, "grupo:vespera:2026-09-16")
        self.assertIsNone(planejar_vespera([prova], memoria, self._brt(2026, 9, 15, 18, 10)))  # só uma vez
        prova_seg = self._atividade("Prova 1", "avaliacao", self._brt(2026, 9, 21, 8), self._brt(2026, 9, 21, 10))
        self.assertIsNone(planejar_vespera([prova_seg], {}, self._brt(2026, 9, 18, 18)))  # sexta → sábado
        self.assertIsNotNone(planejar_vespera([prova_seg], {}, self._brt(2026, 9, 20, 18)))  # domingo → segunda
        feriado = self._atividade("Quiz", "quiz", self._brt(2026, 9, 7, 10), self._brt(2026, 9, 7, 10, 15))
        self.assertIsNone(planejar_vespera([feriado], {}, self._brt(2026, 9, 6, 18)))  # 07/09 é feriado
        memoria = {}
        self.assertIsNone(planejar_vespera([], memoria, self._brt(2026, 9, 15, 18)))  # nada a dizer
        self.assertEqual(memoria["vesperas"], {"2026-09-16": "nada_a_dizer"})

    def test_agrupa_por_materia_sem_repetir_o_nome(self):
        from suricata.publico import texto_vespera

        amanha, agora = self._brt(2026, 9, 16).date(), self._brt(2026, 9, 15, 18)
        algo = dict(curso="Introdução a Algoritmos", curso_id="289812")
        atividades = [
            self._atividade("Big Data", "quiz", self._brt(2026, 9, 16, 10, 10), self._brt(2026, 9, 16, 10, 25), pontos=3.0),
            self._atividade("Lista 1", "tarefa", self._brt(2026, 9, 16), self._brt(2026, 9, 16, 23, 59), pontos=7.0),
            self._atividade("Prova 1", "avaliacao", self._brt(2026, 9, 16), self._brt(2026, 9, 16, 23, 59), pontos=25.0, **algo),
            self._atividade("Exercícios de Revisão", "tarefa", None, self._brt(2026, 9, 16, 23, 59), pontos=1.0, **algo),
            self._atividade("Lista 5", "tarefa", self._brt(2026, 9, 16, 12), self._brt(2026, 9, 23, 23, 59)),
            self._atividade("Prova 2", "avaliacao", None, self._brt(2026, 9, 18, 19), pontos=30.0),
            self._atividade("Antiga", "quiz", self._brt(2026, 9, 1), self._brt(2026, 9, 2)),
        ]
        texto = texto_vespera(atividades, amanha, agora)
        self.assertEqual(texto.split("\n"), [
            "🎓 *PUC Bot* · amanhã, qua 16/09",
            "",
            "📘 *Introdução à Computação*",
            "🎯 *Lista 1* · 7 pts",  # ordem cronológica: abre 00:00
            "   ↳ última entrega antes da Prova 2 (sex 18/09)",
            "⚡ *Quiz Big Data* · 3 pts, das 10:10 às 10:25",
            "",
            "📘 *Introdução a Algoritmos*",
            "📝 *Prova 1* · 25 pts",
            "📌 *Exercícios de Revisão* · 1 pt — entrega até 23:59",
            "",
            "🔭 *Próximos dias*",
            "• sex 18/09 — Prova 2 · 30 pts (Introdução à Computação)",
        ])

    def test_pontos_no_singular_e_com_virgula(self):
        from suricata.publico import pts

        self.assertEqual((pts(25.0), pts(1.0), pts(1.5), pts(None), pts(0.0)), (" · 25 pts", " · 1 pt", " · 1,5 pts", "", ""))


class MateriaPesadaTests(unittest.TestCase):
    """Computabilidade: lista avisada 2 dias antes (dá um dia pra fazer), prova 3 dias antes, com livro."""

    DESCRICOES = json.loads((Path(__file__).with_name("fixtures") / "descricoes_computabilidade.json").read_text(encoding="utf-8"))

    def _comp(self, titulo, tipo, fecha, estudo=""):
        from suricata.publico import Atividade

        return Atividade("292184", "Computabilidade", titulo, titulo, tipo, None, None, fecha, 1.5 if tipo == "tarefa" else 25.0,
                         "", "canvas", estudo)

    def test_linha_de_estudo_das_descricoes_reais(self):
        from suricata.publico import resumo_estudo

        self.assertEqual(resumo_estudo(self.DESCRICOES["Lista 5: Conjuntos"]), "Gersting · cap. 4 · pp. 205–227 · 14 exercícios")
        self.assertEqual(resumo_estudo(self.DESCRICOES["Lista 2: Lógica de predicatos"]), "Gersting · cap. 1 · pp. 19–52 · 29 exercícios")
        self.assertEqual(resumo_estudo(self.DESCRICOES["Lista 4: Revisão para a prova 1"]), "3 livros: Scheinerman, Stein, Rosen")
        self.assertEqual(resumo_estudo(self.DESCRICOES["Prova 2"]), "")  # sem padrão: não inventa

    def test_lista_avisada_dois_dias_antes_em_qualquer_dia_e_uma_vez(self):
        from suricata.publico import BRASILIA, resumo_estudo
        from suricata.rodada import planejar_vespera

        estudo = resumo_estudo(self.DESCRICOES["Lista 5: Conjuntos"])
        lista = self._comp("Lista 5: Conjuntos", "tarefa", datetime(2026, 9, 21, 23, 59, tzinfo=BRASILIA), estudo)
        memoria: dict = {}
        sabado = planejar_vespera([lista], memoria, datetime(2026, 9, 19, 18, tzinfo=BRASILIA))  # sábado, sem aula amanhã
        self.assertEqual(sabado.texto.split("\n"), [
            "🎓 *PUC Bot* · próximos dias",
            "",
            "📘 *Computabilidade*",
            "📌 *Lista 5: Conjuntos* · 1,5 pts — vence seg 21/09, em 2 dias",
            "   📖 Gersting · cap. 4 · pp. 205–227 · 14 exercícios",
        ])
        domingo = planejar_vespera([lista], memoria, datetime(2026, 9, 20, 18, tzinfo=BRASILIA)).texto
        self.assertIn("📌 *Lista 5: Conjuntos* · 1,5 pts — entrega até 23:59", domingo)
        self.assertIn("   📖 Gersting", domingo)
        self.assertNotIn("reserve", domingo)

    def test_prova_avisada_tres_dias_antes_junto_do_dia_seguinte(self):
        from suricata.publico import BRASILIA
        from suricata.rodada import planejar_vespera

        prova = self._comp("Prova 2", "avaliacao", datetime(2026, 10, 9, 23, 59, tzinfo=BRASILIA))
        outra = VesperaTests()._atividade("Lista 2", "tarefa", None, datetime(2026, 10, 7, 23, 59, tzinfo=BRASILIA))
        texto = planejar_vespera([prova, outra], {}, datetime(2026, 10, 6, 18, tzinfo=BRASILIA)).texto
        self.assertIn("🔭 *Próximos dias*", texto)
        self.assertIn("📝 *Prova 2* · 25 pts — sex 09/10, em 3 dias", texto)
        self.assertNotIn("• ", texto)  # a prova já apareceu com detalhe: não repete como item de "Próximos dias"


class AgendaManualTests(unittest.TestCase):
    """Datas anotadas em aula complementam o Canvas; o Canvas sempre vence."""

    def _canvas(self, titulo, tipo, dia_iso, assignment_id="1", curso_id="292189"):
        from suricata.publico import Atividade, BRASILIA

        d = datetime.fromisoformat(dia_iso).replace(tzinfo=BRASILIA)
        return Atividade(curso_id, "Introdução à Computação", assignment_id, titulo, tipo, d,
                         None, d + timedelta(hours=23, minutes=59), 30.0, "")

    def test_complementa_so_o_que_o_canvas_nao_cobre(self):
        from suricata.agenda_manual import complementar

        canvas = [self._canvas("Prova 1", "avaliacao", "2026-09-23", "1441228")]
        manual = [
            {"id": "ligado", "curso_id": "292189", "titulo": "Prova 1", "tipo": "avaliacao", "data": "2026-09-30", "canvas_assignment_id": "1441228"},
            {"id": "mesmo-dia", "curso_id": "292189", "titulo": "P1", "tipo": "avaliacao", "data": "2026-09-23"},
            {"id": "sem-data", "curso_id": "292189", "titulo": "ADA", "tipo": "avaliacao", "data": None},
            {"id": "sem-oferta", "curso_id": None, "titulo": "Prova 2", "tipo": "avaliacao", "data": "2026-10-10"},
            {"id": "ic-prova-2", "curso_id": "292189", "curso": "Introdução à Computação", "titulo": "Prova 2",
             "tipo": "avaliacao", "data": "2026-12-03", "pontos": 30},
        ]
        (extra,) = complementar(canvas, manual)
        self.assertEqual((extra.titulo, extra.fonte, extra.assignment_id), ("Prova 2", "caderno", "caderno:ic-prova-2"))

    def test_vespera_mostra_prova_do_caderno_amanha_e_chegando(self):
        from suricata.agenda_manual import complementar
        from suricata.publico import BRASILIA, texto_vespera

        manual = [{"id": "alg-prova-1", "curso_id": "289812", "curso": "Introdução a Algoritmos", "titulo": "Prova 1",
                   "tipo": "avaliacao", "data": "2026-09-16", "pontos": 25}]
        extras = complementar([], manual)
        amanha = texto_vespera(extras, datetime(2026, 9, 16).date(), datetime(2026, 9, 15, 18, tzinfo=BRASILIA))
        self.assertIn("📘 *Introdução a Algoritmos*", amanha)
        self.assertIn("📝 *Prova 1* · 25 pts", amanha)
        self.assertNotIn("marcada em aula", amanha)  # D37
        self.assertIsNone(texto_vespera(extras, datetime(2026, 9, 15).date(), datetime(2026, 9, 14, 18, tzinfo=BRASILIA)))
        entrega = self._canvas("Lista", "tarefa", "2026-09-15")
        chegando = texto_vespera([entrega, *extras], datetime(2026, 9, 15).date(), datetime(2026, 9, 14, 18, tzinfo=BRASILIA))
        self.assertIn("• qua 16/09 — Prova 1 · 25 pts (Introdução a Algoritmos)", chegando)

    def test_agenda_ausente_ou_invalida_nao_derruba_a_rodada(self):
        from suricata.agenda_manual import NOME, carregar

        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            self.assertEqual(carregar(objetos), ([], None))
            objetos.gravar(NOME, b"{nao json", generation=None)
            self.assertEqual(carregar(objetos), ([], "agenda inválida"))


class AvisoProvaMeioDiaTests(unittest.TestCase):
    """12:00 da véspera, só quando amanhã (dia de aula) tem prova ou quiz."""

    @staticmethod
    def _prova(dia_, tipo="avaliacao", titulo="Prova 1", fonte="canvas"):
        from suricata.publico import Atividade, BRASILIA

        inicio = datetime(2026, 9, dia_, tzinfo=BRASILIA)
        return Atividade("289812", "Introdução a Algoritmos", titulo, titulo, tipo, inicio, None,
                         inicio + timedelta(hours=23, minutes=59), 25.0, "", fonte)

    def test_so_meio_dia_so_com_prova_uma_vez(self):
        from suricata.publico import Atividade, BRASILIA
        from suricata.rodada import planejar_aviso_prova

        prova = self._prova(16, fonte="caderno")
        memoria: dict = {}
        self.assertIsNone(planejar_aviso_prova([prova], memoria, datetime(2026, 9, 15, 11, 50, tzinfo=BRASILIA)))
        evento = planejar_aviso_prova([prova], memoria, datetime(2026, 9, 15, 12, 0, tzinfo=BRASILIA))
        self.assertEqual(evento.event_id, "grupo:aviso-prova:2026-09-16")
        self.assertEqual(evento.texto.split("\n"), [
            "🎓 *PUC Bot* · amanhã (qua 16/09) tem prova",
            "",
            "📘 *Introdução a Algoritmos*",
            "📝 *Prova 1* · 25 pts"])
        self.assertIsNone(planejar_aviso_prova([prova], memoria, datetime(2026, 9, 15, 12, 10, tzinfo=BRASILIA)))
        tarefa = Atividade("1", "X", "L", "Lista", "tarefa", datetime(2026, 9, 16, tzinfo=BRASILIA), None,
                           datetime(2026, 9, 16, 23, 59, tzinfo=BRASILIA), 7.0, "")
        self.assertIsNone(planejar_aviso_prova([tarefa], {}, datetime(2026, 9, 15, 12, tzinfo=BRASILIA)))  # sem prova
        self.assertIsNone(planejar_aviso_prova([self._prova(21)], {}, datetime(2026, 9, 18, 12, tzinfo=BRASILIA)))  # sábado
        self.assertIsNone(planejar_aviso_prova([prova], {}, datetime(2026, 9, 15, 18, 5, tzinfo=BRASILIA)))  # 18h cobre
