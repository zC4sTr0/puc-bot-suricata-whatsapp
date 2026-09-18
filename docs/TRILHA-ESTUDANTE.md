# Trilha do estudante

Quatro níveis, do clone ao entendimento das fronteiras. Cada nível diz o que
você vê, o que isso prova e qual é o próximo passo. Nada aqui envia mensagem,
toca no Canvas real com segredo ou exige GCP.

Pré-requisitos: Python 3.11+ (std lib pura, zero `pip install` — só o `pytest`
para os testes) e Node 20+ se quiser rodar os testes da ponte.

## Nível 1 — Testes verdes

Rode, na raiz do repo:

```bash
python -m suricata --mode shadow    # probe: JSON ok em 1 linha
python -m compileall -q suricata   # todo .py compila
python -m pytest -q                 # suíte Python completa (~300 testes)
```

Para os testes da ponte Node, instale a dependência primeiro (uma vez por
clone; ver `suricata/whatsapp/README.md`):

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

O que cada runner prova:

- `shadow` — o pacote importa e o entrypoint responde.
- `compileall` — não há erro de sintaxe em nenhum módulo.
- `pytest` — contratos funcionais: planejamento, estado, outbox, lease,
  fail-closed das variáveis, E2E com Canvas falso.
- `node --test` — o contrato da ponte (stdin JSON → resultados com ACK) e o
  stub offline dela.

Se algo falhar em `npm ci` (dependência Git pede rede), veja
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). Se um teste Python falhar uma vez
e passar na seguinte, rode o arquivo isolado antes de concluir que quebrou —
há um teste conhecido sensível à ordem.

**O que você vê:** tudo verde, sem configuração nenhuma.
**O que isso prova:** o checkout está íntegro e os contratos básicos valem na
sua máquina — não prova nada sobre a integração real com Canvas/WhatsApp.
**Próximo passo:** Nível 2.

## Nível 2 — Shadow: o que a probe prova (e o que não)

```bash
python -m suricata --mode shadow
```

Saída esperada (exit 0):

```json
{"mode":"shadow","status":"ok","adapter":"none"}
```

**O que você vê:** um JSON de uma linha.
**O que isso prova:** pacote importável, entrypoint válido, saída estruturada.
**O que NÃO prova:** nada de Canvas, estado, planejamento ou ponte — o
`"adapter":"none"` diz explicitamente que nada além disso foi exercitado.
Shadow não consulta rede nem escreve em lugar nenhum.

**Próximo passo:** Nível 3, onde as mensagens aparecem.

## Nível 3 — Demo e rodada local com estado em diretório

Primeiro o modo demo, offline e zero-config — ele planeja avisos a partir de
fixtures congeladas e imprime o relatório com entrega desligada:

```bash
python -m suricata --mode demo
```

Depois, uma rodada com estado em diretório local. Um detalhe que economiza
horas: `SURICATA_ESTADO_URI` sem prefixo `gs://` vira armazenamento em
diretório local — **não é preciso GCP nem bucket** para rodar o caminho
canônico:

```bash
SURICATA_ESTADO_URI=./tmp-estado SURICATA_CANVAS_TOKEN=falso \
  SURICATA_ENTREGA=desligada python -m suricata --mode rodada
```

Com token falso, a consulta ao Canvas falha (401) e o relatório sai parcial —
normal. O ponto deste nível é ver o estado nascer: após rodar, inspecione o
diretório `./tmp-estado` criado no seu clone (memória, outbox, lease). A
entrega é desligada por padrão; o valor explícito aqui é só didático.

**O que você vê:** o relatório da rodada e um diretório de estado local.
**O que isso prova:** o caminho completo Canvas → planejamento → outbox →
estado funciona na sua máquina, com entrega fechada.
**Próximo passo:** Nível 4.

## Nível 4 — Isolamento e fronteiras

O repo nunca envia mensagem sem três gates simultâneos:

1. `SURICATA_ENTREGA=ligada` — qualquer outro valor (inclusive ausente) mantém
   a entrega desligada;
2. um destino válido (`SURICATA_GRUPO_JID` ou `SURICATA_DESTINOS_JSON`,
   validado por regex; inválido falha fechado);
3. a janela BRT do destino aberta — fora da janela, nada sai.

Ou seja: apagar a variável de entrega, errar o JID ou estar fora da janela,
qualquer um dos três, trava o envio. Em produção, segredo fica em Secret
Manager, nunca em JSON, log ou argv.

Para brincar com a ponte sem rede, use os fixtures:
[`../suricata/tests/fixtures/bridge_stub.mjs`](../suricata/tests/fixtures/bridge_stub.mjs)
é um stub offline da ponte Node — lê um lote JSON no stdin e devolve
resultados com ACK, sem importar Baileys nem abrir socket. Ele aceita cenários
(sucesso, timeout, ack-divergente, crash) via env `SURICATA_STUB_SCENARIO`.
Os testes E2E usam esse mesmo stub; veja
[`../suricata/tests/README.md`](../suricata/tests/README.md).

**O que você vê:** stubs e testes que exercitam a ponte sem rede.
**O que isso prova:** o isolamento é verificável localmente, não promessa.
**Próximo passo:** leia [`CONTRACTS.md`](CONTRACTS.md) e
[`../suricata/ARCHITECTURE.md`](../suricata/ARCHITECTURE.md) para entender os
contratos por trás de cada gate.
