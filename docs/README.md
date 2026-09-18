# Documentação da Suricata

Esta pasta separa documentação operacional, contratos, histórico e estado verificado. O runtime permanece em [`../suricata/`](../suricata/); esta página é o índice humano para decidir por onde começar.

## Comece aqui

- [`TRILHA-ESTUDANTE.md`](TRILHA-ESTUDANTE.md) — trilha do estudante: quatro níveis, de testes verdes a uma rodada local sem GCP.
- [`../README.md`](../README.md) — visão do produto, modos e comandos locais sem efeitos.
- [`../AGENTS.md`](../AGENTS.md) — limites operacionais, segurança e validação obrigatória.
- [`STATUS.md`](STATUS.md) — estado verificado mais recente; snapshots históricos são identificados no próprio texto.
- [`CONTRACTS.md`](CONTRACTS.md) — contratos que uma refatoração deve preservar.

## Operar sem publicar

- [`OPERATIONS.md`](OPERATIONS.md) — pré-voo, leitura de estado e critérios de parada.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — diagnóstico sem expor segredos ou ativar entrega.
- [`SECURITY.md`](SECURITY.md) — fronteiras, segredos, sessão e invariantes de entrega.
- [`CONFIGURATION.md`](CONFIGURATION.md) — variáveis e configuração por ambiente.

## Entender o produto

- [`PRODUCT.md`](PRODUCT.md) — comportamento público e limites do bot.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — fluxo Python → estado/outbox → Node/ACK.
- [`../suricata/MAPA.md`](../suricata/MAPA.md) — mapa detalhado de módulos e testes.
- [`../suricata/tests/README.md`](../suricata/tests/README.md) — o que cada runner de teste prova e como rodar os testes `.mjs` da ponte.
- [`../suricata/DOCUMENTATION.md`](../suricata/DOCUMENTATION.md) — índice interno do runtime.

## Deploy e continuidade

- [`DEPLOYMENT.md`](DEPLOYMENT.md) — build, canário sem entrega, corte e rollback.

Os três documentos abaixo são planos históricos: arquivo de decisões,
opcionais, e não autorizam comandos automaticamente. Não são leitura
obrigatória de onboarding.

- [`PLANO-CONTINUIDADE-INDEPENDENTE.md`](PLANO-CONTINUIDADE-INDEPENDENTE.md) — procedimento executável de retomada e gates (434 linhas).
- [`PLANO-EXTRACAO-SURICATA.md`](PLANO-EXTRACAO-SURICATA.md) — histórico da extração para o repositório próprio (681 linhas).
- [`PLANO-SURICATA-WHATSAPP.md`](PLANO-SURICATA-WHATSAPP.md) — plano histórico de contratos e decisões (711 linhas); não é autorização automática para executar comandos.
- [`MIGRATION.md`](MIGRATION.md) — decisões e compatibilidade de migração.

## Regra de leitura

`STATUS.md` descreve o que foi verificado. Planos e documentos históricos explicam decisões anteriores, mas não substituem read-back do GitHub, Cloud Run, Scheduler, Artifact Registry ou estado operacional. Nenhuma página deste diretório contém sessão, QR, token, JID real ou payload de produção.

### Taxonomia de evidência

- **Verificado localmente:** reproduzido neste checkout por comando/teste.
- **Verificado por read-back:** lido diretamente do recurso externo na data indicada.
- **Snapshot histórico:** fato válido apenas para a data/commit registrado.
- **Não verificado:** hipótese ou estado que exige nova leitura antes de qualquer ação.

Quando fontes divergirem, prevalece o read-back mais recente; sem read-back, não se afirma equivalência entre código, imagem e produção.
