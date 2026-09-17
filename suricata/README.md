# Suricata College

> **Escopo:** bot público e separado para avisos da turma no WhatsApp. Esta pasta não é o Bot acadêmico pessoal do Telegram.

O Suricata consulta dados públicos do Canvas por `GET`, planeja eventos para uma audiência configurada e pode entregar mensagens por uma ponte Python → Node → Baileys. A sessão do WhatsApp, tokens e estado operacional são segredos: não entram no Git, na imagem, nos logs ou nas mensagens.

## Como rodar e onde procurar

### Teste local em 30 segundos

Para conferir o pacote sem Canvas, rede, estado ou envio:

```bash
python -m suricata --mode shadow
```

Para acompanhar o caminho Python sem efeitos externos, leia os testes offline em `tests/README.md`. O comando de produção é diferente: `python -m suricata --mode rodada` consulta o ambiente configurado e pode enviar mensagens.

### Os cinco modos

| Modo | O que faz | Envia? |
|---|---|---:|
| `shadow` | Probe local do container; emite JSON e termina. | Não |
| `sentinela` | Caminho funcional de sombra, com `--config` explícito. | Não por padrão |
| `rodada` | Caminho canônico: Canvas → planejamento → outbox → ponte WhatsApp. | Condicionado ao ambiente |
| `grupos` | Inventaria grupos da sessão; não publica mensagens. | Não |
| `teste-envio` | Exercício explícito de envio/idempotência. | Sim |

### Onde está cada coisa?

| Pergunta | Caminho |
|---|---|
| Onde as mensagens do grupo são escritas? | `publico.py` e `planejamento.py`; a orquestração está em `rodada.py`. |
| Onde fica o Docker? | `Dockerfile` desta pasta. |
| Onde fica o código WhatsApp/Node? | `whatsapp/`; a ponte Python é `bridge.py`. |
| Onde ficam os testes? | `tests/` (Python e contratos Node) e `whatsapp/tests/` (testes do pacote Node). |
| Onde fica a configuração? | `config.example.json` para `sentinela`; ambiente para `rodada`, `grupos` e `teste-envio`; detalhes em `ARCHITECTURE.md`. |
| Onde está o corte das 21h? | `rodada.py`, com testes em `tests/test_corte_21h*.py`. |
| Onde estão outbox e ACK? | `outbox.py`, `persistencia_rodada.py`, `bridge.py` e `whatsapp/enviar.mjs`. |
| Por onde começa? | `__main__.py` → `entrypoint.py`. |

### Ordem de leitura recomendada

1. `__main__.py` — ponto de entrada de `python -m suricata`.
2. `entrypoint.py` — valida argumentos e encaminha o modo.
3. `rodada.py` — compõe o runtime e preserva os imports históricos.
4. `coleta.py` — consulta e normaliza a coleta pública.
5. `planejamento.py` e `publico.py` — decidem e escrevem o texto das mensagens.
6. `execucao.py` — executa lease, memória, outbox, corte e entrega.
7. `outbox.py` e `bridge.py` — persistem tentativas e chamam o Node.
8. `whatsapp/enviar.mjs` — envia e aguarda o ACK do WhatsApp.

O Job de produção é executado em Cloud Run por um Scheduler, usando a imagem construída por este `Dockerfile`; os nomes e o estado atuais da nuvem continuam não verificados sem read-back. Não confunda o Suricata com o Bot Acadêmico do Telegram.

## Comece pela documentação certa

- [`DOCUMENTATION.md`](DOCUMENTATION.md) — índice por tarefa e limites de evidência.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — entrada, modos, configuração e fronteiras.
- [`RUNBOOK.md`](RUNBOOK.md) — operação humana conservadora, pré-voo, gates e parada.
- [`tests/README.md`](tests/README.md) — suíte offline e o que ela não prova.
- [`whatsapp/README.md`](whatsapp/README.md) — contratos da camada Node/WhatsApp.
- [`../docs/PLANO-SURICATA-WHATSAPP.md`](../docs/PLANO-SURICATA-WHATSAPP.md) — plano executável e decisões datadas.
- [`infra/README.md`](infra/README.md) e [`infra/isolamento.json`](infra/isolamento.json) — fronteira e inventário declarativo da infraestrutura.

## Execução local sem efeitos externos

Na raiz do repositório:

```bash
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Esses comandos são offline por desenho. Não conectam ao Canvas, GCS ou WhatsApp real. Para uma simulação funcional sem entrega, use o contrato descrito em [`RUNBOOK.md`](RUNBOOK.md), não ligue `SURICATA_ENTREGA`.

## Entrada do container

O [`Dockerfile`](Dockerfile) declara exatamente:

```text
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
```

Portanto, sem sobrescrever o comando, o container executa a **probe `shadow`**, que só emite um registro local de saúde. O caminho funcional de produção precisa ser selecionado explicitamente com `--mode rodada`; o `CMD` não o seleciona sozinho.

O arquivo de exemplo [`config.example.json`](config.example.json) é para o modo `sentinela`, com `--config` explícito. Ele contém apenas placeholder público; não coloque token, sessão, JID real ou dados pessoais nele.

## Configuração e isolamento

- `rodada`, `grupos` e `teste-envio` leem configuração do ambiente; não usam `config.example.json` automaticamente.
- `sentinela` exige `--config ARQUIVO`; o arquivo fornece ofertas, origem/timeout do Canvas e estado local opcional. O token nunca é aceito no JSON e é resolvido pelo cliente via `SURICATA_CANVAS_TOKEN`.
- O runtime funcional usa, entre outras, `SURICATA_ESTADO_URI`, `SURICATA_CANVAS_TOKEN`, `SURICATA_ENTREGA`, `SURICATA_GRUPO_JID`, `SURICATA_DESTINOS_JSON` (ou `SURICATA_DESTINOS`) e `SURICATA_LEASE_MINUTOS`. Consulte [`ARCHITECTURE.md`](ARCHITECTURE.md) para efeitos por modo.
- Projeto GCP, bucket, Artifact Registry, service account, secrets, Jobs e Schedulers devem ter namespace Suricata; os recursos do Bot Telegram continuam fora da fronteira.
- O registro [`infra/isolamento.json`](infra/isolamento.json) preserva um snapshot histórico, datado de 2026-09-16, de um Job `suricata-rodada` e um Scheduler `suricata-rodada-10min` registrados como ativos. Isso não prova estado atual nem correspondência entre imagem implantada e código local.
- IAM least-privilege, build limpo, clone limpo, digest implantado e estado atual da nuvem permanecem não verificados até novo read-back. Para a revalidação, siga [`RUNBOOK.md`](RUNBOOK.md).

## Não confundir

`shadow` é uma probe sem coleta e sem efeito funcional. `sentinela` é o caminho funcional antigo de sombra, que exige configuração explícita e consulta/planeja por `application.executar_sombra()`. `rodada` é o caminho funcional canônico atual e pode entregar somente quando o ambiente e as regras de corte autorizam. Nenhum nome de Job ou Scheduler torna um modo seguro por si só.
