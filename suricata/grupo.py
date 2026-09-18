"""facade de compatibilidade; implementação em suricata/legacy/."""

from .legacy.grupo import (
    EXCLUIDAS,
    GrupoError,
    EventoGrupo,
    Evento,
    ofertas_elegiveis,
    decidir_grupo,
    anuncio_relevante,
    renderizar_evento,
    renderizar,
    renderizar_dia_grupo,
)

__all__ = [
    "EXCLUIDAS", "GrupoError", "EventoGrupo", "Evento", "ofertas_elegiveis",
    "decidir_grupo", "anuncio_relevante", "renderizar_evento", "renderizar",
    "renderizar_dia_grupo",
]
