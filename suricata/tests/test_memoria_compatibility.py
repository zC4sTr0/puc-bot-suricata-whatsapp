import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from suricata.execucao import comprometer_memoria
from suricata.memoria_rodada import comprometer_memoria as direto


def _atividade(chave="lista-1", fecha="2026-09-16T03:00:00+00:00",
               unlock="2026-09-15T12:00:00+00:00"):
    from suricata.publico import BRASILIA
    return SimpleNamespace(
        chave=chave,
        fecha=datetime.fromisoformat(fecha).astimezone(BRASILIA),
        unlock_at=datetime.fromisoformat(unlock).astimezone(BRASILIA),
    )


def _evento(tipo, event_id, atividade=None):
    return SimpleNamespace(tipo=tipo, event_id=event_id, texto="t", atividade=atividade)


class MemoriaCompatibilityTests(unittest.TestCase):
    def test_execucao_reexports_canonical_function(self):
        self.assertIs(comprometer_memoria, direto)

    def test_novo_duravel_marca_item_e_consome_novidade(self):
        ativ = _atividade()
        comprometida: dict = {"itens": {}}
        planejada = {"itens": {"lista-1": {"agenda": "x", "novidade_pendente": True}}}
        evento = _evento("novo", "grupo:novo:lista-1", ativ)
        momento = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)
        resultado = comprometer_memoria(comprometida, planejada, [evento],
                                        {"grupo:novo:lista-1"}, {"sessao": "ok"}, momento)
        self.assertIs(resultado, comprometida)
        # Item planejado é copiado e a marca de novidade é consumida.
        self.assertEqual(comprometida["itens"]["lista-1"], {"agenda": "x"})
        # fecha/unlock em 16/09 BRT = amanhã relativo a 15/09 BRT.
        self.assertEqual(comprometida["chegando"]["lista-1"], "2026-09-16")

    def test_novo_sem_durabilidade_nao_muta_memoria(self):
        ativ = _atividade()
        comprometida: dict = {"itens": {}}
        planejada = {"itens": {"lista-1": {"agenda": "x"}}}
        comprometer_memoria(comprometida, planejada,
                            [_evento("novo", "grupo:novo:lista-1", ativ)],
                            set(), {"sessao": "ok"},
                            datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida, {"itens": {}})

    def test_falha_de_ponte_nao_consome_memoria(self):
        ativ = _atividade()
        comprometida: dict = {"itens": {}}
        planejada = {"itens": {"lista-1": {"agenda": "x"}}}
        comprometer_memoria(comprometida, planejada,
                            [_evento("novo", "grupo:novo:lista-1", ativ)],
                            {"grupo:novo:lista-1"}, {"sessao": "erro"},
                            datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida, {"itens": {}})

    def test_anuncio_duravel_copia_marcacao_planejada(self):
        comprometida: dict = {}
        planejada = {"anuncios": {"a1": "2026-09-15T10:00:00+00:00"}}
        evento = _evento("anuncio", "grupo:anuncio:a1")
        comprometer_memoria(comprometida, planejada, [evento], {evento.event_id},
                            {}, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida["anuncios"], {"a1": "2026-09-15T10:00:00+00:00"})

    def test_aviso_prova_duravel_copia_marcacao_planejada(self):
        comprometida: dict = {}
        planejada = {"avisos_prova": {"2026-09-18": "marcado"}}
        evento = _evento("aviso_prova", "grupo:aviso_prova:2026-09-18")
        comprometer_memoria(comprometida, planejada, [evento], {evento.event_id},
                            {}, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida["avisos_prova"], {"2026-09-18": "marcado"})

    def test_vespera_duravel_copia_marcacao_e_campos_auxiliares(self):
        comprometida: dict = {}
        planejada = {"vesperas": {"2026-09-16": "marcado"},
                     "chegando": {"lista-1": "2026-09-16"},
                     "adiantadas": {"lista-2": "2026-09-16"}}
        evento = _evento("vespera", "grupo:vespera:2026-09-16")
        comprometer_memoria(comprometida, planejada, [evento], {evento.event_id},
                            {}, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida["vesperas"], {"2026-09-16": "marcado"})
        self.assertEqual(comprometida["chegando"], {"lista-1": "2026-09-16"})
        self.assertEqual(comprometida["adiantadas"], {"lista-2": "2026-09-16"})

    def test_item_planejado_ausente_apenas_consome_marca_existente(self):
        comprometida: dict = {"itens": {"lista-1": {"novidade_pendente": True}}}
        planejada = {"itens": {}}
        ativ = _atividade()
        comprometer_memoria(comprometida, planejada,
                            [_evento("mudou", "grupo:mudou:lista-1:1", ativ)],
                            {"grupo:mudou:lista-1:1"}, {}, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        self.assertEqual(comprometida["itens"], {"lista-1": {}})

    def test_copia_do_planejado_e_defensiva(self):
        comprometida: dict = {"itens": {}}
        item = {"agenda": "x"}
        planejada = {"itens": {"lista-1": item}}
        ativ = _atividade()
        comprometer_memoria(comprometida, planejada,
                            [_evento("mudou", "grupo:mudou:lista-1:1", ativ)],
                            {"grupo:mudou:lista-1:1"}, {}, datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc))
        comprometida["itens"]["lista-1"]["agenda"] = "mudado"
        self.assertEqual(item["agenda"], "x")


if __name__ == "__main__":
    unittest.main()
