import unittest

from suricata.dominio.relatorio import Relatorio
from suricata.rodada import execucao


class RelatorioCompatibilityTests(unittest.TestCase):
    def test_execucao_reexports_canonical_report_type(self):
        self.assertIs(execucao.Relatorio, Relatorio)

    def test_report_serialization_keeps_public_shape_and_defensive_copies(self):
        report = Relatorio(iniciado_em="2026-09-18T00:00:00+00:00", modo="sombra")
        report.eventos.append({"event_id": "e1"})
        serialized = report.json()
        serialized["eventos"].append({"event_id": "mutated"})
        self.assertEqual([item["event_id"] for item in report.json()["eventos"]], ["e1"])
        self.assertEqual(
            set(report.json()),
            {"iniciado_em", "modo", "estado", "ofertas", "ofertas_com_falha",
             "atividades", "linha_de_base", "eventos", "entrega", "agenda_manual",
             "coleta", "erro"},
        )


if __name__ == "__main__":
    unittest.main()
