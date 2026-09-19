# Guia da Suricata — para quem estuda

## O que é o produto

A Suricata é um bot que transforma o calendário acadêmico em lembretes no grupo da turma. Ela lê as atividades públicas das disciplinas no **Canvas**, decide o que merece atenção e prepara uma mensagem curta com matéria, data, pontos e link.

Ela não entrega trabalhos, não responde quizzes, não lê notas ou submissões e não substitui o Canvas. O Canvas continua sendo a fonte oficial: se houver diferença entre uma mensagem e o Canvas, confira o Canvas.

### O que significam os tipos

- **Prova**: avaliação identificada pelo Canvas como avaliação/exame ou pelo título reconhecido como prova. A Suricata avisa a data provável; não inventa sala, conteúdo ou nota.
- **Quiz**: atividade que o Canvas identifica como quiz, inclusive quiz LTI. Pode receber lembrete especial quando abre em uma janela curta.
- **Tarefa**: trabalho, lista ou entrega que não é prova nem quiz. O aviso usa a data de entrega publicada no Canvas.
- **Agenda manual**: complemento escrito por uma pessoa para algo que ainda não está no Canvas, como uma prova anunciada em aula. É auxiliar, não substitui nem corrige o Canvas; quando o Canvas já tem prova/quiz no mesmo curso e dia, o item manual não duplica o aviso.

## Quando os avisos aparecem

O relógio usado é o de Brasília (`America/Sao_Paulo`). O agendador pode acordar o bot a cada 10 minutos, mas acordar não significa enviar mensagem.

| Horário | Regra humana |
|---|---|
| **07:00** | Reabre a manhã. Novidades que ficaram na fila podem ser tratadas; nada é enviado durante a madrugada. |
| **12:00** | Na véspera, pode sair um aviso extra quando o dia seguinte tem prova ou quiz. Esse aviso evita repetir às 18:00 o que já foi comunicado. |
| **18:00** | Lembrete principal da véspera: reúne o que vence ou acontece amanhã e a antecedência de atividades relevantes. Uma rodada perdida pode ser recuperada até 22:59, se ainda fizer sentido. |
| **21:00** | Corte noturno. A partir de 21:00 nada é reivindicado nem enviado; espera-se a manhã seguinte. |

Entre 07:00 e 11:59, uma novidade para amanhã pode ser avisada imediatamente. Quizzes surpresa (sem data de abertura/entrega) também podem ser considerados imediatamente. O planejador pode silenciar itens distantes, repetidos ou sem informação suficiente.

## Antes de começar

- Python 3.11 ou superior. O runtime usa a biblioteca padrão.
- Node 20 ou superior apenas para testar a ponte WhatsApp.

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp
cd suricata-whatsapp
```

## Primeiro contato: testar sem enviar nada

### 1. Verificar a instalação

```bash
python -m suricata --mode shadow
python -m compileall -q suricata
python -m pytest -q
```

A probe `shadow` deve produzir uma linha JSON semelhante a esta **saída esperada**:

```json
{"mode":"shadow","status":"ok","adapter":"none"}
```

`compileall` verifica sintaxe. `pytest` verifica contratos locais, incluindo planejamento, estado, outbox, lease e cenários de Canvas falso. Nada desses comandos prova que uma conta Canvas ou uma sessão WhatsApp real está funcionando.

Para a ponte Node:

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

### 2. Ver uma rodada didática

```bash
python -m suricata --mode demo
```

A demo usa dados sintéticos congelados e um relógio fixo. A **saída esperada** contém mensagens que seriam planejadas e um relatório, mas não faz chamadas ao Canvas, não grava estado persistente e não envia WhatsApp. Se o `npm ci` falhar, a dependência Git do Baileys precisa de rede; consulte [`interno/TROUBLESHOOTING.md`](interno/TROUBLESHOOTING.md).

### 3. Exercitar estado local, ainda sem entrega

```bash
SURICATA_ESTADO_URI=./tmp-estado SURICATA_CANVAS_TOKEN=falso \
  SURICATA_ENTREGA=desligada python -m suricata --mode rodada
```

O token falso deve produzir uma coleta parcial (401). Isso é intencional: o objetivo é observar o diretório `./tmp-estado`, que contém memória, outbox e lease. A entrega permanece desligada.

## Só depois: operação real

A entrega exige **todos** estes gates:

1. `SURICATA_ENTREGA=ligada` com valor exato;
2. um destino confirmado por uma pessoa (`SURICATA_GRUPO_JID` ou `SURICATA_DESTINOS_JSON`);
3. horário permitido, entre 07:00 e antes de 21:00 BRT;
4. sessão WhatsApp autenticada e ACK do servidor.

Qualquer falha mantém o caminho fechado. Token, JID e sessão não devem entrar no Git. O pareamento é humano e a sessão fica fora do repositório:

```bash
node suricata/whatsapp/parear.mjs --auth-dir <diretório-fora-do-repo>
```

O procedimento completo está em [`suricata/whatsapp/README.md`](../suricata/whatsapp/README.md) e no runbook [`interno/RUNBOOK.md`](interno/RUNBOOK.md). Não copie identificadores reais de turma para exemplos ou documentação.

## Como registrar uma agenda manual

Use [`deploy/publicar_agenda.py`](../deploy/publicar_agenda.py) apenas para um complemento que não está no Canvas. O arquivo precisa ter `classe: "nota_pessoal"`, IDs únicos e tipo `avaliacao`, `quiz` ou `tarefa`. Uma data exige `curso_id`.

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

Valide primeiro, sem publicar:

```bash
python deploy/publicar_agenda.py --arquivo agenda.json --validar
```

Para publicar no estado configurado:

```bash
SURICATA_ESTADO_URI=gs://<bucket-suricata> \
  python deploy/publicar_agenda.py --arquivo agenda.json
```

O publicador faz verificação de concorrência e leitura de volta. Publicar novamente o mesmo conteúdo é idempotente e informa `agenda: já atualizada`. A agenda manual é complementar; o planejamento ainda consulta o Canvas.

## Limites importantes

- A Suricata só lê dados públicos do Canvas; não acessa notas, tentativas, submissões ou respostas.
- Uma mensagem planejada não é uma mensagem enviada. Entrega real exige destino confirmado, sessão válida, estado íntegro, janela aberta e ACK.
- Testes offline e fixtures não provam Canvas ao vivo, IAM, imagem implantada, sessão ou entrega.
- Ausência de dado não significa ausência de atividade: consulte o Canvas quando a coleta estiver parcial.

Para entender a implementação, leia [`arquitetura.md`](arquitetura.md). Para nuvem, leia [`deploy-gcp.md`](deploy-gcp.md). Para troubleshooting, [`interno/TROUBLESHOOTING.md`](interno/TROUBLESHOOTING.md).
