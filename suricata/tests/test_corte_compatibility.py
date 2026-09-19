import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import suricata.rodada as rodada
import suricata.rodada.execucao as execucao
from suricata.dominio.corte_rodada import (
    _corte_21h,
    _evento_disponivel,
    _janela_manha,
    corte_21h,
    evento_disponivel,
    janela_manha,
)
from suricata.dominio.horario import BRASILIA


class CorteCompatibilityTests(unittest.TestCase):
    def test_predicados_tem_identidade_unica_entre_modulos(self):
        self.assertIs(corte_21h, _corte_21h)
        self.assertIs(janela_manha, _janela_manha)
        self.assertIs(evento_disponivel, _evento_disponivel)
        self.assertIs(execucao._corte_21h, corte_21h)
        self.assertIs(execucao._janela_manha, janela_manha)
        self.assertIs(execucao._evento_disponivel, evento_disponivel)
        self.assertIs(execucao._autorizacao_corte, execucao._autorizacao_corte)
        self.assertIs(rodada._corte_21h, corte_21h)
        self.assertIs(rodada._janela_manha, janela_manha)
        self.assertIs(rodada._autorizados_persistidos, execucao._autorizados_persistidos)

    def test_corte_21h_limites_exatos_em_brt(self):
        utc = timezone.utc
        # 20:59:59.999999 BRT = 23:59:59.999999 UTC do dia anterior.
        antes = datetime(2026, 9, 15, 23, 59, 59, 999999, tzinfo=utc)
        self.assertFalse(corte_21h(antes))
        # 21:00:00.000000 BRT = 00:00:00 UTC do dia seguinte.
        exato = datetime(2026, 9, 16, 0, 0, 0, 0, tzinfo=utc)
        self.assertTrue(corte_21h(exato))
        # Limites em BRT com fuso EXPLÍCITO: datetime naive é interpretado no
        # fuso do host por astimezone(), e o teste não pode depender do host
        # (CI roda em UTC; hosts BRT passariam por acidente).
        self.assertFalse(corte_21h(datetime(2026, 9, 15, 20, 59, tzinfo=BRASILIA)))
        self.assertTrue(corte_21h(datetime(2026, 9, 15, 21, 0, tzinfo=BRASILIA)))

    def test_janela_manha_somente_0700(self):
        utc = timezone.utc
        self.assertFalse(janela_manha(datetime(2026, 9, 16, 9, 59, 59, 999999, tzinfo=utc)))
        self.assertTrue(janela_manha(datetime(2026, 9, 16, 10, 0, 0, tzinfo=utc)))
        self.assertFalse(janela_manha(datetime(2026, 9, 16, 10, 1, 0, tzinfo=utc)))

    def test_evento_disponivel_contrato_completo(self):
        agora = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(evento_disponivel({}, agora))
        self.assertTrue(evento_disponivel({"disponivel_em": None}, agora))
        self.assertTrue(evento_disponivel(
            {"disponivel_em": "2026-09-15T12:00:00+00:00"}, agora))
        self.assertFalse(evento_disponivel(
            {"disponivel_em": "2026-09-15T12:00:01+00:00"}, agora))
        # Estado persistido inválido (valor verdadeiro não-datado) nunca
        # autoriza envio antecipado; valores falsy curto-circuitam como
        # "sem janela" (comportamento original preservado).
        self.assertTrue(evento_disponivel({"disponivel_em": []}, agora))
        self.assertTrue(evento_disponivel({"disponivel_em": ""}, agora))
        for invalido in ("não-é-data", 42, ["x"], {"a": 1}):
            self.assertFalse(evento_disponivel({"disponivel_em": invalido}, agora))

    def test_autorizacao_corte_exige_pode_aguardar_07h(self):
        from suricata.dominio.publico import BRASILIA
        # Descoberta às 20:00 BRT → dia da manhã é o dia seguinte (16/09):
        # a exceção exige quiz/avaliação com unlock e fecha no mesmo dia.
        atividade = SimpleNamespace(
            chave="quiz-1", tipo="quiz", titulo="Quiz 1", fonte="canvas",
            unlock_at=datetime(2026, 9, 16, 8, 0, tzinfo=BRASILIA),
            fecha=datetime(2026, 9, 16, 23, 0, tzinfo=BRASILIA),
        )
        evento = SimpleNamespace(tipo="novo", event_id="e1", texto="t",
                                 atividade=atividade, disponivel_em=None)
        agora = datetime(2026, 9, 15, 20, 0, tzinfo=BRASILIA)
        autorizacao = execucao._autorizacao_corte(evento, agora)
        self.assertIsNotNone(autorizacao)
        self.assertEqual(autorizacao["chave"], "quiz-1")
        self.assertEqual(autorizacao["tipo"], "quiz")
        self.assertEqual(autorizacao["descoberto_em"], agora.isoformat())
        # Atividade que não pode aguardar 07h não recebe autorização.
        atividade_fora = SimpleNamespace(
            chave="lista-x", tipo="lista", titulo="Lista X", fonte="canvas",
            unlock_at=datetime(2026, 9, 16, 8, 0, tzinfo=BRASILIA),
            fecha=datetime(2026, 9, 20, 23, 0, tzinfo=BRASILIA),
        )
        evento_fora = SimpleNamespace(tipo="novo", event_id="e2", texto="t",
                                      atividade=atividade_fora, disponivel_em=None)
        self.assertIsNone(execucao._autorizacao_corte(evento_fora, agora))


if __name__ == "__main__":
    unittest.main()
