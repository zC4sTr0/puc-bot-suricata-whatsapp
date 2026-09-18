import re
import unittest

from suricata.dominio.message_id import message_id


class MessageIdTests(unittest.TestCase):
    def test_vetor_conhecido_segue_formula(self):
        self.assertEqual(message_id("turma", "evento-123"), "3EB03127523346EDF4261C")

    def test_mesmo_grupo_e_evento_sao_deterministicos(self):
        self.assertEqual(message_id("turma", "evento-123"), message_id("turma", "evento-123"))

    def test_grupos_ou_eventos_distintos_produzem_ids_distintos(self):
        ids = {
            message_id("turma-a", "evento-123"),
            message_id("turma-b", "evento-123"),
            message_id("turma-a", "evento-456"),
        }
        self.assertEqual(len(ids), 3)

    def test_formato_tem_prefixo_hexadecimal_maiusculo_e_22_caracteres(self):
        result = message_id("turma", "evento-123")
        self.assertEqual(len(result), 22)
        self.assertRegex(result, r"^3EB0[0-9A-F]{18}$")

    def test_tres_entradas_invalidas_sao_rejeitadas(self):
        casos = (
            (None, "evento-123", TypeError),
            ("turma", 123, TypeError),
            ("", "evento-123", ValueError),
        )
        for grupo, event_id, error in casos:
            with self.subTest(grupo=grupo, event_id=event_id):
                with self.assertRaises(error):
                    message_id(grupo, event_id)


if __name__ == "__main__":
    unittest.main()
