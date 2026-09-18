"""Schema do _emit congelado chave a chave (1.3).

Caracterização: os payloads de erro são congelados por ``main`` em processo
(argv + stdout capturado). O payload sentinela de sucesso é congelado com
``client_factory`` injetado (double local, sem rede): o caminho real construiria
``CanvasClient`` contra a origem allowlisted externa
(``https://pucminas.instructure.com``), e a config de teste é uma cópia de
``config.example.json`` em tmp (sem chaves de segredo).

DIVERGÊNCIA REGISTRADA (plano x código real): o plano assumia que o
``relatorio`` do sentinela de sucesso teria as 12 chaves de
``Relatorio.json()`` (``suricata/relatorio.py``). No código atual esse shape
pertence ao caminho ``rodada`` (``execucao.py`` devolve ``relatorio.json()``);
o sentinela emite o dicionário de ``executar_rodada_sombra`` + as chaves
``entrega``/``delivery`` adicionadas por ``SentinelaApplication.run``. Os dois
schemas são congelados abaixo como eles são.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from suricata import entrypoint
from suricata.relatorio import Relatorio

ROOT = Path(__file__).resolve().parents[1]  # diretório do pacote suricata/

CHAVES_RELATORIO_SENTINELA = {
    "modo", "estado", "coleta", "candidatos", "projetados", "decisoes",
    "avisos", "eventos", "envio_whatsapp", "entrega", "delivery",
}

CHAVES_RELATORIO_JSON = {
    "iniciado_em", "modo", "estado", "ofertas", "ofertas_com_falha",
    "atividades", "linha_de_base", "eventos", "entrega", "agenda_manual",
    "coleta", "erro",
}


class _ClienteCanvasDuplo:
    """Double local: planner 200 implícito + assignments 200 por oferta."""

    def __init__(self):
        self.status = 200
        self.chamadas = []

    def assignments(self, oferta):
        self.chamadas.append(oferta)
        resposta = type("Resposta", (), {})()
        resposta.status = 200
        resposta.items = [{"id": 1, "name": "Tarefa", "course_id": oferta}]
        return resposta


class EmitSchemaTests(unittest.TestCase):
    def invoke(self, *args, client_factory=None):
        """Roda ``entrypoint.main`` em processo e captura o stdout do _emit."""
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = entrypoint.main(list(args), client_factory=client_factory)
        linhas = saida.getvalue().splitlines()
        self.assertEqual(len(linhas), 1)
        return codigo, json.loads(linhas[0]), linhas[0]

    # ---------------------------------------------------------------- erros

    def test_erro_sem_mode(self):
        codigo, payload, _ = self.invoke()
        self.assertEqual(codigo, 2)
        self.assertEqual(set(payload), {"status", "error"})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "modo ausente")

    def test_erro_mode_invalido(self):
        codigo, payload, _ = self.invoke("--mode", "foo")
        self.assertEqual(codigo, 2)
        self.assertEqual(set(payload), {"status", "error"})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "modo inválido")

    def test_erro_argumentos_invalidos(self):
        for argumentos in (("--flag", "x"), ("--mode",)):
            with self.subTest(argumentos=argumentos):
                codigo, payload, _ = self.invoke(*argumentos)
                self.assertEqual(codigo, 2)
                self.assertEqual(set(payload), {"status", "error"})
                self.assertEqual(payload["status"], "error")
                self.assertEqual(payload["error"], "argumentos inválidos")

    def test_erro_sentinela_sem_config(self):
        codigo, payload, _ = self.invoke("--mode", "sentinela")
        self.assertEqual(codigo, 2)
        self.assertEqual(set(payload), {"mode", "status", "error"})
        self.assertEqual(payload["mode"], "sentinela")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "configuração ausente")

    def test_erro_sentinela_config_invalida(self):
        # JSON ilegível no arquivo e JSON válido que falha na validação
        # (ofertas ausentes) produzem o mesmo payload sanitizado.
        with tempfile.TemporaryDirectory() as directory:
            ilegivel = Path(directory) / "ilegivel.json"
            ilegivel.write_text("não é json", encoding="utf-8")
            codigo, payload, _ = self.invoke("--mode", "sentinela", "--config", str(ilegivel))
            sem_ofertas = Path(directory) / "sem-ofertas.json"
            sem_ofertas.write_text(json.dumps({"ambiente": "teste"}), encoding="utf-8")
            codigo2, payload2, _ = self.invoke("--mode", "sentinela", "--config", str(sem_ofertas))
        for atual in (codigo, codigo2):
            self.assertEqual(atual, 2)
        for atual in (payload, payload2):
            self.assertEqual(set(atual), {"mode", "status", "error"})
            self.assertEqual(atual["mode"], "sentinela")
            self.assertEqual(atual["status"], "error")
            self.assertEqual(atual["error"], "configuração inválida")

    # -------------------------------------------------- sentinela sucesso

    def _config_exemplo(self, directory) -> Path:
        """Copia config.example.json para tmp (modelo público, sem segredo)."""
        destino = Path(directory) / "config.json"
        destino.write_text(
            (ROOT / "config.example.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return destino

    def test_sentinela_sucesso_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            caminho = self._config_exemplo(directory)
            fabrica = lambda **kwargs: _ClienteCanvasDuplo()
            codigo, payload, linha = self.invoke(
                "--mode", "sentinela", "--config", str(caminho),
                client_factory=fabrica,
            )
        self.assertEqual(codigo, 0)
        # Payload de sucesso: exatamente mode/status/relatorio.
        self.assertEqual(set(payload), {"mode", "status", "relatorio"})
        self.assertEqual(payload["mode"], "sentinela")
        self.assertEqual(payload["status"], "ok")

        relatorio = payload["relatorio"]
        # Divergência registrada no docstring: 11 chaves reais, não as 12
        # chaves de Relatorio.json() (que pertencem ao caminho rodada).
        self.assertEqual(set(relatorio), CHAVES_RELATORIO_SENTINELA)

        self.assertEqual(relatorio["modo"], "sombra")
        self.assertEqual(relatorio["estado"], "concluida")
        self.assertEqual(relatorio["candidatos"], 1)
        self.assertEqual(relatorio["avisos"], 0)
        self.assertEqual(relatorio["eventos"], [])
        self.assertEqual(relatorio["projetados"], 1)
        # Item "Tarefa" sem datas vira tarefa nova no diário (determinístico).
        self.assertEqual(
            relatorio["decisoes"],
            [{"event_id": "canvas:pucminas:course:00000000:assignment:1",
              "decisao": "nova_no_diario"}],
        )
        self.assertEqual(relatorio["envio_whatsapp"], "desabilitado")
        self.assertEqual(relatorio["entrega"], {"habilitada": False, "chamado": False, "status": []})
        self.assertEqual(relatorio["delivery"], relatorio["entrega"])

        coleta = relatorio["coleta"]
        self.assertEqual(set(coleta), {"planner", "ofertas_consultadas", "assignments", "falhas"})
        self.assertEqual(set(coleta["planner"]), {"status", "estado"})
        self.assertEqual(coleta["planner"]["status"], 200)
        self.assertEqual(coleta["planner"]["estado"], "vazio_confirmado")
        self.assertEqual(coleta["ofertas_consultadas"], 1)
        self.assertEqual(coleta["assignments"], 1)
        self.assertEqual(coleta["falhas"], [])

        # Nada de segredo no stdout emitido.
        self.assertNotIn("token", linha.casefold())

    # --------------------------------------- schema Relatorio.json() (rodada)

    def test_relatorio_json_congelado_em_12_chaves(self):
        # O shape de 12 chaves do plano existe, mas no caminho rodada:
        # execucao.py devolve relatorio.json() e runtime.py o imprime com a
        # chave "codigo". Aqui o schema é congelado direto no dataclass.
        relatorio = Relatorio(iniciado_em="2026-01-01T00:00:00+00:00", modo="sombra")
        payload = relatorio.json()
        self.assertEqual(set(payload), CHAVES_RELATORIO_JSON)
        self.assertEqual(payload["iniciado_em"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(payload["modo"], "sombra")
        self.assertEqual(payload["estado"], "iniciada")
        self.assertEqual(payload["ofertas"], 0)
        self.assertEqual(payload["ofertas_com_falha"], [])
        self.assertEqual(payload["atividades"], 0)
        self.assertIs(payload["linha_de_base"], False)
        self.assertEqual(payload["eventos"], [])
        self.assertEqual(payload["entrega"], {})
        self.assertEqual(payload["agenda_manual"], {})
        self.assertEqual(payload["coleta"], {})
        self.assertIsNone(payload["erro"])
        # Cópia defensiva: mutar o snapshot não corrompe o relatório.
        payload["ofertas_com_falha"].append("x")
        self.assertEqual(relatorio.ofertas_com_falha, [])


if __name__ == "__main__":
    unittest.main()
