"""Compatibilidade da quarentena de legados (suricata/legacy/).

As facades nas origens devem re-exportar EXATAMENTE os mesmos objetos
(assertIs de identidade) que as implementações em suricata/legacy/, e
todo símbolo usado por importadores reais (produção e testes) deve
continuar importável pelos caminhos antigos.
"""
import unittest

from suricata import delivery, grupo, lease
from suricata.legacy import delivery as legacy_delivery
from suricata.legacy import grupo as legacy_grupo
from suricata.legacy import lease as legacy_lease
from suricata.legacy import whatsapp as legacy_whatsapp
from suricata.notifiers import whatsapp


class DeliveryFacadeIdentityTests(unittest.TestCase):
    def test_simbolos_publicos_sao_os_mesmos_objetos(self):
        self.assertIs(delivery.Delivery, legacy_delivery.Delivery)
        self.assertIs(delivery.DeliveryError, legacy_delivery.DeliveryError)
        self.assertIs(delivery.DeliveryOrchestrator, legacy_delivery.DeliveryOrchestrator)

    def test_all_da_facade_cobre_todos_os_simbolos_publicos(self):
        self.assertEqual(
            delivery.__all__, ["Delivery", "DeliveryError", "DeliveryOrchestrator"]
        )


class LeaseFacadeIdentityTests(unittest.TestCase):
    def test_simbolos_publicos_sao_os_mesmos_objetos(self):
        self.assertIs(lease.Lease, legacy_lease.Lease)
        self.assertIs(lease.LeaseConfig, legacy_lease.LeaseConfig)
        self.assertIs(lease.LeaseState, legacy_lease.LeaseState)
        self.assertIs(lease.LeaseStore, legacy_lease.LeaseStore)


class GrupoFacadeIdentityTests(unittest.TestCase):
    def test_simbolos_publicos_sao_os_mesmos_objetos(self):
        self.assertIs(grupo.EXCLUIDAS, legacy_grupo.EXCLUIDAS)
        self.assertIs(grupo.GrupoError, legacy_grupo.GrupoError)
        self.assertIs(grupo.EventoGrupo, legacy_grupo.EventoGrupo)
        self.assertIs(grupo.Evento, legacy_grupo.Evento)
        self.assertIs(grupo.ofertas_elegiveis, legacy_grupo.ofertas_elegiveis)
        self.assertIs(grupo.decidir_grupo, legacy_grupo.decidir_grupo)
        self.assertIs(grupo.anuncio_relevante, legacy_grupo.anuncio_relevante)
        self.assertIs(grupo.renderizar_evento, legacy_grupo.renderizar_evento)
        self.assertIs(grupo.renderizar, legacy_grupo.renderizar)
        self.assertIs(grupo.renderizar_dia_grupo, legacy_grupo.renderizar_dia_grupo)

    def test_all_da_facade_igual_ao_legado(self):
        self.assertEqual(grupo.__all__, legacy_grupo.__all__)


class WhatsappFacadeIdentityTests(unittest.TestCase):
    def test_simbolos_publicos_sao_os_mesmos_objetos(self):
        self.assertIs(whatsapp.WhatsAppGrupo, legacy_whatsapp.WhatsAppGrupo)
        self.assertIs(whatsapp.entregar_grupo, legacy_whatsapp.entregar_grupo)


class ImportadoresReaisTests(unittest.TestCase):
    """Importa cada símbolo que os importadores reais usam.

    Produção: suricata/sentinela.py (grupo.decidir_grupo/renderizar_evento) e
    suricata/notifiers/__init__.py (whatsapp.WhatsAppGrupo/entregar_grupo).
    Testes: test_delivery, test_application_integration, test_lease,
    test_grupo, test_bridge_integration, test_notifier_whatsapp.
    """

    def test_sentinela_importa_simbolos_de_grupo(self):
        from suricata.grupo import decidir_grupo, renderizar_evento

        self.assertIs(decidir_grupo, legacy_grupo.decidir_grupo)
        self.assertIs(renderizar_evento, legacy_grupo.renderizar_evento)

    def test_notifiers_package_reexporta_simbolos_de_whatsapp(self):
        import suricata.notifiers as notifiers

        self.assertIs(notifiers.WhatsAppGrupo, legacy_whatsapp.WhatsAppGrupo)
        self.assertIs(notifiers.entregar_grupo, legacy_whatsapp.entregar_grupo)
        self.assertIs(notifiers.whatsapp, whatsapp)

    def test_importadores_de_delivery(self):
        from suricata.delivery import DeliveryError, DeliveryOrchestrator

        self.assertIs(DeliveryOrchestrator, legacy_delivery.DeliveryOrchestrator)
        self.assertIs(DeliveryError, legacy_delivery.DeliveryError)

    def test_importadores_de_lease(self):
        from suricata.lease import Lease, LeaseConfig, LeaseState

        self.assertIs(Lease, legacy_lease.Lease)
        self.assertIs(LeaseConfig, legacy_lease.LeaseConfig)
        self.assertIs(LeaseState, legacy_lease.LeaseState)

    def test_importadores_de_grupo(self):
        from suricata.grupo import (
            EXCLUIDAS,
            anuncio_relevante,
            decidir_grupo,
            ofertas_elegiveis,
            renderizar_dia_grupo,
            renderizar_evento,
        )

        self.assertIs(EXCLUIDAS, legacy_grupo.EXCLUIDAS)
        self.assertIs(anuncio_relevante, legacy_grupo.anuncio_relevante)
        self.assertIs(decidir_grupo, legacy_grupo.decidir_grupo)
        self.assertIs(ofertas_elegiveis, legacy_grupo.ofertas_elegiveis)
        self.assertIs(renderizar_dia_grupo, legacy_grupo.renderizar_dia_grupo)
        self.assertIs(renderizar_evento, legacy_grupo.renderizar_evento)

    def test_importadores_de_notifiers_whatsapp(self):
        from suricata.notifiers.whatsapp import WhatsAppGrupo, entregar_grupo

        self.assertIs(WhatsAppGrupo, legacy_whatsapp.WhatsAppGrupo)
        self.assertIs(entregar_grupo, legacy_whatsapp.entregar_grupo)


if __name__ == "__main__":
    unittest.main()
