"""Execução da rodada Suricata: outbox, entrega e destinos.

Extração estrutural de ``rodada.py``; contratos e ordem de efeitos preservados.
"""
from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..dominio.corte_rodada import (
    _autorizacao_corte,
    _autorizados_persistidos,
    _corte_21h,
    _evento_disponivel,
    _janela_manha,
)
from ..dominio.lotes import (  # noqa: F401 - MAX_LOTE é fachada de compatibilidade
    MAX_LOTE,
    agrupar_envios,
)
from ..dominio.memoria_rodada import comprometer_memoria
from ..dominio.message_id import message_id
from ..dominio.planejamento import Evento, _limite_manha, planejar
from ..dominio.publico import BRASILIA, Atividade, em_silencio
from ..dominio.relatorio import Relatorio
from ..integracao.canvas import CanvasClient
from ..storage.cas import CASConflict, StorageError
from ..storage.lease_rodada import Lease
from ..storage.outbox import OutboxError
from ..storage.persistencia_rodada import OutboxSincronizado
from . import agenda_manual
from .coleta import Coleta, ColetaIndisponivel, coletar
from .config import Destino
from .falhas import registrar_falhas


def _todos(fila: OutboxSincronizado) -> list[dict[str, Any]]:
    return json.loads(fila.caminho.read_text(encoding="utf-8")) if fila.caminho.exists() else []


def _agora_vivo(agora: datetime | Callable[[], datetime]) -> datetime:
    return agora() if callable(agora) else agora


# Predicados do corte das 21h vivem em ``corte_rodada``; os nomes históricos
# continuam importáveis daqui (fachada de compatibilidade de ``rodada``).


def _registrar_eventos(fila: OutboxSincronizado, outbox: Any, grupo_jid: str,
                       eventos: list[Evento], momento: datetime) -> set[str]:
    """Registra os eventos da rodada no outbox e devolve os IDs novos nesta leva."""
    eventos_atuais: set[str] = set()
    for evento in eventos:
        existentes = {registro["event_id"] for registro in _todos(fila)}
        registro = {"event_id": evento.event_id, "message_id": message_id(grupo_jid, evento.event_id),
                    "texto": evento.texto}
        if evento.disponivel_em:
            registro["disponivel_em"] = evento.disponivel_em
        autorizacao = _autorizacao_corte(evento, momento)
        if autorizacao is not None:
            registro["corte_21h"] = autorizacao
        if evento.expira_em:
            registro["expira_em"] = evento.expira_em
        try:
            outbox.adicionar(registro, agora=momento)
        except OutboxError:
            # Mesmo event_id já enfileirado com texto de uma versão anterior (ex.: deploy que mudou
            # o estilo das mensagens): o registro existente vale; nunca travar a rodada por isso.
            if evento.event_id not in {r["event_id"] for r in _todos(fila)}:
                raise
        if evento.event_id not in existentes:
            eventos_atuais.add(evento.event_id)
    return eventos_atuais


def _reivindicar_pendentes(outbox: Any, atual: datetime) -> list[dict[str, Any]]:
    """Reivindica pendentes disponíveis; só ``in_flight`` segue para a ponte."""
    claims = [outbox.reivindicar(p["event_id"], agora=atual)
              for p in outbox.pendentes() if _evento_disponivel(p, atual)]
    return [c for c in claims if c["estado"] == "in_flight"]


def _reconciliar_ack(outbox: Any, envios: list[dict[str, Any]],
                     resposta: Any, resumo: dict[str, Any]) -> list[str]:
    """Confirma ``sent`` somente com ACK válido; qualquer dúvida volta a ``pending``.

    Devolve os ``event_id`` dos envios que ficaram sem ACK (rastro da dead-letter).
    """
    resumo["sessao"] = resposta.get("sessao") if isinstance(resposta, dict) else "erro"
    if isinstance(resposta, dict) and (resposta.get("erro") or resposta.get("detalhe")):
        resumo["erro"] = str(resposta.get("detalhe") or resposta.get("erro"))[:400]
    itens = {r.get("event_id"): r for r in (resposta.get("resultados") or [])} if isinstance(resposta, dict) else {}
    sem_ack: list[str] = []
    for envio in envios:
        item = itens.get(envio["event_id"]) or {}
        ack = (resumo["sessao"] == "ok" and item.get("message_id") == envio["message_id"]
               and item.get("ack") is True and type(item.get("status")) is int and item["status"] >= 2)
        for claim in envio["claims"]:  # um lote confirma todos os eventos que carrega
            outbox.aplicar_resultado(claim["event_id"], attempt_id=claim["attempt_id"],
                                     message_id=claim["message_id"], ack=ack,
                                     status=item.get("status") if ack else None)
            resumo["sent" if ack else "sem_ack"] += 1
        if not ack:
            sem_ack.append(envio["event_id"])
    return sem_ack


def entregar(fila: OutboxSincronizado, ponte: Any, grupo_jid: str, eventos: list[Evento],
             agora: datetime | Callable[[], datetime], atividades: list[Atividade] | None = None) -> dict[str, Any]:
    outbox = fila.outbox
    momento = _agora_vivo(agora)
    # IDs adicionados nesta chamada recebem autorização efêmera às 07:30;
    # isso não depende de qualquer marcador gravado no JSON.
    eventos_atuais: set[str] = set()
    if _corte_21h(momento):
        permitidos = [evento for evento in eventos if _autorizacao_corte(evento, momento)]
        for evento in permitidos:
            registro = {"event_id": evento.event_id, "message_id": message_id(grupo_jid, evento.event_id),
                        "texto": evento.texto, "corte_21h": _autorizacao_corte(evento, momento)}
            limite = datetime.fromisoformat(_limite_manha(momento.astimezone(BRASILIA).date() + timedelta(days=1)))
            registro["expira_em"] = (limite + timedelta(minutes=1)).isoformat()
            try:
                outbox.adicionar(registro, agora=momento)
            except OutboxError:
                if evento.event_id not in {r["event_id"] for r in _todos(fila)}:
                    raise
        autorizados = {evento.event_id for evento in permitidos}
        if atividades is not None:
            autorizados |= _autorizados_persistidos(fila, atividades, momento)
        corte = outbox.cortar_apos_21h(agora=momento, autorizados=autorizados)
        fila.publicar()
        return {"silencio": True, "aguardando": len(outbox.pendentes()), "expirados": corte["expirados"],
                "pendentes_enviados": 0, "sent": 0, "sem_ack": 0, "sessao": None}
    eventos_atuais = _registrar_eventos(fila, outbox, grupo_jid, eventos, momento)
    outbox.recuperar_interrompidos(agora=momento)
    atual = _agora_vivo(agora)
    expirados = []
    if _janela_manha(atual):
        autorizados = _autorizados_persistidos(fila, atividades or [], atual)
        corte = outbox.cortar_apos_21h(
            agora=atual, autorizados=autorizados, eventos_atuais=eventos_atuais
        )
        expirados_count = corte["expirados"]
    else:
        expirados_count = 0
    expirados.extend(outbox.expirar(agora=atual))
    expirados_count += len(expirados)
    if _corte_21h(atual):
        autorizados = _autorizados_persistidos(fila, atividades or [], atual)
        corte = outbox.cortar_apos_21h(agora=atual, autorizados=autorizados)
        fila.publicar()
        return {"silencio": True, "aguardando": len(outbox.pendentes()), "expirados": corte["expirados"],
                "pendentes_enviados": 0, "sent": 0, "sem_ack": 0, "sessao": None}
    if em_silencio(atual):
        # Nunca de madrugada: tudo espera na fila e sai às 07:30 (o que perder o sentido expira).
        fila.publicar()
        return {"silencio": True, "aguardando": len(outbox.pendentes()), "expirados": expirados_count,
                "pendentes_enviados": 0, "sent": 0, "sem_ack": 0, "sessao": None}
    claims = _reivindicar_pendentes(outbox, atual)
    fila.publicar()  # in_flight durável ANTES do efeito externo
    resumo = {"pendentes_enviados": len(claims), "sent": 0, "sem_ack": 0, "expirados": expirados_count,
              "sessao": None}
    if not claims:
        return resumo
    atual = _agora_vivo(agora)
    if _corte_21h(atual):
        autorizados = _autorizados_persistidos(fila, atividades or [], atual)
        corte = outbox.cortar_apos_21h(
            agora=atual, autorizados=autorizados, eventos_atuais=eventos_atuais
        )
        fila.publicar()
        resumo.update({"silencio": True, "pendentes_enviados": 0, "expirados": corte["expirados"], "sessao": None})
        return resumo
    envios = agrupar_envios(claims, grupo_jid)
    try:
        resposta = ponte.enviar_lote(grupo_jid, [{k: e[k] for k in ("event_id", "message_id", "texto")}
                                                 for e in envios])
    except Exception as exc:  # noqa: BLE001 - nada vira sent sem ACK
        resposta = {"sessao": "erro", "resultados": [], "erro": f"{type(exc).__name__}: {exc}"[:400]}
    sem_ack_ids = _reconciliar_ack(outbox, envios, resposta, resumo)
    if sem_ack_ids:
        # Rastro durável da falha (dead-letter): nunca derruba a rodada.
        registrar_falhas(getattr(fila, "objetos", None),
                         [{"etapa": "entrega", "event_id": event_id,
                           "erro": resumo.get("erro") or f"sessao={resumo.get('sessao')}"}
                          for event_id in sem_ack_ids], momento)
    fila.publicar()
    return resumo


def _carregar_memoria(objetos: Any, memoria_nome: str,
                      relatorio: Relatorio) -> tuple[Any, dict] | None:
    """Lê a memória persistida; devolve ``(objeto, memória)`` ou ``None`` se inválida.

    Memória corrompida marca o relatório e não deixa a rodada avançar (fail-closed).
    """
    obj = objetos.ler(memoria_nome)
    try:
        memoria = json.loads(obj.dados) if obj.dados else {}
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        relatorio.estado = "memoria_invalida"
        relatorio.erro = "memória persistida inválida; rodada não avançada"
        return None
    if not isinstance(memoria, dict):
        relatorio.estado = "memoria_invalida"
        relatorio.erro = "memória persistida deve ser um objeto JSON; rodada não avançada"
        return None
    return obj, memoria


def _planejar_rodada(atividades: list, memoria: dict, momento: datetime, coleta: Any,
                     extras: list, relatorio: Relatorio,
                     entrega_ligada: bool) -> tuple[list[Evento], dict, dict]:
    """Transação em memória: nenhuma marca chega ao estado persistido antes do outbox."""
    memoria_planejada = deepcopy(memoria)
    eventos, relatorio.linha_de_base = planejar(atividades, memoria_planejada, momento, coleta.anuncios, extras)
    relatorio.eventos = [{"tipo": e.tipo, "event_id": e.event_id, "texto": e.texto} for e in eventos]
    memoria_comprometida = deepcopy(memoria)
    if relatorio.linha_de_base:
        # A linha de base é inicialização, não consumo de novidade.
        memoria_comprometida["linha_de_base_em"] = memoria_planejada["linha_de_base_em"]
        if entrega_ligada:
            memoria_comprometida = memoria_planejada
    return eventos, memoria_planejada, memoria_comprometida


def _executar_entrega(objetos: Any, ponte: Any, grupo_jid: str | None, outbox_nome: str,
                      eventos: list[Evento], atividades: list, agora: Callable[[], datetime],
                      momento: datetime, relatorio: Relatorio,
                      memoria_comprometida: dict, memoria_planejada: dict) -> dict:
    """Executa a entrega com outbox temporário e consolida a memória dos eventos duráveis."""
    if not grupo_jid or ponte is None:
        raise StorageError("entrega ligada sem SURICATA_GRUPO_JID")
    with tempfile.TemporaryDirectory(prefix="suricata-outbox-") as pasta:
        fila = OutboxSincronizado(objetos, Path(pasta), outbox_nome)
        fila.podar(momento)
        relatorio.entrega = entregar(fila, ponte, grupo_jid, eventos, agora, atividades)
        # Só depois de o registro existir no outbox a memória pode
        # considerar a novidade vista de forma irreversível.
        duraveis = {r["event_id"] for r in fila.outbox.pendentes()}
        duraveis |= {r["event_id"] for r in _todos(fila)
                     if r.get("estado") in {"in_flight", "sent"}}
        comprometer_memoria(memoria_comprometida, memoria_planejada,
                            eventos, duraveis, relatorio.entrega, momento)
    return memoria_comprometida


def _publicar_relatorio(objetos: Any, relatorio_nome: str, relatorio: Relatorio) -> None:
    """Publica o relatório por CAS; falha de armazenamento não mascara o resultado."""
    try:
        atual = objetos.ler(relatorio_nome)
        objetos.gravar(relatorio_nome, json.dumps(relatorio.json(), ensure_ascii=False, indent=1).encode(),
                       generation=atual.generation)
    except (StorageError, CASConflict):
        pass


def executar(*, objetos: Any, canvas: CanvasClient, entrega_ligada: bool, grupo_jid: str | None,
             ponte: Any | None, agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
             coleta_pronta: Coleta | None = None, destino_prefixo: str = "grupo",
             gerenciar_lease: bool = True) -> tuple[int, dict]:
    momento = agora()
    relatorio = Relatorio(iniciado_em=momento.isoformat(), modo="entrega" if entrega_ligada else "sombra")
    memoria_nome = f"{destino_prefixo}/memoria.json"
    outbox_nome = f"{destino_prefixo}/outbox.json"
    relatorio_nome = f"{destino_prefixo}/ultima-rodada.json"
    lease = Lease(objetos, agora)
    try:
        if gerenciar_lease and not lease.adquirir():
            relatorio.estado = "lease_ocupado"
            return 0, relatorio.json()
    except StorageError as exc:
        relatorio.estado, relatorio.erro = "falha_armazenamento", str(exc)
        return 5, relatorio.json()

    codigo = 0
    try:
        try:
            coleta = coleta_pronta or coletar(canvas, momento)
        except ColetaIndisponivel as exc:
            relatorio.estado, relatorio.erro = "coleta_indisponivel", str(exc)
            codigo = 3
            return codigo, relatorio.json()
        atividades = coleta.atividades
        relatorio.ofertas, relatorio.ofertas_com_falha = coleta.ofertas, coleta.falhas
        relatorio.atividades = len(atividades)
        relatorio.coleta = {
            "estado": "parcial" if coleta.falhas else "completa",
            "ofertas": coleta.ofertas,
            "falhas": list(coleta.falhas),
            "anuncios_determinaveis": coleta.anuncios is not None,
        }
        if coleta.falhas:
            registrar_falhas(objetos, [{"etapa": "coleta", "erro": str(f)} for f in coleta.falhas],
                             _agora_vivo(agora))

        carregado = _carregar_memoria(objetos, memoria_nome, relatorio)
        if carregado is None:
            codigo = 5
            return codigo, relatorio.json()
        obj, memoria = carregado
        manual, erro_agenda = agenda_manual.carregar(objetos)
        extras = agenda_manual.complementar(atividades, manual)
        relatorio.agenda_manual = {"itens": len(manual), "complementares": len(extras), "erro": erro_agenda}
        eventos, memoria_planejada, memoria_comprometida = _planejar_rodada(
            atividades, memoria, momento, coleta, extras, relatorio, entrega_ligada)

        if entrega_ligada:
            memoria_comprometida = _executar_entrega(
                objetos, ponte, grupo_jid, outbox_nome, eventos, atividades,
                agora, momento, relatorio, memoria_comprometida, memoria_planejada)
            if relatorio.entrega.get("sessao") not in (None, "ok"):
                codigo = 6
        memoria = memoria_comprometida
        # A memória só avança depois que os eventos estão duráveis no outbox.
        objetos.gravar(memoria_nome, json.dumps(memoria, ensure_ascii=False, sort_keys=True).encode(),
                       generation=obj.generation)
        relatorio.estado = "concluida" if not relatorio.ofertas_com_falha else "parcial"
        return codigo, relatorio.json()
    except (StorageError, OutboxError) as exc:
        relatorio.estado, relatorio.erro = "falha_armazenamento", f"{type(exc).__name__}: {exc}"
        codigo = 5
        return codigo, relatorio.json()
    finally:
        _publicar_relatorio(objetos, relatorio_nome, relatorio)
        if gerenciar_lease:
            try:
                lease.liberar()
            except Exception:  # noqa: BLE001 - limpeza não pode mascarar o resultado
                pass


def executar_destinos(*, objetos: Any, canvas: CanvasClient, entrega_ligada: bool,
                      ponte: Any | None, destinos: list[Destino],
                      agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> tuple[int, list[dict]]:
    """Coleta uma vez e processa destinos elegíveis com estado totalmente separado."""
    momento = agora()
    lease = Lease(objetos, agora)
    try:
        if not lease.adquirir():
            return 0, [{"estado": "lease_ocupado"}]
    except StorageError as exc:
        return 5, [{"estado": "falha_armazenamento", "erro": str(exc)}]
    try:
        try:
            coleta = coletar(canvas, momento)
        except ColetaIndisponivel as exc:
            return 3, [{"estado": "coleta_indisponivel", "erro": str(exc)}]
        relatorios: list[dict] = []
        codigo = 0
        for destino in destinos:
            if not destino.elegivel(momento):
                continue
            resultado, relatorio = executar(
                objetos=objetos, canvas=canvas, entrega_ligada=entrega_ligada,
                grupo_jid=destino.jid, ponte=ponte, agora=agora,
                coleta_pronta=coleta, destino_prefixo=destino.prefixo, gerenciar_lease=False)
            relatorio["destino"] = destino.identificador
            relatorios.append(relatorio)
            codigo = max(codigo, resultado)
        return codigo, relatorios
    finally:
        try:
            lease.liberar()
        except Exception:  # noqa: BLE001 - limpeza não pode mascarar o resultado
            pass
