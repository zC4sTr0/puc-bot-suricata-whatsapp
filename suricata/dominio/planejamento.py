"""Planejamento puro de uma rodada da Suricata."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ..storage.persistencia_rodada import RETENCAO
from .publico import (BRASILIA, Atividade, anuncio_de_agora, anuncio_relevante, decidir, eh_dia_de_aula,
                      expira_em, HORA_AVISO_PROVA, HORA_VESPERA, SILENCIO, dias_relevantes, montar_vespera,
                      provas_de_amanha, quando_importa, precisa_lembrete, texto_anuncio, texto_aviso_prova,
                      texto_lembrete, texto_mudou, texto_novo)

if TYPE_CHECKING:
    # Anuncio vive em rodada.coleta; import direto criaria ciclo
    # (rodada/__init__ importa planejamento). Uso só em anotações.
    from ..rodada.coleta import Anuncio


@dataclass
class Evento:
    tipo: str  # novo | mudou | anuncio | aviso_prova | vespera
    event_id: str
    texto: str
    expira_em: str | None = None
    atividade: Atividade | None = None
    disponivel_em: str | None = None

    @classmethod
    def de_atividade(cls, tipo: str, a: Atividade, agora: datetime | None = None,
                     todas: list[Atividade] | None = None) -> "Evento":
        if tipo == "novo":
            event_id, texto = f"grupo:novo:{a.chave}", texto_novo(a, agora, todas)
        elif tipo == "mudou":
            event_id, texto = f"grupo:mudou:{a.chave}:{a.agenda}", texto_mudou(a)
        else:
            event_id, texto = f"grupo:lembrete:{a.chave}:{a.unlock_at.isoformat()}", texto_lembrete(a)
        return cls(tipo, event_id, texto, expira_em(a, tipo), a)

def planejar(atividades: list[Atividade], memoria: dict[str, Any], agora: datetime,
             anuncios: list[Anuncio] | None = None,
             extras: list[Atividade] | None = None) -> tuple[list[Evento], bool]:
    """Decide os eventos da rodada e atualiza ``memoria`` (sem efeito externo)."""
    linha_de_base = not memoria.get("linha_de_base_em")
    eventos: list[Evento] = []
    vistos: dict[str, str] = memoria.setdefault("anuncios", {})
    for anuncio in anuncios or []:
        if anuncio.id in vistos:
            continue
        vistos[anuncio.id] = agora.isoformat()
        # A primeira rodada com anúncios também é linha de base deles. Só recado de prova/quiz
        # que fala de hoje ou amanhã (ex.: "a prova de amanhã foi adiada").
        if not linha_de_base and memoria.get("anuncios_desde") \
                and anuncio_relevante(anuncio.titulo, anuncio.mensagem) \
                and anuncio_de_agora(anuncio.titulo, anuncio.mensagem, agora):
            eventos.append(Evento("anuncio", f"grupo:anuncio:{anuncio.curso_id}:{anuncio.id}",
                                  texto_anuncio(anuncio.curso, anuncio.titulo, anuncio.mensagem, anuncio.url)))
    if anuncios is not None:
        memoria.setdefault("anuncios_desde", agora.isoformat())
        limite_anuncios = agora - timedelta(days=30)
        for chave in [c for c, v in vistos.items() if datetime.fromisoformat(v) < limite_anuncios]:
            del vistos[chave]
    itens: dict[str, dict[str, Any]] = memoria.setdefault("itens", {})
    for a in atividades:
        decisao = decidir(a, agora)
        registro = itens.get(a.chave)
        novo = False
        dias_agora = sorted(d.isoformat() for d in dias_relevantes(a))
        if registro is None:
            registro = itens[a.chave] = {"agenda": a.agenda, "tipo": a.tipo, "lembretes": []}
            # Publicação só vira aviso se for surpresa (hoje, ou amanhã sem véspera pela frente).
            if not linha_de_base and decisao == "alertar":
                evento = Evento.de_atividade("novo", a, agora, atividades + list(extras or []))
                inicio = _inicio_janela_novidade(a, agora)
                evento.disponivel_em = inicio.astimezone(timezone.utc).isoformat() if inicio else None
                eventos.append(evento)
                registro["novo_em"] = agora.isoformat()
                if evento.disponivel_em:
                    registro["novidade_pendente"] = True
                novo = True
        elif registro.get("agenda") != a.agenda:
            registro["agenda"] = a.agenda
            dias_antes = {date.fromisoformat(d) for d in registro.get("dias", [])}
            # Mudança só importa se envolve hoje/amanhã — antes OU depois (ex.: prova de amanhã adiada).
            if decisao != "ignorar_fechado" and (decisao == "alertar" or quando_importa(dias_antes, agora)):
                eventos.append(Evento.de_atividade("mudou", a))
        elif registro.get("novidade_pendente") and decisao != "ignorar_fechado":
            # Uma descoberta noturna não pode desaparecer só porque uma
            # rodada anterior não conseguiu materializar o outbox.
            evento = Evento.de_atividade("novo", a, agora, atividades + list(extras or []))
            inicio = _inicio_janela_novidade(a, agora)
            evento.disponivel_em = inicio.astimezone(timezone.utc).isoformat() if inicio else None
            eventos.append(evento)
            novo = True
        registro["dias"] = dias_agora
        registro["visto_em"] = agora.isoformat()
        # D32: lembrete ~15 min antes de um quiz CONHECIDO abrir (substitui D30).
        if precisa_lembrete(a, agora):
            marca = a.unlock_at.isoformat()
            if marca not in registro["lembretes"]:
                registro["lembretes"].append(marca)
                # Publicação avisada há pouco (inclusive a que esperou a madrugada) já traz o horário.
                novo_recente = novo or (registro.get("novo_em") and
                                        agora - datetime.fromisoformat(registro["novo_em"]) < timedelta(hours=6))
                if not novo_recente:
                    eventos.append(Evento.de_atividade("lembrete", a))
    limite = agora - RETENCAO
    for chave in [c for c, r in itens.items() if datetime.fromisoformat(r["visto_em"]) < limite]:
        del itens[chave]
    # A véspera também conta com o que foi anotado em aula e ainda não está no Canvas.
    todas = atividades + list(extras or [])
    novidades_no_ciclo = {e.atividade.chave for e in eventos
                          if e.tipo == "novo" and e.atividade is not None}
    for vespera in (planejar_aviso_prova(todas, memoria, agora),
                    planejar_vespera(todas, memoria, agora,
                                     ja_mencionadas_extra=novidades_no_ciclo)):
        if vespera is not None:
            eventos.append(vespera)
    if linha_de_base:
        memoria["linha_de_base_em"] = agora.isoformat()
    return eventos, linha_de_base

def _chaves(valor: Any) -> set[str]:
    """Memória antiga guardava "enviado"/"sem_prova"; a nova guarda a lista de chaves."""
    return {str(v) for v in valor} if isinstance(valor, list) else set()


def _limite_manha(amanha) -> str:
    limite = datetime.combine(amanha, datetime.min.time(), tzinfo=BRASILIA) + timedelta(hours=7)
    return limite.astimezone(timezone.utc).isoformat()


def _inicio_janela_novidade(atividade: Atividade, agora: datetime) -> datetime | None:
    """Retorna quando uma novidade não urgente pode sair, sempre em BRT.

    A data do evento vence a hora da detecção: no próprio dia a novidade é
    imediata; amanhã, descoberta entre 07:00 e 11:59, também é imediata;
    nos demais casos aguarda o próximo marco operacional (18:00 ou 07:00).
    O helper é deliberadamente conservador para dados sem datas.
    """
    local = agora.astimezone(BRASILIA)
    hoje = local.date()
    dias = dias_relevantes(atividade)
    if hoje in dias:
        # Novidade do próprio dia é imediata durante a janela externa. Depois
        # do corte ela continua sendo descartável, não uma novidade matinal.
        if 7 <= local.hour < 21:
            return None
        if local.hour < 7:
            return datetime.combine(hoje, datetime.min.time(), tzinfo=BRASILIA).replace(hour=7)
        return None
    amanha = hoje + timedelta(days=1)
    if amanha not in dias:
        return None
    if local.hour >= 18:
        return datetime.combine(amanha, datetime.min.time(), tzinfo=BRASILIA).replace(hour=7)
    if local.hour < 7:
        return datetime.combine(hoje, datetime.min.time(), tzinfo=BRASILIA).replace(hour=7)
    if 12 <= local.hour < 18:
        return datetime.combine(hoje, datetime.min.time(), tzinfo=BRASILIA).replace(hour=18)
    return None


def janela_novidade(atividade: Atividade, agora: datetime) -> str:
    """Classifica a janela BRT da novidade: imediata, 18h, matinal ou silêncio.

    A hora da descoberta define a janela; 07:00 é apenas o horário de
    entrega, não um requisito da atividade.
    """
    local = agora.astimezone(BRASILIA)
    dias = dias_relevantes(atividade)
    hoje = local.date()
    if local.hour < 7:
        return "silencio"
    if hoje in dias and local.hour < 21:
        return "imediata"
    if hoje + timedelta(days=1) in dias and 7 <= local.hour < 12:
        return "imediata"
    if hoje + timedelta(days=1) in dias and 12 <= local.hour < 18:
        return "18h"
    if hoje + timedelta(days=1) in dias and local.hour >= 18:
        return "07h"
    return "silencio"

def planejar_aviso_prova(atividades: list[Atividade], memoria: dict[str, Any], agora: datetime) -> Evento | None:
    """Aviso extra às 12:00 da véspera, só quando amanhã (dia de aula) tem prova ou quiz.

    Janela 12:00–17:59: depois disso a véspera das 18:00 já cobre. Uma decisão por data.
    """
    local = agora.astimezone(BRASILIA)
    amanha = local.date() + timedelta(days=1)
    decididos: dict[str, str] = memoria.setdefault("avisos_prova", {})
    if not HORA_AVISO_PROVA <= local.hour < HORA_VESPERA or not eh_dia_de_aula(amanha) \
            or amanha.isoformat() in decididos:
        return None
    texto = texto_aviso_prova(atividades, amanha, agora)
    # Guarda QUAIS provas saíram ao meio-dia: as 18:00 não as repetem, mas incluem as publicadas depois.
    decididos[amanha.isoformat()] = [a.chave for a in provas_de_amanha(atividades, amanha, agora)] if texto else []
    for chave in sorted(decididos)[:-14]:
        del decididos[chave]
    if texto is None:
        return None
    return Evento("aviso_prova", f"grupo:aviso-prova:{amanha.isoformat()}", texto, _limite_manha(amanha))

def planejar_vespera(atividades: list[Atividade], memoria: dict[str, Any], agora: datetime,
                     ja_mencionadas_extra: set[str] | None = None) -> Evento | None:
    """Mensagem das 18:00: amanhã (se é dia de aula) + antecedência de matéria pesada (qualquer dia).

    Qualquer rodada entre 18:00 e 22:59 serve (tolerante a rodada perdida); a memória
    garante uma decisão por data, e o texto não é recalculado depois de decidido.
    """
    local = agora.astimezone(BRASILIA)
    amanha = local.date() + timedelta(days=1)
    vesperas: dict[str, str] = memoria.setdefault("vesperas", {})
    # 18:00–22:59: a partir das 23:00 é silêncio, e o resumo expiraria antes de sair.
    if not HORA_VESPERA <= local.hour < SILENCIO[0] or amanha.isoformat() in vesperas:
        return None
    chegando: dict[str, str] = memoria.setdefault("chegando", {})
    adiantadas_mem: dict[str, str] = memoria.setdefault("adiantadas", {})
    texto, citadas, adiantadas = montar_vespera(
        atividades, amanha, agora,
        amanha_tem_aula=eh_dia_de_aula(amanha),
        ja_avisadas_meio_dia=_chaves(memoria.get("avisos_prova", {}).get(amanha.isoformat())),
        ja_mencionadas=set(chegando) | set(ja_mencionadas_extra or ()),
        ja_adiantadas=set(adiantadas_mem))
    vesperas[amanha.isoformat()] = "enviada" if texto else "nada_a_dizer"
    for chave in sorted(vesperas)[:-14]:  # guarda só as duas últimas semanas
        del vesperas[chave]
    for memoria_itens, chaves in ((chegando, citadas), (adiantadas_mem, adiantadas)):
        for chave in chaves:
            memoria_itens[chave] = amanha.isoformat()
        limite_mem = (amanha - timedelta(days=30)).isoformat()
        for chave in [c for c, d in memoria_itens.items() if d < limite_mem]:
            del memoria_itens[chave]
    if texto is None:
        return None
    limite = datetime.combine(amanha, datetime.min.time(), tzinfo=BRASILIA) + timedelta(hours=7)
    return Evento("vespera", f"grupo:vespera:{amanha.isoformat()}", texto, limite.astimezone(timezone.utc).isoformat())

_LISTA_URGENTE = re.compile(r"(?<!\w)(lista|exerc[ií]cios?)(?!\w)", re.IGNORECASE)


def _pode_aguardar_07h(evento: Evento, agora: datetime) -> bool:
    """Única exceção: novidade do Canvas claramente marcada para hoje."""
    atividade = evento.atividade
    if (evento.tipo != "novo" or atividade is None or atividade.fonte != "canvas"
            or atividade.unlock_at is None or atividade.fecha is None):
        return False
    descoberta_local = agora.astimezone(BRASILIA)
    hoje = descoberta_local.date()
    # A elegibilidade matinal nasce do aviso das 18:00 anterior: depois dele,
    # a atividade do dia seguinte fica fora dos avisos e pode atravessar 21:00.
    if descoberta_local.hour >= 18:
        dia_da_manha = hoje + timedelta(days=1)
    elif descoberta_local.hour < 7:
        dia_da_manha = hoje
    else:
        return False
    reconhecida = atividade.tipo in {"quiz", "avaliacao"} or bool(_LISTA_URGENTE.search(atividade.titulo))
    inicio = atividade.unlock_at.astimezone(BRASILIA).date()
    fim = atividade.fecha.astimezone(BRASILIA).date()
    return (reconhecida and inicio == dia_da_manha == fim
            and atividade.fecha > agora)
