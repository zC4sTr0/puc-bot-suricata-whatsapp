import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suricata.estado import (
    EstadoLocal,
    EstadoError,
    dedup_key,
    escrever_json_atomico,
    anexar_jsonl_atomico,
    sanitizar_status_operacional,
)


class EstadoLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def test_dedup_eh_identidade_de_item_versao_e_transicao(self):
        self.assertEqual(dedup_key("item-1", "v2", "novo"), "item-1|v2|novo")
        self.assertEqual(dedup_key("item-1", "v2", "janela:aberto"), "item-1|v2|janela:aberto")
        self.assertNotEqual(dedup_key("item-1", "v1", "novo"), dedup_key("item-1", "v2", "novo"))
        with self.assertRaises(EstadoError):
            dedup_key("item|injetado", "v1", "novo")

    def test_memoria_diaria_e_dedupe_sao_append_only(self):
        estado = EstadoLocal(self.root)
        registro = {"item_id": "item-1", "versao": "v1", "transicao": "novo", "visto_em": self.now.isoformat()}
        self.assertTrue(estado.registrar_dedup(registro))
        self.assertFalse(estado.registrar_dedup(registro))
        self.assertTrue(estado.ja_deduplicado(dedup_key("item-1", "v1", "novo")))
        estado.registrar_memoria_grupo({"linha_de_base_em": self.now.isoformat(), "anuncios_vistos": {}})
        self.assertEqual(estado.ler_memoria_grupo()["linha_de_base_em"], self.now.isoformat())
        estado.registrar_diario({"event_id": "grupo:dia:2026-09-14", "eventos": 1, "registrado_em": self.now.isoformat()})
        estado.registrar_diario({"event_id": "grupo:dia:2026-09-15", "eventos": 0, "registrado_em": self.now.isoformat()})
        linhas = (self.root / "grupo" / "diario.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertEqual(json.loads(linhas[0])["event_id"], "grupo:dia:2026-09-14")

    def test_heartbeat_atualiza_apenas_rodada_saudavel(self):
        estado = EstadoLocal(self.root)
        estado.atualizar_heartbeat(saudavel=True, agora=self.now, contagens={"itens": 3})
        primeiro = estado.ler_heartbeat()
        self.assertEqual(primeiro["sentinela_ok_em"], self.now.isoformat())
        self.assertEqual(primeiro["contagens"], {"itens": 3})
        estado.atualizar_heartbeat(saudavel=False, agora=self.now.replace(hour=13), status="erro")
        self.assertEqual(estado.ler_heartbeat()["sentinela_ok_em"], self.now.isoformat())
        self.assertEqual(estado.ler_heartbeat()["status"], "erro")

    def test_status_operacional_remove_detalhe_e_rejeita_segredos(self):
        status = sanitizar_status_operacional({"status": "degradado", "erro": "timeout", "tentativas": 2, "token": "segredo"})
        self.assertEqual(status, {"status": "degradado", "erro": "timeout", "tentativas": 2})
        for campo in ("token", "session", "sessao", "cookie", "nota", "entrega", "jid"):
            seguro = sanitizar_status_operacional({"status": "ok", campo: "privado"})
            self.assertNotIn(campo, seguro)
        with self.assertRaises(EstadoError):
            sanitizar_status_operacional({"status": "ok", "contagens": {"token": 1}})

    def test_escritas_atomicas_deixam_json_valido_e_limpa_temporario(self):
        caminho = self.root / "estado.json"
        escrever_json_atomico(caminho, {"status": "ok"})
        self.assertEqual(json.loads(caminho.read_text(encoding="utf-8")), {"status": "ok"})
        anexar_jsonl_atomico(self.root / "eventos.jsonl", [{"id": "1"}, {"id": "2"}])
        anexar_jsonl_atomico(self.root / "eventos.jsonl", [{"id": "3"}])
        self.assertEqual(len((self.root / "eventos.jsonl").read_text(encoding="utf-8").splitlines()), 3)
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
