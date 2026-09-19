import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from suricata.storage.outbox import Outbox, OutboxError


def _hold_lock(path, ready):
    from suricata.storage.outbox import _lock_arquivo

    with _lock_arquivo(Path(path), timeout=5):
        ready.set()
        time.sleep(30)


def _add_event(path, start, event_id, now_iso):
    start.wait()
    Outbox(path).adicionar(
        {"event_id": f"e{event_id}", "message_id": f"m{event_id}", "texto": f"texto-e{event_id}",
         "expira_em": (datetime.fromisoformat(now_iso) + timedelta(hours=1)).isoformat()},
        agora=datetime.fromisoformat(now_iso),
    )


class OutboxConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.path = Path(self.root.name) / "outbox.json"
        self.now = datetime(2026, 9, 13, tzinfo=timezone.utc)

    def tearDown(self):
        self.root.cleanup()

    def evento(self, event_id, *, message_id=None):
        return {
            "event_id": event_id,
            "message_id": message_id or f"message-{event_id}",
            "texto": f"texto-{event_id}",
            "expira_em": (self.now + timedelta(hours=1)).isoformat(),
        }

    def test_quarenta_processos_independentes_em_vinte_rodadas_preservam_todos_os_eventos(self):
        worker = (
            "from suricata.storage.outbox import Outbox; "
            "from datetime import datetime, timedelta; "
            "import sys; "
            "path, event_id, now = sys.argv[1:4]; "
            "at = datetime.fromisoformat(now); "
            "Outbox(path).adicionar({'event_id': event_id, 'message_id': 'm-' + event_id, "
            "'texto': 'texto-' + event_id, 'expira_em': (at + timedelta(hours=1)).isoformat()}, agora=at)"
        )
        interpreters = []
        for candidate in (sys.executable, shutil.which("python")):
            if candidate and candidate not in interpreters:
                interpreters.append(candidate)
        repo_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")

        for round_id in range(20):
            round_path = self.path.with_name(f"outbox-{round_id}.json")
            processes = [
                subprocess.Popen(
                    [interpreter, "-c", worker, str(round_path), f"e{index}", self.now.isoformat()],
                    cwd=repo_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for index, interpreter in ((i, interpreters[i % len(interpreters)]) for i in range(40))
            ]
            results = [process.communicate(timeout=60) for process in processes]
            failures = [
                (process.returncode, stdout, stderr)
                for process, (stdout, stderr) in zip(processes, results, strict=True)
                if process.returncode != 0
            ]
            self.assertEqual(failures, [], f"falhas na rodada {round_id}: {failures[:2]}")
            self.assertEqual(len(Outbox(round_path).pendentes()), 40, f"rodada {round_id}")

    def test_timeout_de_lock_e_expresso_como_erro_de_outbox(self):
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Event()
        holder = ctx.Process(target=_hold_lock, args=(str(self.path.with_name(".outbox.json.lock")), ready))
        holder.start()
        self.assertTrue(ready.wait(10))
        try:
            with self.assertRaises(OutboxError):
                Outbox(self.path, lock_timeout=0.05).adicionar(self.evento("timeout"), agora=self.now)
        finally:
            holder.terminate()
            holder.join(10)

    @unittest.skipUnless(os.name == "nt", "reparo específico do lockfile Windows")
    def test_lockfile_vazio_de_versao_anterior_e_reparado(self):
        lock_path = self.path.with_name(".outbox.json.lock")
        lock_path.touch()
        Outbox(self.path, lock_timeout=2).adicionar(self.evento("apos-lock-vazio"), agora=self.now)
        self.assertEqual([r["event_id"] for r in Outbox(self.path).pendentes()], ["apos-lock-vazio"])

    def test_processo_morto_libera_lock_sem_apagar_estado(self):
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Event()
        holder = ctx.Process(target=_hold_lock, args=(str(self.path.with_name(".outbox.json.lock")), ready))
        holder.start()
        self.assertTrue(ready.wait(10))
        holder.terminate()
        holder.join(10)
        Outbox(self.path, lock_timeout=2).adicionar(self.evento("depois-do-crash"), agora=self.now)
        self.assertEqual([r["event_id"] for r in Outbox(self.path).pendentes()], ["depois-do-crash"])

    def test_dois_escritores_preservam_eventos_criados_com_cache_stale(self):
        primeiro = Outbox(self.path)
        segundo = Outbox(self.path)

        primeiro.adicionar(self.evento("e1"), agora=self.now)
        segundo.adicionar(self.evento("e2"), agora=self.now)

        eventos = {item["event_id"] for item in Outbox(self.path).pendentes()}
        self.assertEqual(eventos, {"e1", "e2"})

    def test_duplicacao_concorrente_do_mesmo_evento_e_idempotente(self):
        primeiro = Outbox(self.path, politica="reenvio_idempotente")
        segundo = Outbox(self.path, politica="reenvio_idempotente")
        evento = self.evento("e1")

        self.assertEqual(primeiro.adicionar(evento, agora=self.now)["event_id"], "e1")
        self.assertEqual(segundo.adicionar(evento, agora=self.now)["event_id"], "e1")
        self.assertEqual(len(Outbox(self.path).pendentes()), 1)

        with self.assertRaises(OutboxError):
            segundo.adicionar({**evento, "texto": "conteudo-divergente"}, agora=self.now)

    def test_crash_apos_in_flight_reabre_com_fencing(self):
        escritor = Outbox(self.path)
        escritor.adicionar(self.evento("e1"), agora=self.now)
        tentativa = escritor.reivindicar("e1", agora=self.now)

        reiniciado = Outbox(self.path)
        recuperado = reiniciado.recuperar_interrompidos(agora=self.now + timedelta(minutes=1))
        self.assertEqual(recuperado[0]["estado"], "pending")
        nova_tentativa = reiniciado.reivindicar("e1", agora=self.now + timedelta(minutes=1))
        self.assertNotEqual(nova_tentativa["attempt_id"], tentativa["attempt_id"])
        with self.assertRaises(OutboxError):
            reiniciado.aplicar_resultado(
                "e1",
                attempt_id=tentativa["attempt_id"],
                message_id="message-e1",
                ack=True,
                status=200,
            )

    def test_in_flight_nao_pode_ir_diretamente_para_expirado(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.evento("e1"), agora=self.now)
        outbox.reivindicar("e1", agora=self.now)

        with self.assertRaises(OutboxError):
            outbox.transicionar("e1", "expirado", agora=self.now + timedelta(hours=2))

    def test_in_flight_expirado_reabre_pending_e_expira_no_fluxo_explicito(self):
        outbox = Outbox(self.path)
        expirado_em = self.now - timedelta(minutes=1)
        outbox.adicionar(
            {**self.evento("e1"), "expira_em": expirado_em.isoformat()},
            agora=self.now - timedelta(hours=1),
        )
        tentativa = outbox.reivindicar("e1", agora=self.now - timedelta(hours=1))

        recuperado = outbox.recuperar_interrompidos(agora=self.now)
        self.assertEqual(recuperado[0]["estado"], "pending")
        self.assertEqual(recuperado[0]["message_id"], "message-e1")
        self.assertEqual(outbox.expirar(agora=self.now)[0]["estado"], "expirado")
        self.assertEqual(Outbox(self.path).pendentes(), [])
        self.assertEqual(tentativa["message_id"], "message-e1")

    def test_registro_persistido_incompleto_e_rejeitado(self):
        self.path.write_text(
            '[{"event_id":"e1","message_id":"message-e1","estado":"pending",'
            '"criado_em":"2026-09-13T20:00:00+00:00",'
            '"expira_em":"2026-09-13T21:00:00+00:00"}]',
            encoding="utf-8",
        )

        with self.assertRaises(OutboxError):
            Outbox(self.path)

    def test_ids_duplicados_com_conteudo_divergente_sao_rejeitados(self):
        self.path.write_text(
            '[{"event_id":"e1","message_id":"message-e1","texto":"primeiro",'
            '"estado":"pending","criado_em":"2026-09-13T20:00:00+00:00",'
            '"expira_em":"2026-09-13T21:00:00+00:00"},'
            '{"event_id":"e1","message_id":"message-e1","texto":"segundo",'
            '"estado":"pending","criado_em":"2026-09-13T20:00:00+00:00",'
            '"expira_em":"2026-09-13T21:00:00+00:00"}]',
            encoding="utf-8",
        )

        with self.assertRaises(OutboxError):
            Outbox(self.path)

    def test_estado_desconhecido_nao_e_persistido_nem_aceito(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.evento("e1"), agora=self.now)
        with self.assertRaises(OutboxError):
            outbox.transicionar("e1", "unknown", agora=self.now)
        self.assertEqual(Outbox(self.path).pendentes()[0]["estado"], "pending")

        self.path.write_text(
            '[{"event_id":"e2","message_id":"message-e2","texto":"x",'
            '"estado":"unknown","expira_em":"2026-09-13T20:00:00+00:00"}]',
            encoding="utf-8",
        )
        with self.assertRaises(OutboxError):
            Outbox(self.path)

    def test_politicas_diferenciam_reenvio_apos_resultado_sem_ack(self):
        padrao = Outbox(self.path, politica="padrao")
        padrao.adicionar(self.evento("padrao"), agora=self.now)
        tentativa = padrao.reivindicar("padrao", agora=self.now)
        padrao.aplicar_resultado(
            "padrao", attempt_id=tentativa["attempt_id"], message_id="message-padrao", ack=False, status=None
        )
        with self.assertRaises(OutboxError):
            padrao.reivindicar("padrao", agora=self.now + timedelta(minutes=1))

        idempotente = Outbox(Path(self.root.name) / "idempotente.json", politica="reenvio_idempotente")
        idempotente.adicionar(self.evento("retry"), agora=self.now)
        tentativa = idempotente.reivindicar("retry", agora=self.now)
        retry = idempotente.aplicar_resultado(
            "retry", attempt_id=tentativa["attempt_id"], message_id="message-retry", ack=False, status=None
        )
        self.assertEqual(retry["estado"], "pending")
        self.assertEqual(idempotente.reivindicar("retry", agora=self.now + timedelta(minutes=1))["estado"], "in_flight")


if __name__ == "__main__":
    unittest.main()
