# Documentação da Suricata

Esta pasta separa documentação operacional, contratos, histórico e estado verificado. O runtime permanece em [`../suricata/`](../suricata/); esta página é o índice humano para decidir por onde começar.

## Comece aqui

- [`../README.md`](../README.md) — visão do produto, modos e comandos locais sem efeitos.
- [`../AGENTS.md`](../AGENTS.md) — limites operacionais, segurança e validação obrigatória.
- [`STATUS.md`](STATUS.md) — estado verificado mais recente; snapshots históricos são identificados no próprio texto.

## Operar sem publicar

- [`OPERATIONS.md`](OPERATIONS.md) — pré-voo, leitura de estado e critérios de parada.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — diagnóstico sem expor segredos ou ativar entrega.
- [`SECURITY.md`](SECURITY.md) — fronteiras, segredos, sessão e invariantes de entrega.
- [`CONFIGURATION.md`](CONFIGURATION.md) — variáveis e configuração por ambiente.

## Entender o produto

- [`PRODUCT.md`](PRODUCT.md) — comportamento público e limites do bot.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — fluxo Python → estado/outbox → Node/ACK.
- [`../suricata/MAPA.md`](../suricata/MAPA.md) — mapa detalhado de módulos e testes.
- [`../suricata/DOCUMENTATION.md`](../suricata/DOCUMENTATION.md) — índice interno do runtime.

## Deploy e continuidade

- [`DEPLOYMENT.md`](DEPLOYMENT.md) — build, canário sem entrega, corte e rollback.
- [`PLANO-CONTINUIDADE-INDEPENDENTE.md`](PLANO-CONTINUIDADE-INDEPENDENTE.md) — procedimento executável de retomada e gates.
- [`PLANO-EXTRACAO-SURICATA.md`](PLANO-EXTRACAO-SURICATA.md) — histórico da extração para o repositório próprio.
- [`PLANO-SURICATA-WHATSAPP.md`](PLANO-SURICATA-WHATSAPP.md) — plano histórico de contratos e decisões; não é autorização automática para executar comandos.
- [`MIGRATION.md`](MIGRATION.md) — decisões e compatibilidade de migração.

## Regra de leitura

`STATUS.md` descreve o que foi verificado. Planos e documentos históricos explicam decisões anteriores, mas não substituem read-back do GitHub, Cloud Run, Scheduler, Artifact Registry ou estado operacional. Nenhuma página deste diretório contém sessão, QR, token, JID real ou payload de produção.
