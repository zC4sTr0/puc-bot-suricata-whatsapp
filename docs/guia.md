# Guia da Suricata — do clone ao WhatsApp

Este guia é uma escada de quatro níveis. Cada degrau roda na sua máquina, sem
nuvem, sem conta, sem segredo — e nenhum deles envia mensagem. No fim, há duas
seções para quem quer ir além: ligar o WhatsApp de verdade e publicar itens
manuais na agenda.

Se algo falhar, provavelmente não é você: veja
[`interno/TROUBLESHOOTING.md`](interno/TROUBLESHOOTING.md).

## Antes de começar

- **Python 3.11 ou superior** — o projeto usa só a biblioteca padrão. Não há
  `pip install` nenhum para rodar; o `pytest` entra apenas para os testes.
- **Node 20 ou superior (opcional)** — só se você quiser rodar os testes da
  ponte WhatsApp.

Clone e entre na pasta:

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp
cd suricata-whatsapp
```

## Nível 1 — A suíte de testes

```bash
python -m suricata --mode shadow    # probe: um JSON de uma linha
python -m compileall -q suricata    # todo .py compila
python -m pytest -q                 # suíte Python completa
```

Para incluir os testes da ponte Node (uma vez por clone):

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

O que cada comando prova: `shadow` mostra que o pacote importa e responde;
`compileall` que não há erro de sintaxe; `pytest` congela os contratos
(planejamento, estado, outbox, lease, fail-closed das variáveis, E2E com Canvas
falso); `node --test` o contrato da ponte (stdin JSON → resultados com ACK).

Dois avisos honestos:

- Se o `npm ci` falhar, é a dependência Git `libsignal` do Baileys, que exige
  rede — veja [`interno/TROUBLESHOOTING.md`](interno/TROUBLESHOOTING.md).
- Se um teste Python falhar uma vez e passar na seguinte, rode o arquivo
  isolado antes de concluir que quebrou.

Tudo verde sem configurar nada? O checkout está íntegro. Isso **não** prova
integração real com Canvas ou WhatsApp — só que os contratos valem na sua
máquina.

## Nível 2 — Shadow: a probe

```bash
python -m suricata --mode shadow
```

Saída real (exit 0):

```json
{"mode":"shadow","status":"ok","adapter":"none"}
```

Três campos, três significados: `mode` confirma o modo pedido; `status: ok`
que o roteador respondeu; `adapter: none` avisa que **nada além disso foi
exercitado** — sem Canvas, sem estado, sem ponte, sem rede. Shadow não
escreve em lugar nenhum. É a probe que o CI e o container usam.

## Nível 3 — Demo: o bot inteiro, sem efeitos

```bash
python -m suricata --mode demo
```

O modo demo roda o pipeline completo com um Canvas congelado (fixtures) e o
relógio fixo em 15/09/2026. A saída real tem quatro partes — vale ler devagar:

**1. O cabeçalho avisa as regras do jogo:**

```text
suricata · modo demo — Canvas congelado da fixture, relógio fixo em 15/09/2026,
estado temporário, entrega desligada. Nada sai deste processo.
```

**2. As mensagens que *seriam* enviadas.** Aqui entram três avisos: uma lista
com prazo amanhã, uma prova amanhã e um quiz hoje. Cada bloco traz o
`event_id` (a identidade determinística da mensagem — o que impede duplicatas
na vida real), o texto com emoji, pontos, data e o link público do Canvas:

```text
--- novo · grupo:novo:292184:901
🚨 🎓 *PUC Bot*: entrega amanhã no Canvas!
📚 Computabilidade — Lista 1: Indução matemática · 1,5 pts
🔒 até qua 16/09 23:59
↳ última entrega antes da Prova 1 (qua 16/09)
https://pucminas.instructure.com/courses/292184/assignments/901
```

**3. O relatório da rodada em JSON.** Os campos que importam: `"estado":
"concluida"` (a rodada terminou limpa), `"atividades": 3` e `"ofertas": 1`
(o que a coleta viu), `"eventos": [...]` (os três avisos planejados, com
`event_id` e texto), `"entrega": {}` (vazio: nada foi enviado) e `"erro": null`.

**4. A última linha carimba a promessa:**

```text
entrega: desligada — nenhum envio foi feito; nenhum Canvas, WhatsApp ou rede foi acessado.
```

O que isso prova: o caminho planejamento → mensagens → relatório funciona de
ponta a ponta, de forma determinística. O que não prova: Canvas ao vivo,
estado persistente ou WhatsApp.

## Nível 4 — Rodada local com estado de verdade

Aqui o bot roda o caminho canônico (`rodada`), mas com o estado num diretório
local. Um detalhe que economiza horas: `SURICATA_ESTADO_URI` **sem** prefixo
`gs://` vira armazenamento em diretório local — não é preciso GCP nem bucket:

```bash
SURICATA_ESTADO_URI=./tmp-estado SURICATA_CANVAS_TOKEN=falso \
  SURICATA_ENTREGA=desligada python -m suricata --mode rodada
```

Com token falso, a consulta ao Canvas falha (401) e o relatório sai parcial —
isso é o esperado. O ponto deste nível é ver o estado nascer: depois de rodar,
olhe dentro de `./tmp-estado` — lá estão a memória (o que já foi avisado), o
outbox (o que está pendente) e o lease (a trava da rodada). Rode de novo e
veja o estado ser reaproveitado em vez de recomeçado do zero.

A entrega é `desligada` por padrão; o valor explícito aqui é só didático. E
nada escapa por acidente: o repo nunca envia mensagem sem **três** gates
simultâneos — `SURICATA_ENTREGA=ligada` (valor exato, qualquer outro desliga),
um destino válido (`SURICATA_GRUPO_JID` ou `SURICATA_DESTINOS_JSON`) e a
janela BRT aberta (nada sai entre 21:00 e 06:59). Errar qualquer um deles
trava o envio. Para entender o porquê de cada trava, leia
[`arquitetura.md`](arquitetura.md).

## Colocando no WhatsApp de verdade

Chegou até aqui e quer entrega real? Os três passos, na ordem:

1. **Parear a sessão.** A sessão do WhatsApp vive sempre **fora do repo** —
   nunca versionada, nunca dentro da imagem. O pareamento é uma operação
   humana, no seu terminal:

   ```bash
   node suricata/whatsapp/parear.mjs --auth-dir <diretório-fora-do-repo>
   ```

   Escaneie o QR no celular, confirme o sucesso e apague qualquer cópia
   temporária. O fluxo completo (incluindo o utilitário `verificar.mjs`) está
   em [`suricata/whatsapp/README.md`](../suricata/whatsapp/README.md).

2. **Configurar o destino.** Aponte `SURICATA_GRUPO_JID` (ou
   `SURICATA_DESTINOS_JSON` para vários grupos) para o JID confirmado do
   grupo da turma — confirmado por humano, não copiado de documentação velha.
   Em produção, o token e o JID vivem no Secret Manager, nunca no Git.

3. **Ligar a entrega.** `SURICATA_ENTREGA=ligada` — e só isso liga. Qualquer
   outro valor (inclusive ausente) mantém desligado. Depois disso, o bot
   respeita a janela BRT e só marca `sent` com ACK do servidor.

A ponte em produção encontra a sessão pela variável `SURICATA_WA_AUTH_DIR`.
A sessão caída (`logged_out`) é um gate humano: não insista em loop — refaça
o pareamento quando autorizado. O procedimento conservador, com os gates
H1–H3, está em [`interno/RUNBOOK.md`](interno/RUNBOOK.md).

## Publicando itens manuais na agenda

A Suricata lê o Canvas, mas às vezes você quer avisar algo que **não está**
lá — uma prova oral marcada por e-mail, um quiz surpresa anunciado em aula.
Para isso existe o [`deploy/publicar_agenda.py`](../deploy/publicar_agenda.py).

O arquivo JSON tem uma classe fixa e uma lista de itens:

| Campo | Regra |
|---|---|
| `classe` | sempre `"nota_pessoal"` |
| `itens[].id` | obrigatório e único no arquivo |
| `itens[].tipo` | `avaliacao`, `quiz` ou `tarefa` |
| `itens[].titulo` e `itens[].curso` | obrigatórios |
| `itens[].data` | `AAAA-MM-DD` ou `null`; item com data exige `curso_id` |

Exemplo mínimo (`agenda.json`):

```json
{
  "classe": "nota_pessoal",
  "itens": [
    {
      "id": "prova-comp-1",
      "tipo": "avaliacao",
      "titulo": "Prova 1 — Computabilidade",
      "curso": "Computabilidade",
      "data": "2026-10-01",
      "curso_id": "292184"
    }
  ]
}
```

Valide sem publicar nada (exit 0 = válido; exit 2 lista os erros):

```bash
python deploy/publicar_agenda.py --arquivo agenda.json --validar
```

Para publicar, o destino vem de `SURICATA_ESTADO_URI` (o mesmo do estado da
rodada) e o script grava o objeto `agenda/manual.json` com verificação de
concorrência e read-back no fim — se o conteúdo não conferir, ele termina com
`READ-BACK DIVERGENTE` e código 1. Publicar de novo o mesmo arquivo só
responde `agenda: já atualizada`:

```bash
SURICATA_ESTADO_URI=gs://<bucket-suricata> python deploy/publicar_agenda.py --arquivo agenda.json
```

A rodada junta esses itens às atividades do Canvas na hora de planejar.

## E agora?

- Quer entender **por que** o bot é tão cuidadoso com estado, outbox e ACK?
  Leia [`arquitetura.md`](arquitetura.md).
- Quer colocar o bot **na nuvem**? Leia [`deploy-gcp.md`](deploy-gcp.md).
- Vai mexer no código? [`CONTRIBUTING.md`](../CONTRIBUTING.md) explica o
  ritmo: fatia pequena, teste antes, PR com provas.
