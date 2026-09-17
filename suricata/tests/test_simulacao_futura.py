"""Previsão offline com Canvas congelado: nunca chama a ponte WhatsApp."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from suricata.publico import Atividade, BRASILIA
from suricata.rodada import Coleta, executar, planejar, planejar_vespera
from suricata.storage.gcs import ObjetosLocais


class PonteProibida:
    def __init__(self) -> None:
        self.chamadas = 0

    def enviar_lote(self, *args, **kwargs):
        self.chamadas += 1
        raise AssertionError("simulação não pode chamar a ponte")


class CanvasProibido:
    def __getattr__(self, nome):
        raise AssertionError(f"simulação não pode consultar Canvas: {nome}")


def brt(dia: int, hora: int = 0, minuto: int = 0) -> datetime:
    return datetime(2026, 9, dia, hora, minuto, tzinfo=BRASILIA)


def atividade(titulo: str, tipo: str, inicio: datetime | None, fim: datetime | None,
              identificador: str, pontos: float = 1.0) -> Atividade:
    return Atividade(
        curso_id="292189", curso="Introdução à Computação", assignment_id=identificador,
        titulo=titulo, tipo=tipo, unlock_at=inicio, due_at=fim, lock_at=fim,
        pontos=pontos, url=f"https://canvas.test/{identificador}", fonte="canvas",
    )


class SimulacaoFuturaTests(unittest.TestCase):
    def test_caminho_do_job_com_relogio_avancado_persiste_memoria_sem_entrega(self):
        """O caminho de produção é exercitado, mas todos os efeitos externos são proibidos."""
        atividades = [
            atividade("Lista 1", "tarefa", brt(16), brt(16, 23, 59), "job-lista-1", 7.0),
            atividade("Prova 1", "avaliacao", brt(16), brt(16, 23, 59), "job-prova-1", 25.0),
            atividade("Prova 2", "avaliacao", None, brt(18, 19), "job-prova-2", 30.0),
            atividade("Lista 5: Conjuntos", "tarefa", None, brt(21, 23, 59), "job-lista-5", 1.5),
        ]
        coleta = Coleta(atividades=atividades, ofertas=1, falhas=[], anuncios=[])
        ponte = PonteProibida()
        canvas = CanvasProibido()
        eventos_por_horario: dict[str, list[str]] = {}

        with tempfile.TemporaryDirectory() as pasta:
            objetos = ObjetosLocais(Path(pasta))
            inicio = brt(15, 7)
            for indice in range(7 * 24 * 6):
                instante = inicio + timedelta(minutes=10 * indice)
                codigo, relatorio = executar(
                    objetos=objetos, canvas=canvas, entrega_ligada=False,
                    grupo_jid=None, ponte=ponte, agora=lambda instante=instante: instante,
                    coleta_pronta=coleta,
                )
                self.assertEqual(codigo, 0)
                eventos = relatorio["eventos"]
                if eventos:
                    eventos_por_horario[instante.isoformat()] = [e["tipo"] for e in eventos]
                    print(f"\n[{instante.strftime('%d/%m %H:%M BRT')}] PREVISÃO PELO CAMINHO DO JOB:")
                    for evento in eventos:
                        print(evento["texto"])

            self.assertGreaterEqual(len(eventos_por_horario), 4)
            self.assertIn("aviso_prova", eventos_por_horario[brt(15, 12).isoformat()])
            # Sem entrega, a novidade não é consumida pela memória e pode
            # reaparecer; o resumo não substitui o evento imediato.
            self.assertIn("novo", eventos_por_horario[brt(15, 18).isoformat()])
            self.assertIn("aviso_prova", eventos_por_horario[brt(17, 12).isoformat()])
            self.assertNotIn("vespera", eventos_por_horario.get(brt(16, 18).isoformat(), []))
            self.assertNotIn("vespera", eventos_por_horario.get(brt(18, 18).isoformat(), []))
            self.assertIn("novo", eventos_por_horario[brt(20, 18).isoformat()])
            self.assertTrue((Path(pasta) / "grupo" / "memoria.json").exists())
            memoria = json.loads((Path(pasta) / "grupo" / "memoria.json").read_text(encoding="utf-8"))
            self.assertNotIn("vesperas", memoria)
            self.assertEqual(ponte.chamadas, 0)

    def test_canvas_congelado_imprime_previsao_e_nao_entrega(self):
        # Snapshot fixo: nenhuma atividade/anúncio muda durante a simulação.
        atividades = [
            atividade("Lista 1", "tarefa", brt(16), brt(16, 23, 59), "lista-1", 7.0),
            atividade("Prova 1", "avaliacao", brt(16), brt(16, 23, 59), "prova-1", 25.0),
            atividade("Prova 2", "avaliacao", None, brt(18, 19), "prova-2", 30.0),
            atividade("Lista 5: Conjuntos", "tarefa", None, brt(21, 23, 59), "lista-5", 1.5),
        ]
        memoria: dict = {}
        ponte = PonteProibida()

        # A primeira rodada registra a fotografia congelada como linha de base.
        eventos, linha_de_base = planejar(atividades, memoria, brt(15, 12), anuncios=[])
        self.assertTrue(linha_de_base)
        self.assertEqual([evento.tipo for evento in eventos], ["aviso_prova"])
        print("\n[15/09 12:00 BRT] PREVISÃO:")
        print(eventos[0].texto)

        previsao: list[tuple[str, list[str]]] = []
        for instante in (brt(15, 18), brt(16, 18), brt(17, 18), brt(18, 18), brt(19, 18), brt(20, 18)):
            evento = planejar_vespera(atividades, memoria, instante)
            textos = [] if evento is None else [evento.texto]
            previsao.append((instante.strftime("%d/%m %H:%M"), textos))
            if textos:
                print(f"\n[{instante.strftime('%d/%m %H:%M BRT')}] PREVISÃO:")
                print(textos[0])
            else:
                print(f"\n[{instante.strftime('%d/%m %H:%M BRT')}] nenhuma mensagem nova")

        self.assertTrue(previsao[0][1])  # véspera de 16/09
        self.assertEqual(previsao[1][1], [])  # Prova 2 já foi citada em "Próximos dias"
        self.assertEqual(previsao[2][1], [])  # estado direto já marcou a antecedência
        self.assertEqual(previsao[3][1], [])
        self.assertEqual(previsao[4][1], [])
        self.assertTrue(previsao[5][1])  # amanhã é 21/09; Lista 5 volta como item do dia seguinte
        self.assertEqual(ponte.chamadas, 0)


if __name__ == "__main__":
    unittest.main()
