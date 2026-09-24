"""Suíte de propriedade do planejamento puro (determinística, sem dependências).

Gerador próprio com ``random.Random(SEED)`` fixo — nada de Hypothesis nem
rede: 240 cargas sintéticas de atividades (títulos/datas/tipos variados) por
rodada da suíte. Para toda amostra vale:

(a) nenhuma saída (texto de evento ou memória resultante) contém campo
    privado/token/JID;
(b) ``message_id`` é estável para o mesmo par (destino, event_id);
(c) a janela de envio é fechada: todo timestamp em que o envio seria
    autorizado (fora do silêncio) está dentro de 07:30–20:59 BRT — o corte
    das 21h nunca autoriza envio fora da janela;
(d) idempotência: planejar duas vezes o mesmo estado produz o mesmo
    resultado (eventos e memória).

A seed usada é registrada em ``SEED`` e impressa na execução.
"""
from __future__ import annotations

import copy
import json
import random
import unittest
from datetime import datetime, timedelta, timezone

from suricata.dominio.corte_rodada import _corte_21h
from suricata.dominio.message_id import message_id
from suricata.dominio.planejamento import planejar
from suricata.dominio.publico import BRASILIA, Atividade, em_silencio
from suricata.rodada.coleta import Anuncio

SEED = 20260918
AMOSTRAS = 240
JID = "120363000000000000-1700000000@g.us"

CURSOS = [("292184", "Computabilidade"), ("289837", "Mentoria"), ("276510", "Teoria da Computação"),
          ("281144", "Banco de Dados"), ("295002", "Engenharia de Software")]
PALAVRAS = ["Prova", "quiz relâmpago", "Lista de exercícios", "Trabalho prático", "Seminário",
            "entrega do projeto", "Revisão", "Atividade avaliativa", "lab", "Leitura prévia"]
TIPOS = ["quiz", "avaliacao", "tarefa"]
BASE = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
PROIBIDO = ("SURICATA_", "@g.us", "Bearer ", "stub:", "3EB0", "creds.json")


def _data(aleatorio: random.Random, minimo: int, maximo: int) -> datetime:
    return BASE + timedelta(days=aleatorio.randint(-3, 20),
                            hours=aleatorio.randint(minimo, maximo),
                            minutes=aleatorio.choice([0, 10, 15, 30, 45, 59]))


def _atividade(aleatorio: random.Random, i: int) -> Atividade:
    curso_id, curso = aleatorio.choice(CURSOS)
    titulo = " ".join(aleatorio.sample(PALAVRAS, aleatorio.randint(1, 3)))
    datas = [None if aleatorio.random() < 0.2 else _data(aleatorio, 0, 20) for _ in range(3)]
    return Atividade(curso_id, curso, str(1000 + i), f"{titulo} #{i}",
                     aleatorio.choice(TIPOS), datas[0], datas[1], datas[2],
                     aleatorio.choice([None, 1.0, 3.0, 10.0]),
                     f"https://pucminas.instructure.com/courses/{curso_id}/assignments/{1000 + i}")


def _anuncios(aleatorio: random.Random, atividades: list[Atividade]) -> list[Anuncio] | None:
    sorte = aleatorio.random()
    if sorte < 0.3:
        return None  # rota de anúncios falhou: entrada válida
    saida: list[Anuncio] = []
    for _ in range(aleatorio.randint(0, 2)):
        curso_id, curso = aleatorio.choice(CURSOS)
        saida.append(Anuncio(f"anuncio-{aleatorio.randint(1, 9999)}", curso_id, curso,
                             aleatorio.choice(PALAVRAS), "recado do professor",
                             "https://pucminas.instructure.com/courses/x/discussion_topics/y"))
    _ = atividades
    return saida


def _carga(aleatorio: random.Random, indice: int) -> tuple[list[Atividade], dict, datetime, list[Anuncio] | None]:
    atividades = [_atividade(aleatorio, indice * 10 + j) for j in range(aleatorio.randint(0, 4))]
    memoria: dict = {}
    if aleatorio.random() < 0.5:  # meio de rodada: linha de base já existe
        memoria["linha_de_base_em"] = (BASE - timedelta(days=1)).isoformat()
    agora = _data(aleatorio, 0, 23)
    return atividades, memoria, agora, _anuncios(aleatorio, atividades)


class PropriedadesPlanejamentoTests(unittest.TestCase):
    def test_invariantes_para_todas_as_amostras(self):
        aleatorio = random.Random(SEED)
        verificadas = 0
        for indice in range(AMOSTRAS):
            atividades, memoria, agora, anuncios = _carga(aleatorio, indice)

            # (d) idempotência: mesmo estado de partida ⇒ mesmo resultado
            memoria_a, memoria_b = copy.deepcopy(memoria), copy.deepcopy(memoria)
            eventos, linha = planejar(atividades, memoria_a, agora, anuncios)
            _ = linha
            saidas = [e.texto for e in eventos] + [json.dumps(memoria_a, ensure_ascii=False)]

            # (a) nada privado vaza para as saídas
            for saida in saidas:
                for marca in PROIBIDO:
                    self.assertNotIn(marca, saida, f"amostra {indice}: {marca!r} vazou")

            # (b) message_id estável por (destino, event_id)
            for evento in eventos:
                self.assertEqual(message_id(JID, evento.event_id), message_id(JID, evento.event_id))
                self.assertTrue(message_id(JID, evento.event_id).startswith("3EB0"))

            # (c) janela de envio fechada: autorizado ⇒ 07:30–20:59 BRT;
            # silêncio (23–07:29) e corte 21h bloqueiam todo o resto da noite.
            local = agora.astimezone(BRASILIA)
            if not em_silencio(agora) and not _corte_21h(agora):
                self.assertGreaterEqual((local.hour, local.minute), (7, 30))
                self.assertLessEqual(local.hour, 20)
            self.assertTrue((local.hour >= 21 or (local.hour, local.minute) < (7, 30))
                            == (_corte_21h(agora) or em_silencio(agora)),
                            f"amostra {indice}: bloqueio desalinhado da janela: {local}")

            eventos2, linha2 = planejar(atividades, memoria_b, agora, anuncios)
            _ = linha2
            primeira = [(e.tipo, e.event_id, e.texto, e.expira_em, e.disponivel_em) for e in eventos]
            segunda = [(e.tipo, e.event_id, e.texto, e.expira_em, e.disponivel_em) for e in eventos2]
            self.assertEqual(primeira, segunda, f"amostra {indice}: planejamento não idempotente")
            self.assertEqual(memoria_a, memoria_b)
            verificadas += 1
        print(f"\n[propriedade] seed={SEED} amostras={verificadas}")
        self.assertGreaterEqual(verificadas, 200)

    def test_message_id_estavel_entre_amostras_e_chamadas(self):
        aleatorio = random.Random(SEED + 1)
        vistos: dict[str, str] = {}
        for indice in range(AMOSTRAS):
            atividade = _atividade(aleatorio, 5000 + indice)
            event_id = f"grupo:novo:{atividade.chave}"
            valor = message_id(JID, event_id)
            self.assertEqual(valor, vistos.setdefault(event_id, valor))


if __name__ == "__main__":
    unittest.main()
