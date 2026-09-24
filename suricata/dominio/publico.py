"""Classificação e textos públicos da Suricata (caminho de produção).

Regras:
- Horários sempre em ``America/Sao_Paulo`` (a turma lê Brasília, não UTC).
- Textos **determinísticos**: dependem só da versão do item, nunca do relógio.
  Assim um reenvio com o mesmo ``message_id`` repete exatamente o mesmo texto
  e o outbox aceita o evento como idêntico.
- Nada pessoal: a coleta não pede ``submission``; aqui só entram fatos públicos
  da atividade (título, curso, datas, pontos, link).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from .calendario import (  # noqa: F401 - _pascoa é fachada de compatibilidade
    _pascoa,
    eh_dia_de_aula,
    feriados_nacionais,
)
from .classificacao import (  # noqa: F401 - nomes históricos, reexport deliberado
    Atividade,
    _limpo,
    _sem_acento,
    atividade_de,
    classificar_tipo,
    data,
    nome_curto,
    resumo_estudo,
)
from .horario import BRASILIA

HORA_AVISO_PROVA = 12  # véspera: aviso extra só com prova/quiz amanhã
HORA_VESPERA = 18  # véspera: resumo do dia seguinte
ANTECEDENCIA_LEMBRETE = timedelta(minutes=15)  # > intervalo de 10 min: alguma rodada cai antes
JANELA_CURTA = timedelta(hours=3)
SILENCIO = (23, 7)  # nunca mandar nada entre 23:00 e a ABERTURA (titular, 2026-09-14)
ABERTURA = (7, 30)  # primeiro aviso do dia às 07:30 BRT (titular, 2026-09-24)


def antes_da_abertura(local: datetime) -> bool:
    """Horário local (BRT) antes das 07:30."""
    return (local.hour, local.minute) < ABERTURA


def em_silencio(agora: datetime) -> bool:
    local = agora.astimezone(BRASILIA)
    return local.hour >= SILENCIO[0] or antes_da_abertura(local)


def fim_do_silencio(agora: datetime) -> datetime:
    """Próximas 07:30 (Brasília) a partir de um momento dentro da madrugada."""
    local = agora.astimezone(BRASILIA)
    dia_ = local.date() + timedelta(days=1) if local.hour >= SILENCIO[0] else local.date()
    return datetime(dia_.year, dia_.month, dia_.day, *ABERTURA, tzinfo=BRASILIA)


MAX_CHARS = 1500
DIAS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")

# A normalização, a entidade Atividade e a classificação de tipo vivem em
# ``classificacao``; os nomes históricos continuam importáveis daqui.

# Matérias pesadas recebem antecedência e a linha de estudo (titular, 2026-09-14).
MATERIAS_PESADAS = frozenset({"292184"})  # Computabilidade
ANTECEDENCIA_PESADA = {"tarefa": 2, "quiz": 2, "avaliacao": 3}  # dias antes do prazo/dia da prova


def dias_relevantes(atividade: Atividade) -> set[date]:
    """Dias em que a atividade pede algo do aluno: o dia em que acontece e o dia do prazo."""
    dias = {dia(atividade.fecha)} if atividade.fecha is not None else set()
    provavel = dia_provavel(atividade)
    if provavel is not None:
        dias.add(provavel)
    return dias


def quando_importa(dias: set[date], agora: datetime) -> str | None:
    """``hoje`` / ``amanha`` quando o ritmo normal NÃO cobre a tempo; senão ``None``.

    O ritmo normal é a véspera (12:00 para prova/quiz, 18:00 para tudo) nos dias de aula.
    Entre 07:30 e 11:59, uma novidade de amanhã é avisada imediatamente; depois,
    a véspera cobre o anúncio até o próximo marco (18:00 ou 07:30).
    """
    local = agora.astimezone(BRASILIA)
    hoje = local.date()
    if hoje in dias:
        return "hoje"
    amanha = hoje + timedelta(days=1)
    if amanha in dias and (not antes_da_abertura(local) and local.hour < HORA_AVISO_PROVA
                           or local.hour >= HORA_VESPERA or not eh_dia_de_aula(amanha)):
        return "amanha"
    return None


def decidir(atividade: Atividade, agora: datetime) -> str:
    """Filosofia do grupo: avisar só o que é surpresa e útil agora.

    - ``alertar``: acontece/vence hoje, ou amanhã descoberta entre 07:30 e 11:59,
      sem véspera pela frente; quiz sem data
      nenhuma (disponível já, o quiz-surpresa típico);
    - ``ignorar_fechado``: já passou;
    - ``sem_urgencia``: fica para a véspera/lembrete (ex.: prova de novembro publicada em setembro).
    """
    fecha = atividade.fecha
    if fecha is not None and fecha <= agora:
        return "ignorar_fechado"
    if atividade.tipo == "quiz" and atividade.unlock_at is None and fecha is None:
        return "alertar"
    return "alertar" if quando_importa(dias_relevantes(atividade), agora) else "sem_urgencia"


def precisa_lembrete(atividade: Atividade, agora: datetime) -> bool:
    abre = atividade.unlock_at
    if atividade.tipo != "quiz" or abre is None:
        return False
    if atividade.fecha is not None and atividade.fecha <= agora:
        return False
    # Só quiz de janela curta (quiz-relâmpago, F13): aberto por dias não precisa de lembrete.
    if atividade.fecha is None or atividade.fecha - abre > JANELA_CURTA:
        return False
    return timedelta(0) < abre - agora <= ANTECEDENCIA_LEMBRETE


# --------------------------------------------------------------------------
# textos — assinatura "PUC Bot" com 🎓 (pedido do titular em 2026-09-14; antes "Suricata")
#
# Estilo: frase curta e direta, um emoji por linha no máximo, uma dica (💡) só
# quando ela explica algo que o horário sozinho não deixa óbvio.

ASSINATURA = "🎓 *PUC Bot*"


def pts(pontos: float | None) -> str:
    """' · 25 pts' / ' · 1 pt'; vazio quando o Canvas não informa valor."""
    if not pontos:
        return ""
    return f" · {pontos:g}".replace(".", ",") + (" pt" if pontos == 1 else " pts")


def quando(momento: datetime | None) -> str:
    if momento is None:
        return "—"
    local = momento.astimezone(BRASILIA)
    return f"{DIAS[local.weekday()]} {local:%d/%m %H:%M}"


def hora(momento: datetime) -> str:
    return f"{momento.astimezone(BRASILIA):%H:%M}"


def dia(momento: datetime) -> date:
    return momento.astimezone(BRASILIA).date()


def dia_curto(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d:%d/%m}"


def duracao(inicio: datetime, fim: datetime) -> str:
    minutos = max(0, int((fim - inicio).total_seconds() // 60))
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    if horas < 48:
        return f"{horas} h" + (f" {resto:02d} min" if resto else "")
    return f"{horas // 24} dias"


NOME_TIPO = {"quiz": "quiz", "avaliacao": "prova", "tarefa": "tarefa"}


def dia_provavel(atividade: Atividade) -> date | None:
    """Dia em que a atividade provavelmente acontece (inferência declarada).

    - abre e fecha no mesmo dia → é nesse dia;
    - só tem abertura → é no dia em que abre;
    - prova sem abertura → o dia do prazo.
    """
    abre, fecha = atividade.unlock_at, atividade.fecha
    if abre is not None and (fecha is None or dia(abre) == dia(fecha)):
        return dia(abre)
    if abre is None and fecha is not None and atividade.tipo == "avaliacao":
        return dia(fecha)
    return None


def _titulo(atividade: Atividade) -> str:
    pontos = pts(atividade.pontos)
    return f"📚 {atividade.curso} — {atividade.titulo}{pontos}"


def _dia_inteiro(abre: datetime, fecha: datetime) -> bool:
    a, f = abre.astimezone(BRASILIA), fecha.astimezone(BRASILIA)
    return a.date() == f.date() and (a.hour, a.minute) == (0, 0) and (f.hour, f.minute) >= (23, 59)


def _janela(atividade: Atividade) -> str:
    abre, fecha = atividade.unlock_at, atividade.fecha
    if abre is not None and fecha is not None and abre >= fecha:
        return f"📅 {quando(fecha)}"
    if abre is not None and fecha is not None and _dia_inteiro(abre, fecha):
        return f"📅 {dia_curto(dia(abre))}, o dia todo"
    if abre is not None and fecha is not None:
        fim = hora(fecha) if dia(abre) == dia(fecha) else quando(fecha)
        return f"🔓 {quando(abre)} → 🔒 {fim} ({duracao(abre, fecha)})"
    if abre is not None:
        return f"🔓 abre {quando(abre)}"
    if fecha is not None:
        return f"🔒 até {quando(fecha)}"
    return "🗓️ sem data no Canvas"


def _dica(atividade: Atividade) -> str | None:
    # D37: sem "tudo indica que é…": a data já está na linha de horário; inferência não vira texto.
    return None


def _montar(linhas: list[str | None], atividade: Atividade | None = None) -> str:
    if atividade is not None and atividade.url:
        linhas.append(atividade.url)
    return "\n".join(linha for linha in linhas if linha)[:MAX_CHARS]


def texto_novo(atividade: Atividade, agora: datetime | None = None, todas: list[Atividade] | None = None) -> str:
    """Aviso de publicação-surpresa. Diz QUANDO acontece; o texto é fixado na criação do evento."""
    if agora is not None and em_silencio(agora):
        agora = fim_do_silencio(agora)  # escrito do ponto de vista de quem lê às 07:30
    quando_txt = quando_importa(dias_relevantes(atividade), agora) if agora is not None else None
    sufixo = {"hoje": " hoje", "amanha": " amanhã"}.get(quando_txt or "", "")
    chamada = {"quiz": f"quiz{sufixo} no Canvas!", "avaliacao": f"prova{sufixo} no Canvas!"}.get(
        atividade.tipo, f"entrega{sufixo} no Canvas!")
    if atividade.tipo == "quiz" and atividade.unlock_at is None and atividade.fecha is None:
        chamada = "quiz disponível agora no Canvas!"
    obs = observar(atividade, todas or [], agora) if agora is not None else []
    return _montar([f"🚨 {ASSINATURA}: {chamada}", _titulo(atividade), _janela(atividade), _dica(atividade),
                    f"↳ {' · '.join(obs)}" if obs else None], atividade)


def texto_lembrete(atividade: Atividade) -> str:
    assert atividade.unlock_at is not None
    fim = f" e fecha {hora(atividade.fecha)}" if atividade.fecha is not None else ""
    return _montar([f"⏰ {ASSINATURA}: o quiz abre às {hora(atividade.unlock_at)}{fim}!", _titulo(atividade)],
                   atividade)


def texto_mudou(atividade: Atividade) -> str:
    return _montar([f"🔁 {ASSINATURA}: mudou o horário!", _titulo(atividade), _janela(atividade)], atividade)


# Sem "teste"/"simulado": geram falso alarme ("teste seu código", "simulado de exercícios").
PALAVRAS_ANUNCIO = re.compile(r"(?<!\w)(prova|provas|quiz|quizzes|avaliacao|avaliacoes|"
                              r"recuperacao|reavaliacao|exame)(?!\w)")


def anuncio_relevante(titulo: str, mensagem: str) -> bool:
    """Anúncio do professor que fala de avaliação (palavras inteiras, sem acento)."""
    return bool(PALAVRAS_ANUNCIO.search(_sem_acento(f"{titulo} {mensagem}")))


def texto_anuncio(curso: str, titulo: str, mensagem: str, url: str) -> str:
    corpo = _limpo(mensagem)
    if len(corpo) > 400:
        corpo = corpo[:400].rsplit(" ", 1)[0] + "…"
    linhas = [f"📣 {ASSINATURA} repassa o recado de {nome_curto(curso)}:", f"*{_limpo(titulo)}*", corpo or None]
    if url:
        linhas.append(url)
    return _montar(linhas)


# --------------------------------------------------------------------------
# véspera: 18:00 do dia anterior a um dia de aula

# O calendário letivo (Páscoa, feriados, dia de aula) vive em ``calendario``;
# os nomes históricos continuam importáveis daqui.

def provas_de_amanha(atividades: list[Atividade], amanha: date, agora: datetime) -> list[Atividade]:
    return [a for a in atividades
            if a.tipo in {"avaliacao", "quiz"} and (a.fecha is None or a.fecha > agora) and dia_provavel(a) == amanha]


def anuncio_de_agora(titulo: str, mensagem: str, agora: datetime) -> bool:
    """O recado fala de hoje ou amanhã (palavra ou data dd/mm)? Recado sobre novembro, em setembro, não."""
    texto = _sem_acento(f"{titulo} {mensagem}")
    hoje = agora.astimezone(BRASILIA).date()
    datas = {f"{d:%d/%m}" for d in (hoje, hoje + timedelta(days=1))} | {f"{d.day}/{d.month}" for d in (hoje, hoje + timedelta(days=1))}
    return bool(re.search(r"(?<!\w)(hoje|amanha|agora)(?!\w)", texto)) or any(
        re.search(rf"(?<![\d/]){re.escape(d)}(?![\d])", texto) for d in datas)


def texto_aviso_prova(atividades: list[Atividade], amanha: date, agora: datetime) -> str | None:
    """Aviso extra do meio-dia da véspera: só quando amanhã tem prova ou quiz."""
    provas = sorted(provas_de_amanha(atividades, amanha, agora), key=lambda a: (a.unlock_at or agora, a.titulo))
    blocos: dict[str, list[str]] = {}
    for a in provas:
        if linha := _linha_curta(a, amanha):
            blocos.setdefault(a.curso, []).extend(_com_observacoes(linha, a, atividades, agora, ignorar_mesmo_dia=True))
    if not blocos:
        return None
    total = sum(len(itens) for itens in blocos.values())
    plural = "prova ou quiz" if total > 1 else ("quiz" if provas[0].tipo == "quiz" else "prova")
    linhas = [f"{ASSINATURA} · amanhã ({dia_curto(amanha)}) tem {plural}"]
    for curso, itens in blocos.items():
        linhas += ["", f"📘 *{curso}*", *itens]
    return "\n".join(linhas)[:MAX_CHARS]


_PALAVRA_TIPO = {"quiz": ("quiz",), "avaliacao": ("prova", "avaliacao", "reavaliacao", "exame")}


def _titulo_com_tipo(atividade: Atividade) -> str:
    """'Prova 1' fica 'Prova 1'; 'Big Data' (quiz) vira 'Quiz Big Data'. Nunca 'Prova Prova 1'."""
    palavras = _PALAVRA_TIPO.get(atividade.tipo, ())
    if not palavras or any(p in _sem_acento(atividade.titulo) for p in palavras):
        return atividade.titulo
    return f"{NOME_TIPO[atividade.tipo].capitalize()} {atividade.titulo}"


def _linha_curta(atividade: Atividade, amanha: date) -> str | None:
    """Linha dentro do bloco da matéria (sem repetir o nome da matéria)."""
    abre, fecha = atividade.unlock_at, atividade.fecha
    nome = f"*{_titulo_com_tipo(atividade)}*{pts(atividade.pontos)}"
    if dia_provavel(atividade) == amanha:
        rotulo = {"quiz": "⚡", "avaliacao": "📝", "tarefa": "🎯"}[atividade.tipo]
        if abre is not None and fecha is not None and abre < fecha and fecha - abre <= timedelta(hours=3):
            return f"{rotulo} {nome}, das {hora(abre)} às {hora(fecha)}"
        return f"{rotulo} {nome}"  # D37: o bloco já diz "amanhã"; sem "tudo indica"/"marcada em aula"
    if fecha is not None and dia(fecha) == amanha:
        return f"📌 {nome} — entrega até {hora(fecha)}"
    return None


def _dia_alvo(atividade: Atividade) -> date | None:
    if atividade.tipo == "tarefa":
        return dia(atividade.fecha) if atividade.fecha is not None else None
    return dia_provavel(atividade) or (dia(atividade.fecha) if atividade.fecha is not None else None)


def _linha_adiantar(atividade: Atividade, alvo: date, hoje: date) -> str:
    """Só constata (D36): data e distância. Nunca 'reserve', 'comece', 'revise'."""
    faltam = (alvo - hoje).days
    nome = f"*{_titulo_com_tipo(atividade)}*{pts(atividade.pontos)}"
    if atividade.tipo == "tarefa":
        return f"📌 {nome} — vence {dia_curto(alvo)}, em {faltam} dias"
    rotulo = "📝" if atividade.tipo == "avaliacao" else "⚡"
    return f"{rotulo} {nome} — {dia_curto(alvo)}, em {faltam} dias"


# --------------------------------------------------------------------------
# observações de risco (D36): fatos do calendário que mudam a leitura de um item.
# Nunca ordens. Prioridade: colisão > sequência > depois de pausa > última lista > fecha cedo.


def _pausa_antes(alvo: date, hoje: date) -> str | None:
    """'fim de semana' / 'feriado' / 'feriadão' quando o dia anterior não tem aula.

    Só informa enquanto a pausa ainda não começou: lido no domingo à noite, "logo depois do
    fim de semana" não acrescenta nada.
    """
    dias, d = [], alvo - timedelta(days=1)
    while not eh_dia_de_aula(d) and len(dias) < 6:
        dias.append(d)
        d -= timedelta(days=1)
    if not dias or hoje >= min(dias):
        return None
    feriados = [x for x in dias if x.weekday() < 5]
    if not feriados:
        return "logo depois do fim de semana"
    if len(dias) >= 3:
        return "logo depois do feriadão"
    return f"logo depois do feriado de {feriados[0]:%d/%m}"


def observar(atividade: Atividade, todas: list[Atividade], agora: datetime, maximo: int = 2,
            ignorar_mesmo_dia: bool = False) -> list[str]:
    """Até ``maximo`` observações factuais sobre o item, as mais relevantes primeiro."""
    alvo = _dia_alvo(atividade)
    if alvo is None:
        return []
    abertas = [a for a in todas if a.chave != atividade.chave and (a.fecha is None or a.fecha > agora)]
    provas = [(a, _dia_alvo(a)) for a in abertas if a.tipo in {"avaliacao", "quiz"}]
    obs: list[str] = []
    if atividade.tipo in {"avaliacao", "quiz"}:
        mesmo_dia = [] if ignorar_mesmo_dia else [a for a, d in provas if d == alvo]
        if len(mesmo_dia) == 1:
            obs.append(f"no mesmo dia: {_titulo_com_tipo(mesmo_dia[0])} ({mesmo_dia[0].curso})")
        elif mesmo_dia:
            obs.append(f"no mesmo dia: mais {len(mesmo_dia)} provas/quizzes")
        antes = [a for a, d in provas if d == alvo - timedelta(days=1)]
        depois = [a for a, d in provas if d == alvo + timedelta(days=1)]
        if antes and depois:
            obs.append("provas em 3 dias seguidos")
        elif antes:
            obs.append(f"na véspera tem {_titulo_com_tipo(antes[0])} ({antes[0].curso})")
        elif depois:
            obs.append(f"no dia seguinte tem {_titulo_com_tipo(depois[0])} ({depois[0].curso})")
        if pausa := _pausa_antes(alvo, agora.astimezone(BRASILIA).date()):
            obs.append(pausa)
    else:
        entregas = [] if ignorar_mesmo_dia else [a for a in abertas if a.tipo == "tarefa" and _dia_alvo(a) == alvo]
        if len(entregas) >= 2:
            obs.append(f"no mesmo dia vencem mais {len(entregas)} entregas")
        elif entregas:
            obs.append(f"no mesmo dia vence {_titulo_com_tipo(entregas[0])} ({entregas[0].curso})")
        proxima = min(((a, d) for a, d in provas if a.curso_id == atividade.curso_id and a.tipo == "avaliacao"
                       and d is not None and (d > alvo or (d == alvo and not ignorar_mesmo_dia))
                       and d <= alvo + timedelta(days=7)), key=lambda x: x[1], default=None)
        if proxima:
            outras_listas = [a for a in abertas if a.tipo == "tarefa" and a.curso_id == atividade.curso_id
                             and (d := _dia_alvo(a)) is not None and alvo < d <= proxima[1]]
            if not outras_listas:
                obs.append(f"última entrega antes da {_titulo_com_tipo(proxima[0])} ({dia_curto(proxima[1])})")
    fecha = atividade.fecha
    if fecha is not None and atividade.tipo != "avaliacao" and fecha.astimezone(BRASILIA).hour < 12 \
            and dia_provavel(atividade) != alvo:
        obs.append(f"fecha às {hora(fecha)}, de manhã")
    return obs[:maximo]


def _com_observacoes(linha: str, atividade: Atividade, todas: list[Atividade], agora: datetime,
                     ignorar_mesmo_dia: bool = False) -> list[str]:
    obs = observar(atividade, todas, agora, ignorar_mesmo_dia=ignorar_mesmo_dia)
    return [linha, f"   ↳ {' · '.join(obs)}"] if obs else [linha]


def montar_vespera(atividades: list[Atividade], amanha: date, agora: datetime, *,
                   amanha_tem_aula: bool = True,
                   ja_avisadas_meio_dia: frozenset[str] | set[str] = frozenset(),
                   ja_mencionadas: frozenset[str] | set[str] = frozenset(),
                   ja_adiantadas: frozenset[str] | set[str] = frozenset(),
                   ) -> tuple[str | None, list[str], list[str]]:
    """Mensagem das 18:00, agrupada por matéria. Silêncio (``None``) quando não há o que dizer.

    Seções, nesta ordem e só quando existem:
    1. amanhã (se amanhã é dia de aula), um bloco por matéria;
    2. matéria pesada (``MATERIAS_PESADAS``): lista que vence em 2 dias e prova em 3 dias,
       uma vez por item, em qualquer dia da semana, só constatando data e riscos (D36);
    3. "Chegando": cada prova/quiz dos próximos 6 dias citado uma única vez (só junto de 1 ou 2).
    Devolve (texto, chaves citadas em "Chegando", chaves adiantadas).
    """
    hoje = amanha - timedelta(days=1)
    abertas = [a for a in atividades if a.fecha is None or a.fecha > agora]
    ordem = lambda a: (a.unlock_at or a.fecha or agora, a.titulo)  # noqa: E731
    blocos: dict[str, list[str]] = {}
    for a in sorted(abertas, key=ordem):
        if not amanha_tem_aula or a.chave in ja_avisadas_meio_dia or a.chave in ja_mencionadas:
            continue
        linha = _linha_curta(a, amanha)
        if linha:
            blocos.setdefault(a.curso, []).extend(_com_observacoes(linha, a, abertas, agora, ignorar_mesmo_dia=True))
            if a.curso_id in MATERIAS_PESADAS and a.tipo == "tarefa" and a.estudo:
                blocos[a.curso].append(f"   📖 {a.estudo}")
    adiantar: dict[str, list[str]] = {}
    adiantadas: list[str] = []
    for a in sorted(abertas, key=ordem):
        if a.curso_id not in MATERIAS_PESADAS or a.chave in ja_adiantadas:
            continue
        alvo = _dia_alvo(a)
        if alvo is None or (alvo - hoje).days != ANTECEDENCIA_PESADA[a.tipo]:
            continue
        adiantar.setdefault(a.curso, []).extend(_com_observacoes(_linha_adiantar(a, alvo, hoje), a, abertas, agora))
        if a.tipo == "tarefa" and a.estudo:
            adiantar[a.curso].append(f"   📖 {a.estudo}")
        adiantadas.append(a.chave)
    if not blocos and not adiantar:
        return None, [], []
    proximas, citadas = [], []
    for a in sorted(abertas, key=ordem):
        if a.tipo not in {"quiz", "avaliacao"} or a.chave in ja_mencionadas or a.chave in adiantadas \
                or len(proximas) == 3:
            continue
        quando_dia = _dia_alvo(a)
        if quando_dia is not None and amanha < quando_dia <= amanha + timedelta(days=6):
            proximas.append(f"• {dia_curto(quando_dia)} — {_titulo_com_tipo(a)}{pts(a.pontos)}"
                            f" ({a.curso})")
            citadas.append(a.chave)
    linhas = [f"{ASSINATURA} · amanhã, {dia_curto(amanha)}" if blocos else f"{ASSINATURA} · próximos dias"]
    for curso, itens in blocos.items():
        linhas += ["", f"📘 *{curso}*", *itens]
    if (adiantar or proximas) and blocos:
        linhas += ["", "🔭 *Próximos dias*"]
    for n, (curso, itens) in enumerate(adiantar.items()):
        linhas += ([] if n == 0 and blocos else [""]) + [f"📘 *{curso}*", *itens]
    if proximas:
        linhas += ([""] if adiantar or not blocos else []) + proximas
    return "\n".join(linhas)[:MAX_CHARS], citadas, adiantadas


def texto_vespera(atividades: list[Atividade], amanha: date, agora: datetime) -> str | None:
    return montar_vespera(atividades, amanha, agora)[0]


def texto_lote(textos_novos: list[str]) -> str:
    """Várias surpresas pendentes viram uma mensagem (determinística pela ordem recebida)."""
    blocos = []
    for texto in textos_novos:
        cabeca, *resto = texto.split("\n")
        chamada = cabeca.split(": ", 1)[-1].replace(" no Canvas", "").rstrip("!")
        blocos.append("\n".join([f"*{chamada[:1].upper()}{chamada[1:]}*", *resto]))
    return "\n\n".join([f"🚨 {ASSINATURA}: {len(blocos)} surpresas no Canvas", *blocos])


def expira_em(atividade: Atividade, tipo_evento: str) -> str | None:
    """Até quando o aviso ainda é útil. ``None`` = padrão do outbox (24 h)."""
    if tipo_evento == "lembrete" and atividade.unlock_at is not None:
        limite = atividade.fecha or (atividade.unlock_at + timedelta(minutes=30))
        return limite.astimezone(timezone.utc).isoformat()
    if atividade.fecha is not None:
        return atividade.fecha.astimezone(timezone.utc).isoformat()
    return None


__all__ = ["ASSINATURA", "Atividade", "BRASILIA", "atividade_de", "classificar_tipo", "decidir", "dia_provavel",
           "eh_dia_de_aula", "expira_em", "feriados_nacionais", "precisa_lembrete", "quando", "texto_anuncio",
           "texto_lembrete", "texto_mudou", "texto_novo", "texto_vespera"]
