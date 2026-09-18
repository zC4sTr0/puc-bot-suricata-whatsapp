import unittest
from datetime import date

import suricata.publico as publico
from suricata.calendario import _pascoa, eh_dia_de_aula, feriados_nacionais
from suricata.planejamento import planejar_vespera


class CalendarioCompatibilityTests(unittest.TestCase):
    def test_publico_reexporta_os_nomes_canonicos(self):
        self.assertIs(publico.eh_dia_de_aula, eh_dia_de_aula)
        self.assertIs(publico.feriados_nacionais, feriados_nacionais)
        self.assertIs(publico._pascoa, _pascoa)

    def test_pascoa_datas_conhecidas_do_calendario_gregoriano(self):
        self.assertEqual(_pascoa(2024), date(2024, 3, 31))
        self.assertEqual(_pascoa(2025), date(2025, 4, 20))
        self.assertEqual(_pascoa(2026), date(2026, 4, 5))
        self.assertEqual(_pascoa(2027), date(2027, 3, 28))

    def test_feriados_fixos_e_sexta_feira_santa_2026(self):
        feriados = feriados_nacionais(2026)
        for dia in (date(2026, 1, 1), date(2026, 4, 21), date(2026, 5, 1),
                    date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2),
                    date(2026, 11, 15), date(2026, 11, 20), date(2026, 12, 25)):
            self.assertIn(dia, feriados)
        # Sexta-feira Santa 2026 = 03/04 (Páscoa 05/04 - 2 dias).
        self.assertIn(date(2026, 4, 3), feriados)
        self.assertEqual(len(feriados), 10)

    def test_carnaval_e_corpus_christi_sao_ponto_facultativo(self):
        feriados = feriados_nacionais(2026)
        self.assertNotIn(date(2026, 2, 17), feriados)  # Carnaval 2026
        self.assertNotIn(date(2026, 6, 4), feriados)   # Corpus Christi 2026

    def test_dia_de_aula_exclui_fim_de_semana_e_feriado(self):
        self.assertTrue(eh_dia_de_aula(date(2026, 9, 15)))   # terça comum
        self.assertFalse(eh_dia_de_aula(date(2026, 9, 12)))  # sábado
        self.assertFalse(eh_dia_de_aula(date(2026, 9, 13)))  # domingo
        self.assertFalse(eh_dia_de_aula(date(2026, 9, 7)))   # segunda, feriado
        self.assertFalse(eh_dia_de_aula(date(2026, 4, 3)))   # sexta, Sexta-feira Santa

    def test_vespera_de_feriado_continua_sem_aviso(self):
        # 07/09/2026 (feriado) não gera véspera em 06/09: contrato preservado.
        self.assertIsNone(planejar_vespera([], {}, _sem_timezone(2026, 9, 6)))

    def test_mutacao_de_feriado_e_detectada_pelo_contrato(self):
        # Guarda explícita: se a lista de feriados mudar, este teste quebra.
        self.assertIn(date(2026, 11, 20), feriados_nacionais(2026))  # Consciência Negra
        self.assertNotIn(date(2026, 7, 20), feriados_nacionais(2026))  # não é feriado


def _sem_timezone(ano, mes, dia):
    from datetime import datetime, time
    from suricata.horario import BRASILIA
    return datetime(ano, mes, dia, 18, 0, tzinfo=BRASILIA)


if __name__ == "__main__":
    unittest.main()
