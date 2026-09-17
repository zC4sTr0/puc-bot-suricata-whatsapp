import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suricata.application import SentinelaApplication
from suricata.delivery import DeliveryOrchestrator
from suricata.estado import EstadoLocal
from suricata.outbox import Outbox


NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)


class FakeCanvas:
    def __init__(self, items, status=200, planner_status=200):
        self.items = items
        self.status = status
        self.planner_status = planner_status

    def planner_publico(self):
        return {"status": self.planner_status, "items": []}

    def assignments_publicos(self, oferta):
        return {"status": self.status, "items": self.items if self.status == 200 else []}


class FakeDelivery:
    def __init__(self, result=None, order=None):
        self.result = result if result is not None else [{"status": "sent"}]
        self.order = order if order is not None else []
        self.calls = []

    def enviar_lote(self, eventos):
        self.order.append("delivery")
        self.calls.append(eventos)
        event_id = eventos[0]["event_id"] if eventos else ""
        result = self.result[min(len(self.calls) - 1, len(self.result) - 1)]
        return [{"event_id": event_id, **result}] if eventos else []


class ApplicationStateIntegrationTests(unittest.TestCase):
    def event(self, **overrides):
        value = {
            "id": 7,
            "course_id": "A",
            "name": "Quiz de integração",
            "quiz_id": 8,
            "unlock_at": "2026-09-14T12:10:00Z",
            "due_at": None,
            "lock_at": None,
        }
        value.update(overrides)
        return value

    def test_shadow_default_nao_cria_arquivos_de_estado(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            SentinelaApplication(FakeCanvas([self.event()]), clock=lambda: NOW).run(["A"])
            self.assertEqual(list(Path(directory).rglob("*")), [])
            self.assertEqual(state.ler_heartbeat(), {})

    def test_writer_explicito_persiste_heartbeat_memoria_diario_e_notifica(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            notifications = []
            report = SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state, notifier=notifications.append,
            ).run(["A"])

            self.assertEqual(report["estado"], "concluida")
            self.assertEqual(len(notifications), 1)
            self.assertEqual(state.ler_heartbeat()["sentinela_ok_em"], NOW.isoformat())
            memory = state.ler_memoria_grupo()
            self.assertEqual(memory["linha_de_base_em"], NOW.isoformat())
            self.assertEqual(len(memory["anuncios_vistos"]), 1)
            diary = (Path(directory) / "grupo" / "diario.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(diary), 1)
            record = json.loads(diary[0])
            self.assertEqual(record["eventos"], 1)
            self.assertEqual(record["avisos"], 1)
            self.assertEqual(record["coleta"], "concluida")

    def test_persistencia_e_notificacao_respeitam_ordem_do_contrato(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            order = []

            original_heartbeat = state.atualizar_heartbeat
            state.atualizar_heartbeat = lambda **kwargs: (
                order.append("heartbeat"), original_heartbeat(**kwargs)
            )[1]
            original_memory = state.registrar_memoria_grupo
            state.registrar_memoria_grupo = lambda value: (
                order.append("memory"), original_memory(value)
            )[1]
            original_dedup = state.registrar_dedup
            state.registrar_dedup = lambda value: (
                order.append("dedup"), original_dedup(value)
            )[1]
            original_diary = state.registrar_diario
            state.registrar_diario = lambda value: (
                order.append("diary"), original_diary(value)
            )[1]

            SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state, notifier=lambda _: order.append("notify"),
            ).run(["A"])

            self.assertEqual(order, ["heartbeat", "memory", "dedup", "diary", "notify"])

    def test_dedup_ocorre_antes_da_notificacao_publica(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            order = []

            original = state.registrar_dedup
            def record_then(*args, **kwargs):
                order.append("dedup")
                return original(*args, **kwargs)
            state.registrar_dedup = record_then

            def notify(_message):
                order.append("notify")

            SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state, notifier=notify,
            ).run(["A"])
            self.assertEqual(order, ["dedup", "notify"])

            SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state, notifier=notify,
            ).run(["A"])
            self.assertEqual(order, ["dedup", "notify", "dedup"])

    def test_falha_nao_atualiza_heartbeat_saudavel(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state,
            ).run(["A"])
            before = state.ler_heartbeat()

            report = SentinelaApplication(
                FakeCanvas([], status=500, planner_status=500), clock=lambda: NOW.replace(hour=13),
                state_writer=state,
            ).run(["A"])
            self.assertEqual(report["estado"], "indisponivel")
            self.assertEqual(state.ler_heartbeat(), before)

    def test_delivery_injetado_exige_opt_in_explicito(self):
        delivery = FakeDelivery()
        report = SentinelaApplication(
            FakeCanvas([self.event()]), clock=lambda: NOW, delivery=delivery,
            delivery_enabled=False,
        ).run(["A"])

        self.assertEqual(delivery.calls, [])
        self.assertFalse(report["entrega"]["chamado"])
        self.assertEqual(report["entrega"]["status"], [])

    def test_delivery_ocorre_depois_da_persistencia_e_status_e_sanitizado(self):
        with tempfile.TemporaryDirectory() as directory:
            state = EstadoLocal(directory)
            order = []
            original_diary = state.registrar_diario
            state.registrar_diario = lambda value: (
                order.append("diary"), original_diary(value)
            )[1]
            delivery = FakeDelivery(
                result=[{"status": "sent", "erro": "token=nao deve aparecer"}], order=order
            )
            report = SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                state_writer=state, delivery=delivery,
            ).run(["A"])

            self.assertEqual(order, ["diary", "delivery"])
            self.assertEqual(report["delivery"], report["entrega"])
            self.assertEqual(report["entrega"]["status"], [{
                "event_id": "canvas:pucminas:course:A:assignment:7", "status": "sent",
            }])
            self.assertNotIn("token", json.dumps(report))

    def test_delivery_pending_e_retentado_na_rodada_seguinte(self):
        delivery = FakeDelivery(result=[{"status": "pending"}, {"status": "sent"}])
        app = SentinelaApplication(
            FakeCanvas([self.event()]), clock=lambda: NOW, delivery=delivery,
        )
        first = app.run(["A"])
        second = app.run(["A"])
        self.assertEqual(first["entrega"]["status"][0]["status"], "pending")
        self.assertEqual(second["entrega"]["status"][0]["status"], "sent")
        self.assertEqual(len(delivery.calls), 2)

    def test_application_aceita_orquestrador_duravel_com_metodo_deliver(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = DeliveryOrchestrator(
                Outbox(Path(directory) / "outbox.json"), "grupo@g.us",
                lambda _grupo, eventos: {"sessao": "ok", "resultados": [
                    {"event_id": item["event_id"], "message_id": item["message_id"],
                     "ack": True, "status": 2}
                    for item in eventos
                ]},
                clock=lambda: NOW,
            )
            report = SentinelaApplication(
                FakeCanvas([self.event()]), clock=lambda: NOW,
                delivery=orchestrator,
            ).run(["A"])
            self.assertEqual(report["entrega"]["status"][0]["status"], "sent")


if __name__ == "__main__":
    unittest.main()
