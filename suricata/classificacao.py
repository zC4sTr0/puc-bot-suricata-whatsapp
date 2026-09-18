"""Classificação e normalização de atividades públicas da Suricata.

Extração estrutural de ``publico.py``: normalização de texto, entidade
``Atividade``, classificação de tipo e linha de estudo. Funções puras, sem
relógio, sem I/O e sem nada pessoal (I14): só fatos citados no Canvas.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

# D13: sem envio pelo Canvas + nome de prova = avaliação; F30: Khan etc. não é prova.
_NOME_PROVA = re.compile(r"(?<!\w)(prova|avaliacao|exame|p[1-4]|reavaliacao|recuperacao)(?!\w)")
_TAG = re.compile(r"<[^>]*>")
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn")


def _limpo(texto: object) -> str:
    return re.sub(r"\s+", " ", _CONTROLE.sub("", _TAG.sub("", str(texto or "")))).strip()


def data(valor: object) -> datetime | None:
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Atividade:
    curso_id: str
    curso: str
    assignment_id: str
    titulo: str
    tipo: str  # quiz | avaliacao | tarefa
    unlock_at: datetime | None
    due_at: datetime | None
    lock_at: datetime | None
    pontos: float | None
    url: str
    fonte: str = "canvas"  # "canvas" | "caderno" (anotado em aula, agenda_manual)
    estudo: str = ""  # linha curta de livro/capítulo/exercícios citados na tarefa (resumo_estudo)

    @property
    def chave(self) -> str:
        return f"{self.curso_id}:{self.assignment_id}"

    @property
    def fecha(self) -> datetime | None:
        return self.lock_at or self.due_at

    @property
    def agenda(self) -> str:
        """Versão do horário: muda só quando abertura/prazo/fechamento mudam."""
        partes = [d.isoformat() if d else "-" for d in (self.unlock_at, self.due_at, self.lock_at)]
        return hashlib.sha256("|".join(partes).encode()).hexdigest()[:12]


def classificar_tipo(*, quiz_id: object, is_quiz_lti: bool, submission_types: tuple[str, ...], titulo: str) -> str:
    if quiz_id is not None or is_quiz_lti:
        return "quiz"  # F04: Classic (quiz_id) e New Quizzes (LTI)
    if tuple(submission_types) == ("none",) and _NOME_PROVA.search(_sem_acento(titulo)):
        return "avaliacao"
    return "tarefa"


def nome_curto(curso: str) -> str:
    """'Computabilidade - Ciência de Dados … - 2026/2' → 'Computabilidade'."""
    return _limpo(curso).split(" - ")[0].strip()


def _contar_itens(trecho: str) -> int | None:
    """'3, 4, 6, 16 e 17' → 5; '1, 3 a 5, 10' → 5; '4.1, 4.2, 4.4 a 4.6' → 5. None se não entender."""
    total = 0
    for parte in re.split(r",|\be\b", trecho):
        parte = re.sub(r"\(.*?\)", "", parte).strip().rstrip(".").strip()
        if not parte:
            continue
        faixa = re.fullmatch(r"(\d+)(?:\.(\d+))?\s+a\s+(\d+)(?:\.(\d+))?", parte)
        if faixa:
            inicio = int(faixa.group(2) or faixa.group(1))
            fim = int(faixa.group(4) or faixa.group(3))
            if fim < inicio:
                return None
            total += fim - inicio + 1
        elif re.fullmatch(r"\d+(?:\.\d+)?", parte):
            total += 1
        else:
            return None
    return total or None


def resumo_estudo(descricao: str) -> str:
    """Linha curta 'Gersting · cap. 4 · pp. 205–227 · 14 exercícios' a partir da descrição da tarefa.

    Só dados citados no Canvas (I14): autor do livro, capítulos, páginas e quantos exercícios são
    para entregar. Vazio quando a descrição não segue o padrão (nunca inventa).
    """
    texto = re.sub(r"\s+", " ", descricao or "")
    if not texto:
        return ""
    corte = re.search(r"Exerc[íi]cios complementares", texto, flags=re.I)
    inicio = re.search(r"Exerc[íi]cios da lista:?", texto, flags=re.I)
    if not inicio:
        return ""
    lista = texto[inicio.end():corte.start() if corte and corte.start() > inicio.end() else len(texto)]
    cabeca = texto[:inicio.start()]
    livros = re.findall(r"\[\d\]\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}),", cabeca)
    if len(set(livros)) > 1:
        # Vários livros: capítulos e contagem ficam ambíguos; diz só quais são.
        nomes = list(dict.fromkeys(nome.capitalize() for nome in livros))
        return f"{len(nomes)} livros: {', '.join(nomes)}"
    autores = re.findall(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}),\s+[A-ZÁÉÍÓÚ][a-záéíóúâêôãõç]", cabeca)
    partes = [autores[0].capitalize()] if autores else []
    capitulos = list(dict.fromkeys(re.findall(r"Cap[íi]tulo\s+(\d+(?:\.\d+)?)", lista, flags=re.I)))
    if capitulos:
        partes.append("cap. " + ", ".join(capitulos))
    paginas = [int(n) for par in re.findall(r"p[áa]ginas?\s+(\d+)(?:\s*(?:a|e)\s*(\d+))?", lista, flags=re.I)
               for n in par if n]
    if paginas:
        partes.append(f"pp. {min(paginas)}–{max(paginas)}" if max(paginas) != min(paginas) else f"p. {paginas[0]}")
    contagens = [_contar_itens(t) for t in re.findall(
        r"(?:exerc[íi]cios?|problemas? pr[áa]ticos?)\s+([\d.,\s()a-zA-Záéíóúâêôãõç]+?)(?=Cap[íi]tulo|Livro|$)",
        lista, flags=re.I)]
    if contagens and all(c is not None for c in contagens):
        total = sum(contagens)
        partes.append(f"{total} exercício{'s' if total > 1 else ''}")
    return " · ".join(partes) if len(partes) >= 2 else ""


def atividade_de(assignment, curso_id: str, curso: str) -> Atividade:
    titulo = _limpo(assignment.name) or "sem título"
    return Atividade(
        curso_id=str(curso_id), curso=nome_curto(curso) or str(curso_id), assignment_id=str(assignment.id),
        titulo=titulo,
        tipo=classificar_tipo(quiz_id=assignment.quiz_id, is_quiz_lti=assignment.is_quiz_lti,
                              submission_types=assignment.submission_types, titulo=titulo),
        unlock_at=data(assignment.unlock_at), due_at=data(assignment.due_at), lock_at=data(assignment.lock_at),
        pontos=assignment.points_possible, url=assignment.html_url,
        estudo=resumo_estudo(getattr(assignment, "description", "")),
    )


__all__ = ["Atividade", "atividade_de", "classificar_tipo", "data", "nome_curto", "resumo_estudo"]
