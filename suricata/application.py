"""Caso de uso da sentinela, com persistência opt-in e sem efeitos implícitos."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Callable, Iterable

from .sentinela import executar_rodada_sombra


@dataclass
class SentinelaApplication:
    """Executa uma rodada sombra e, opcionalmente, materializa seu estado.

    ``state_writer`` é deliberadamente ``None`` por padrão. Assim, uma rodada
    sombra continua sendo uma função observável apenas pelo retorno (e pelo
    ``report_writer`` explicitamente fornecido). O writer deve implementar os
    métodos de ``EstadoLocal`` usados abaixo; a dependência é duck-typed para
    permitir testes e backends locais sem importar armazenamento global.
    """

    canvas: Any
    clock: Callable[[], datetime] | None = None
    notifier: Callable[[str], Any] | None = None
    # ``delivery`` is a batch transport.  Supplying it is the explicit opt-in;
    # ``False`` is an explicit kill switch for callers that configure one.
    delivery: Any | None = None
    delivery_enabled: bool | None = None
    report_writer: Callable[[dict[str, Any]], Any] | None = None
    state_writer: Any | None = None

    def run(self, ofertas: Iterable[str]) -> dict[str, Any]:
        momento = self.clock() if self.clock else datetime.now(timezone.utc)
        report = executar_rodada_sombra(self.canvas, ofertas, momento)
        entrega = {"habilitada": self._delivery_habilitada(), "chamado": False, "status": []}
        report["entrega"] = entrega
        report["delivery"] = entrega
        if self.state_writer is not None and report.get("estado") == "concluida":
            self._persistir_rodada(report, momento)
        elif self._delivery_habilitada() and report.get("estado") == "concluida":
            # Delivery is independently injectable; persistence is not a
            # prerequisite, but it always precedes the external call.
            status = self._chamar_delivery(list(report["eventos"]))
            entrega.update({"chamado": bool(report["eventos"]), "status": status})
        if self.report_writer is not None:
            self.report_writer(report)
        return report

    def _persistir_rodada(self, report: dict[str, Any], momento: datetime) -> None:
        """Persiste somente após coleta íntegra; dedup vem antes do notifier."""
        writer = self.state_writer
        writer.atualizar_heartbeat(
            saudavel=True, agora=momento,
            contagens={"candidatos": report["candidatos"], "projetados": report["projetados"],
                       "avisos": report["avisos"]},
            status="ok",
        )

        memoria = writer.ler_memoria_grupo()
        if not memoria:
            writer.registrar_memoria_grupo({
                "linha_de_base_em": momento.isoformat(), "anuncios_vistos": {},
            })

        pendentes: list[tuple[dict[str, Any], str]] = []
        if self._delivery_habilitada():
            # The durable outbox owns idempotency and retry semantics. Recording
            # a terminal dedup key here would suppress a later retry after a
            # timeout/pending result.
            pendentes = [(aviso, str(aviso["texto"])) for aviso in report["eventos"]]
        elif self.notifier is not None:
            for aviso in report["eventos"]:
                texto = str(aviso["texto"])
                version = hashlib.sha256(texto.encode("utf-8")).hexdigest()
                if writer.registrar_dedup({
                    "item_id": aviso["event_id"], "versao": version,
                    "transicao": "alertar", "visto_em": momento.isoformat(),
                }):
                    pendentes.append((aviso, texto))

        # O diário representa a rodada antes de qualquer efeito externo.
        writer.registrar_diario({
            "event_id": f"grupo:rodada:{momento.isoformat()}",
            "eventos": report["projetados"],
            "avisos": len(pendentes),
            "registrado_em": momento.isoformat(),
            "coleta": report["estado"],
        })

        # Dedup e diário já estão persistidos; somente agora há efeito externo.
        if self._delivery_habilitada():
            status = self._chamar_delivery([aviso for aviso, _ in pendentes])
            report["entrega"].update({"chamado": bool(pendentes), "status": status})
            successful = {item["event_id"] for item in status if item["status"] == "sent"}
            for aviso, _ in pendentes:
                if aviso["event_id"] in successful:
                    writer.registrar_anuncio_visto(aviso["event_id"], visto_em=momento)
        elif self.notifier is not None:
            # Compatibility with the original injected text notifier.
            for aviso, texto in pendentes:
                self.notifier(texto)
                writer.registrar_anuncio_visto(aviso["event_id"], visto_em=momento)

    def _delivery_habilitada(self) -> bool:
        return self.delivery is not None and self.delivery_enabled is not False

    def _chamar_delivery(self, eventos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Call an injected transport and expose only safe operational status."""
        if not eventos:
            return []
        try:
            orchestrate = getattr(self.delivery, "deliver", None)
            if callable(orchestrate):
                public_events = [
                    {key: value for key, value in evento.items() if key != "texto"}
                    for evento in eventos
                ]
                raw = orchestrate(public_events)
            else:
                func = getattr(self.delivery, "enviar_lote", None)
                raw = func(eventos) if callable(func) else self.delivery(eventos)
        except Exception:
            return [{"event_id": e["event_id"], "status": "failed"} for e in eventos]
        if not isinstance(raw, list):
            return [{"event_id": e["event_id"], "status": "failed"} for e in eventos]
        by_id = {item.get("event_id"): item for item in raw if isinstance(item, dict)}
        safe = []
        for evento in eventos:
            item = by_id.get(evento["event_id"], {})
            value = item.get("estado", item.get("status", item.get("sessao")))
            acknowledged = item.get("ack") is True and item.get("sessao", "ok") == "ok"
            status = "sent" if acknowledged or value in {"sent", "ok", "ack", True} or (type(value) is int and value >= 2) else "pending" if value in {"pending", "in_flight", "timeout"} else "failed"
            safe.append({"event_id": evento["event_id"], "status": status})
        return safe

    executar = run


def executar_sombra(canvas: Any, ofertas: Iterable[str], *, momento: datetime | None = None,
                    report_writer: Callable[[dict[str, Any]], Any] | None = None,
                    state_writer: Any | None = None,
                    notifier: Callable[[str], Any] | None = None,
                    delivery: Any | None = None,
                    delivery_enabled: bool | None = None) -> dict[str, Any]:
    """Executa sombra; estado e notificação só existem quando injetados."""
    app = SentinelaApplication(
        canvas=canvas, report_writer=report_writer, state_writer=state_writer,
        notifier=notifier, clock=(lambda: momento) if momento is not None else None,
        delivery=delivery, delivery_enabled=delivery_enabled,
    )
    return app.run(ofertas)


run_shadow = executar_sombra

__all__ = ["SentinelaApplication", "executar_sombra", "run_shadow"]
