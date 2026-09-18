"""Execução da rodada Suricata: outbox, entrega e destinos.

Extração estrutural de ``rodada.py``; contratos e ordem de efeitos preservados.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import agenda_manual
from .canvas import CanvasClient
from .coleta import Coleta, ColetaIndisponivel, coletar
from .config import Destino
from .lease_rodada import Lease
from .message_id import message_id
from .outbox import OutboxError
from .persistencia_rodada import OutboxSincronizado
from .planejamento import Evento, _limite_manha, _pode_aguardar_07h, planejar
from .publico import BRASILIA, Atividade, em_silencio, texto_lote
from .storage.cas import CASConflict, StorageError

@dataclass
class Relatorio:
    iniciado_em: str
    modo: str
    estado: str = "iniciada"
    ofertas: int = 0
    ofertas_com_falha: list[str] = field(default_factory=list)
    atividades: int = 0
    linha_de_base: bool = False
    eventos: list[dict[str, str]] = field(default_factory=list)
    entrega: dict[str, Any] = field(default_factory=dict)
    agenda_manual: dict[str, Any] = field(default_factory=dict)
    coleta: dict[str, Any] = field(default_factory=dict)
    erro: str | None = None

    def json(self) -> dict[str, Any]:
        return {
            "iniciado_em": self.iniciado_em,
            "modo": self.modo,
            "estado": self.estado,
            "ofertas": self.ofertas,
            "ofertas_com_falha": deepcopy(self.ofertas_com_falha),
            "atividades": self.atividades,
            "linha_de_base": self.linha_de_base,
            "eventos": deepcopy(self.eventos),
            "entrega": deepcopy(self.entrega),
            "agenda_manual": deepcopy(self.agenda_manual),
            "coleta": deepcopy(self.coleta),
            "erro": self.erro,
        }











def _todos(fila: OutboxSincronizado) -> list[dict[str, Any]]:
    return json.loads(fila.caminho.read_text(encoding="utf-8")) if fila.caminho.exists() else []




def _agora_vivo(agora: datetime | Callable[[], datetime]) -> datetime:
    return agora() if callable(agora) else agora


def _corte_21h(agora: datetime) -> bool:
    local = agora.astimezone(BRASILIA)
    return (local.hour, local.minute, local.second, local.microsecond) >= (21, 0, 0, 0)


def _janela_manha(agora: datetime) -> bool:
    """A exceção só pode ser reivindicada entre 07:00 e 07:00:59 BRT."""
    local = agora.astimezone(BRASILIA)
    return local.hour == 7 and local.minute == 0


def _autorizacao_corte(evento: Evento, agora: datetime) -> dict[str, Any] | None:
    atividade = evento.atividade
    if not _pode_aguardar_07h(evento, agora):
        return None
    return {
        "chave": atividade.chave,
        "tipo": atividade.tipo,
        "titulo": atividade.titulo,
        "fonte": atividade.fonte,
        "unlock_at": atividade.unlock_at.isoformat(),
        "fecha": atividade.fecha.isoformat(),
        "descoberto_em": agora.isoformat(),
    }


def _evento_disponivel(registro: dict[str, Any], agora: datetime) -> bool:
    """Não reivindica novidade antes da janela BRT persistida no outbox."""
    disponivel = registro.get("disponivel_em")
    if not disponivel:
        return True
    try:
        return datetime.fromisoformat(disponivel) <= agora
    except (TypeError, ValueError):
        # Estado persistido inválido nunca autoriza um envio antecipado.
        return False


def _autorizados_persistidos(fila: OutboxSincronizado, atividades: list[Atividade], agora: datetime) -> set[str]:
    atuais = {a.chave: a for a in atividades}
    autorizados: set[str] = set()
    for registro in fila.outbox.pendentes():
        corte = registro.get("corte_21h")
        if not isinstance(corte, dict):
            continue
        chave = corte.get("chave")
        if not isinstance(chave, str):
            continue
        atividade = atuais.get(chave)
        if atividade is None:
            continue
        try:
            descoberta = datetime.fromisoformat(corte["descoberto_em"])
            esperado = Evento.de_atividade("novo", atividade, agora)
            if (_autorizacao_corte(esperado, descoberta) == corte
                    and _janela_manha(agora)):
                autorizados.add(registro["event_id"])
        except (KeyError, TypeError, ValueError):
            # Estado persistido não é evidência. Corrupção fica sem
            # autorização e será descartada pelo corte, sem abortar a rodada.
            continue
    return autorizados


def entregar(fila: OutboxSincronizado, ponte: Any, grupo_jid: str, eventos: list[Evento],
             agora: datetime | Callable[[], datetime], atividades: list[Atividade] | None = None) -> dict[str, Any]:
    outbox = fila.outbox
    momento = _agora_vivo(agora)
    # IDs adicionados nesta chamada recebem autorização efêmera às 07:00;
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
    outbox.recuperar_interrompidos(agora=momento)
    atual = _agora_vivo(agora)
    local_atual = atual.astimezone(BRASILIA)
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
        # Nunca de madrugada: tudo espera na fila e sai às 07:00 (o que perder o sentido expira).
        fila.publicar()
        return {"silencio": True, "aguardando": len(outbox.pendentes()), "expirados": expirados_count,
                "pendentes_enviados": 0, "sent": 0, "sem_ack": 0, "sessao": None}
    claims = [outbox.reivindicar(p["event_id"], agora=atual)
              for p in outbox.pendentes() if _evento_disponivel(p, atual)]
    claims = [c for c in claims if c["estado"] == "in_flight"]
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
    resumo["sessao"] = resposta.get("sessao") if isinstance(resposta, dict) else "erro"
    if isinstance(resposta, dict) and (resposta.get("erro") or resposta.get("detalhe")):
        resumo["erro"] = str(resposta.get("detalhe") or resposta.get("erro"))[:400]
    itens = {r.get("event_id"): r for r in (resposta.get("resultados") or [])} if isinstance(resposta, dict) else {}
    for envio in envios:
        item = itens.get(envio["event_id"]) or {}
        ack = (resumo["sessao"] == "ok" and item.get("message_id") == envio["message_id"]
               and item.get("ack") is True and type(item.get("status")) is int and item["status"] >= 2)
        for claim in envio["claims"]:  # um lote confirma todos os eventos que carrega
            outbox.aplicar_resultado(claim["event_id"], attempt_id=claim["attempt_id"],
                                     message_id=claim["message_id"], ack=ack,
                                     status=item.get("status") if ack else None)
            resumo["sent" if ack else "sem_ack"] += 1
    fila.publicar()
    return resumo


MAX_LOTE = 5


def agrupar_envios(claims: list[dict[str, Any]], grupo_jid: str) -> list[dict[str, Any]]:
    """Publicações pendentes da mesma leva viram uma mensagem (até 5 por mensagem).

    O ``event_id`` do lote deriva dos eventos que carrega: o reenvio do mesmo conjunto
    reusa o mesmo ``message_id`` e o WhatsApp não duplica (F42).
    """
    novos = sorted((c for c in claims if c["event_id"].startswith("grupo:novo:")), key=lambda c: c["event_id"])
    envios = [{**c, "claims": [c]} for c in claims if not c["event_id"].startswith("grupo:novo:")]
    if len(novos) < 2:
        return [{**c, "claims": [c]} for c in novos] + envios
    lotes = []
    for inicio in range(0, len(novos), MAX_LOTE):
        parte = novos[inicio:inicio + MAX_LOTE]
        if len(parte) == 1:
            lotes.append({**parte[0], "claims": parte})
            continue
        ident = "grupo:lote:" + hashlib.sha256("|".join(c["event_id"] for c in parte).encode()).hexdigest()[:16]
        lotes.append({"event_id": ident, "message_id": message_id(grupo_jid, ident),
                      "texto": texto_lote([c["texto"] for c in parte]), "claims": parte})
    return lotes + envios
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

        obj = objetos.ler(memoria_nome)
        try:
            memoria = json.loads(obj.dados) if obj.dados else {}
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            relatorio.estado = "memoria_invalida"
            relatorio.erro = "memória persistida inválida; rodada não avançada"
            codigo = 5
            return codigo, relatorio.json()
        if not isinstance(memoria, dict):
            relatorio.estado = "memoria_invalida"
            relatorio.erro = "memória persistida deve ser um objeto JSON; rodada não avançada"
            codigo = 5
            return codigo, relatorio.json()
        manual, erro_agenda = agenda_manual.carregar(objetos)
        extras = agenda_manual.complementar(atividades, manual)
        relatorio.agenda_manual = {"itens": len(manual), "complementares": len(extras), "erro": erro_agenda}
        # Planejamento é uma transação em memória: nenhuma marca de anúncio,
        # item ou lembrete chega ao estado persistido antes do outbox.
        memoria_planejada = deepcopy(memoria)
        eventos, relatorio.linha_de_base = planejar(atividades, memoria_planejada, momento, coleta.anuncios, extras)
        relatorio.eventos = [{"tipo": e.tipo, "event_id": e.event_id, "texto": e.texto} for e in eventos]
        memoria_comprometida = deepcopy(memoria)
        if relatorio.linha_de_base:
            # A linha de base é inicialização, não consumo de novidade.
            memoria_comprometida["linha_de_base_em"] = memoria_planejada["linha_de_base_em"]
            if entrega_ligada:
                memoria_comprometida = memoria_planejada

        if entrega_ligada:
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
                for evento in eventos:
                    if evento.event_id not in duraveis:
                        continue
                    # ACK não é necessário para a durabilidade do evento, mas
                    # uma falha explícita da ponte não consome a memória: a
                    # próxima rodada deve reconstruir a intenção e reenviar.
                    if relatorio.entrega.get("sessao") not in (None, "ok"):
                        continue
                    if evento.atividade is not None:
                        chave = evento.atividade.chave
                        item_planejado = memoria_planejada.get("itens", {}).get(chave)
                        if item_planejado is not None:
                            memoria_comprometida.setdefault("itens", {})[chave] = deepcopy(item_planejado)
                        # A marca só é consumida depois de o novo ser registrado.
                        memoria_comprometida.get("itens", {}).get(chave, {}).pop("novidade_pendente", None)
                        if evento.tipo == "novo":
                            local = momento.astimezone(BRASILIA)
                            amanha = local.date() + timedelta(days=1)
                            if amanha in {d.astimezone(BRASILIA).date()
                                          for d in (evento.atividade.fecha, evento.atividade.unlock_at)
                                          if d is not None}:
                                memoria_comprometida.setdefault("chegando", {})[chave] = amanha.isoformat()
                    elif evento.tipo == "anuncio":
                        anuncio_id = evento.event_id.rsplit(":", 1)[-1]
                        if anuncio_id in memoria_planejada.get("anuncios", {}):
                            memoria_comprometida.setdefault("anuncios", {})[anuncio_id] = memoria_planejada["anuncios"][anuncio_id]
                    elif evento.tipo == "aviso_prova":
                        data_evento = evento.event_id.rsplit(":", 1)[-1]
                        if data_evento in memoria_planejada.get("avisos_prova", {}):
                            memoria_comprometida.setdefault("avisos_prova", {})[data_evento] = memoria_planejada["avisos_prova"][data_evento]
                    elif evento.tipo == "vespera":
                        data_evento = evento.event_id.rsplit(":", 1)[-1]
                        if data_evento in memoria_planejada.get("vesperas", {}):
                            memoria_comprometida.setdefault("vesperas", {})[data_evento] = memoria_planejada["vesperas"][data_evento]
                        for campo in ("chegando", "adiantadas"):
                            memoria_comprometida[campo] = deepcopy(memoria_planejada.get(campo, {}))
            memoria = memoria_comprometida
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
        try:
            atual = objetos.ler(relatorio_nome)
            objetos.gravar(relatorio_nome, json.dumps(relatorio.json(), ensure_ascii=False, indent=1).encode(),
                           generation=atual.generation)
        except (StorageError, CASConflict):
            pass
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
