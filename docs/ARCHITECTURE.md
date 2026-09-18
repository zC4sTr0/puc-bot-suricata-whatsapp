# Arquitetura

```text
Cloud Scheduler → Cloud Run Job
  → Canvas (GET público)
  → coleta/normalização
  → planejamento público por destino
  → lease + memória + outbox
  → ponte Python → Node/Baileys
  → ACK confirmado → sent
```

Python é dono do estado e do contrato; Node executa somente a ponte WhatsApp. O corte em `America/Sao_Paulo` bloqueia mensagens a partir de 21:00. `shadow` não consulta serviços externos. `rodada` é o caminho funcional e só entrega quando a configuração, a janela, o estado e o ACK permitem.

A configuração real pertence ao ambiente do processo ou ao Secret Manager. O repositório contém apenas placeholders e manifestos sanitizados.

## Ownership para manutenção

- **Entrada/composição:** `suricata/__main__.py`, `suricata/entrypoint.py` e as fachadas de modo. Eles selecionam o caso de uso; não devem conter regras de domínio.
- **Domínio e planejamento:** `dominio/planejamento.py`, `dominio/publico.py`, `dominio/corte_rodada.py`, `dominio/memoria_rodada.py`, `dominio/relatorio.py`, `dominio/horario.py`, `dominio/message_id.py`. Extração incremental continua válida quando precedida de prova de equivalência.
- **Orquestração:** `rodada/` (`__init__.py`, `execucao.py`, `runtime.py`, `coleta.py`, `agenda_manual.py`, `config.py`) e `demo.py`. Coordenam etapas e dependências, mas não devem assumir detalhes de Canvas, GCS ou subprocesso.
- **Adapters/infraestrutura:** `integracao/canvas.py`, `integracao/bridge.py`, `storage/`, `storage/persistencia_rodada.py`, `storage/lease_rodada.py` e `storage/outbox.py`. São as únicas áreas autorizadas a conhecer efeitos externos e persistência concreta.
- **Transporte:** `suricata/whatsapp/` recebe lote JSON, executa Baileys e devolve ACK sanitizado; não decide elegibilidade nem estado de negócio.

Essa classificação é a âncora da refatoração. A estrutura alvo detalhada e os gates estão em [`CONTRACTS.md`](CONTRACTS.md) e no plano local em `.hermes/plans/`.
