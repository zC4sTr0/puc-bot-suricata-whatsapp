"""Composição da rodada de produção da Suricata.

O módulo mantém a fachada histórica e liga ambiente, Canvas, storage e ponte;
as etapas de coleta, planejamento e execução vivem em módulos próprios.

Uma execução do Cloud Run Job (a cada 10 min, 24/7):

1. adquire o lease ``locks/rodada.lock`` (CAS; abandonado após 6 min);
2. lista as ofertas ativas e varre ``assignments`` de cada uma (sem planner:
   ele omite quiz sem prazo, F37), exceto Coordenação;
3. primeira rodada = linha de base: registra tudo que existe, não anuncia;
4. decide o que vale falar no grupo (D33–D34, ``tests/test_discricao.py``): publicação e mudança só se
   forem surpresa (hoje, ou amanhã sem véspera pela frente); recado do professor só de prova/quiz de
   hoje/amanhã; ``aviso_prova`` às 12:00 da véspera (só com prova/quiz); ``vespera`` às 18:00 (só se
   amanhã tem algo); ``lembrete`` ~15 min antes de quiz-relâmpago; nada entre 23:00 e 07:00;
5. com entrega ligada: grava os eventos no outbox **antes** de enviar, envia
   todos os pendentes (inclusive de rodadas anteriores) e só marca ``sent`` com
   ACK do servidor. Sem ACK volta a ``pending`` e sai de novo com o mesmo
   ``message_id`` até confirmar ou expirar (D22: nunca ``unknown``);
6. grava a memória e o relatório; libera o lease.

Códigos de saída: 0 ok (inclui lease ocupado) · 3 coleta sem evidência ·
5 armazenamento · 6 sessão WhatsApp inválida (eventos continuam pendentes).
Uma rodada que não coletou **nunca** sai com 0.
"""
from __future__ import annotations

import sys

from . import agenda_manual
from .canvas import CanvasClient
from .coleta import Coleta, ColetaIndisponivel, EXCLUIDAS, coletar
from .configuracao import Destino, destinos_do_ambiente
from .lease_rodada import LEASE, LEASE_MINUTOS, _campo_json
from .persistencia_rodada import OUTBOX, OutboxSincronizado
from .planejamento import (_LISTA_URGENTE, Evento, _chaves, _limite_manha, _pode_aguardar_07h,
                           planejar, planejar_aviso_prova, planejar_vespera)
from .publico import Atividade, texto_vespera
from .execucao import (MAX_LOTE, _agora_vivo, _autorizacao_corte, _autorizados_persistidos,
                       _corte_21h, _janela_manha, _todos, agrupar_envios, entregar,
                       executar, executar_destinos, Relatorio)
from .runtime import run_from_environment

MEMORIA = "grupo/memoria.json"
RELATORIO = "grupo/ultima-rodada.json"

# --------------------------------------------------------------------------
# rodada





def main(argv: list[str] | None = None) -> int:
    """Configuração só por ambiente (Cloud Run): nada de segredo em argv."""
    from .storage.gcs import SessaoWhatsApp, construir_objetos
    from .bridge import WhatsAppBridge

    return run_from_environment(
        canvas_factory=CanvasClient,
        destinations_factory=destinos_do_ambiente,
        objects_factory=construir_objetos,
        session_factory=SessaoWhatsApp,
        bridge_factory=WhatsAppBridge,
        single_runner=executar,
        multi_runner=executar_destinos,
    )


if __name__ == "__main__":
    sys.exit(main())
