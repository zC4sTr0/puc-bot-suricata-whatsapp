import unittest

from suricata.integracao.canvas import (
    ROUTES,
    CanvasClient,
    CanvasResponseKind,
    PublicAnnouncement,
    PublicAssignment,
    _itens_do_payload,
    classify_status,
)


class FakeTransport:
    def __init__(self, status=200, body=None):
        self.status, self.body, self.calls = status, body or [], []

    def __call__(self, method, url, headers, timeout):
        self.calls.append((method, url, headers, timeout))
        return self.status, {"content-type": "application/json"}, self.body


class CanvasTests(unittest.TestCase):
    def test_interpreta_payload_em_lista_de_dtos(self):
        itens = _itens_do_payload([{"id": 4, "name": "Quiz"}], lambda item: item["name"])

        self.assertEqual(itens, ("Quiz",))

    def test_interpreta_payload_rejeita_item_que_nao_e_objeto(self):
        with self.assertRaises(TypeError):
            _itens_do_payload(["item inválido"], lambda item: item)

    def test_rejeita_origem_externa_antes_do_transporte_mesmo_sem_token(self):
        transport = FakeTransport()
        with self.assertRaises(ValueError):
            CanvasClient(token="", origin="https://evil.example", transport=transport)
        self.assertEqual(transport.calls, [])

    def test_rejeita_origem_externa_antes_do_transporte(self):
        transport = FakeTransport()
        with self.assertRaises(ValueError) as raised:
            CanvasClient("nao-deve-aparecer", origin="https://evil.example", transport=transport)
        self.assertNotIn("nao-deve-aparecer", str(raised.exception))
        self.assertEqual(transport.calls, [])

    def test_sem_token_rejeita_path_query_fragment_credenciais_porta_e_esquema(self):
        for origin in (
            "https://pucminas.instructure.com/api/v1",
            "https://pucminas.instructure.com?next=https://evil.example",
            "https://pucminas.instructure.com#fragment",
            "https://user:pass@pucminas.instructure.com",
            "https://pucminas.instructure.com:444",
            "http://pucminas.instructure.com",
            "https://evil.example",
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    CanvasClient(token="", origin=origin, transport=FakeTransport())

    def test_bearer_normaliza_origem_canonica_esquema_e_porta_padrao(self):
        for origin in ("https://pucminas.instructure.com/", "HTTPS://pucminas.instructure.com:443"):
            with self.subTest(origin=origin):
                client = CanvasClient("segredo", origin=origin, transport=FakeTransport())
                self.assertEqual(client.origin, "https://pucminas.instructure.com")

    def test_request_sem_token_nao_envia_bearer(self):
        transport = FakeTransport()
        result = CanvasClient(token="", origin="https://pucminas.instructure.com", transport=transport).assignments("1")
        self.assertEqual(result.kind, CanvasResponseKind.OK)
        self.assertNotIn("Authorization", transport.calls[0][2])

    def test_assignment_sanitizado_remove_submission_nota_e_token(self):
        transport = FakeTransport(body=[{"id": 4, "name": "Quiz", "points_possible": 10,
            "submission": {"grade": 10}, "token": "secret", "description": "<b>Leia</b>"}])
        result = CanvasClient(transport=transport).assignments("123")
        self.assertEqual(result.kind, CanvasResponseKind.OK)
        self.assertEqual(result.items, (PublicAssignment(id="4", name="Quiz", points_possible=10.0, description="Leia"),))
        self.assertNotIn("submission", result.items[0].__dict__)
        self.assertNotIn("token", repr(result))

    def test_anuncios_publicos_sao_dto_sem_campos_sensiveis(self):
        transport = FakeTransport(body=[{"id": 9, "title": "Prova", "message": "<p>Atenção</p>", "author": {"id": 2}, "access_token": "x"}])
        result = CanvasClient(transport=transport).announcements(["course_123"], "2026-09-11")
        self.assertEqual(result.items[0], PublicAnnouncement(id="9", title="Prova", message="Atenção"))
        self.assertNotIn("author", repr(result))

    def test_cliente_somente_get_com_timeout_explicito_e_rotas(self):
        transport = FakeTransport(status=401, body={"errors": []})
        result = CanvasClient(transport=transport, timeout=3.5).assignments("123")
        method, url, _, timeout = transport.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(timeout, 3.5)
        self.assertIn("include%5B%5D=all_dates", url)
        self.assertEqual(result.kind, CanvasResponseKind.UNAUTHORIZED)
        self.assertEqual(ROUTES["assignments"].method, "GET")

    def test_respostas_sao_classificadas_e_body_invalido_e_erro(self):
        for status, expected in ((404, CanvasResponseKind.NOT_FOUND), (429, CanvasResponseKind.RATE_LIMITED), (503, CanvasResponseKind.SERVER_ERROR)):
            result = CanvasClient(transport=FakeTransport(status=status, body={"x": 1})).assignments("1")
            self.assertEqual(result.kind, expected)
        result = CanvasClient(transport=FakeTransport(body="not-list")).assignments("1")
        self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)

    def test_payload_misto_com_item_nao_mapeavel_e_invalido(self):
        body = [{"id": 1, "name": "válido"}, "item inesperado"]
        result = CanvasClient(transport=FakeTransport(body=body)).assignments("1")
        self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)
        self.assertEqual(result.items, ())

    def test_payload_com_item_sem_id_e_invalido(self):
        for item in ({"name": "sem identificador"}, {"id": None, "name": "id nulo"}, {"id": "  ", "name": "id vazio"}):
            with self.subTest(item=item):
                result = CanvasClient(transport=FakeTransport(body=[item])).assignments("1")
                self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)
                self.assertEqual(result.items, ())

    def test_payload_rejeita_points_possible_nao_numerico(self):
        result = CanvasClient(transport=FakeTransport(body=[
            {"id": 1, "name": "quiz", "points_possible": "não-numérico"}
        ])).assignments("1")
        self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)
        self.assertEqual(result.items, ())

    def test_payload_rejeita_points_possible_nao_finito_booleano_ou_negativo(self):
        for points in (True, False, float("nan"), float("inf"), float("-inf"), -0.01):
            with self.subTest(points=points):
                result = CanvasClient(transport=FakeTransport(body=[
                    {"id": 1, "name": "quiz", "points_possible": points}
                ])).assignments("1")
                self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)
                self.assertEqual(result.items, ())

    def test_classify_status_sanitiza_status_nao_int_bool_none_e_tipos_estranhos(self):
        for status in (None, True, False, "200", 200.0, [], {}, object()):
            with self.subTest(status=repr(status)):
                self.assertEqual(classify_status(status), CanvasResponseKind.INVALID_PAYLOAD)

    def test_get_status_malformado_retorna_payload_invalido_sem_expor_status(self):
        for status in (None, True, False, "503", 503.0, [], {}, object()):
            with self.subTest(status=repr(status)):
                result = CanvasClient(transport=FakeTransport(status=status)).assignments("1")
                self.assertEqual(result.kind, CanvasResponseKind.INVALID_PAYLOAD)
                self.assertIsNone(result.status)
                self.assertEqual(result.items, ())


if __name__ == "__main__":
    unittest.main()
