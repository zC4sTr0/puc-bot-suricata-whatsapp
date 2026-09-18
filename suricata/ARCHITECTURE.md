# Arquitetura do Suricata

> **Status:** documentação reconciliada por leitura estática do código e dos documentos locais. O estado da nuvem só é afirmado quando acompanhado de data e como fato não verificado novamente.

## 1. Entrada e contrato do container

```text
python -m suricata [--mode MODO]
  __main__.py → entrypoint.main()
```

O [`Dockerfile`](Dockerfile) usa:

```text
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
```

`ENTRYPOINT` fixa o módulo Python; `CMD` é apenas o argumento padrão e pode ser substituído pelo runtime. O container não recebe automaticamente nenhum arquivo de configuração.

### Modos observados no `entrypoint.py`

O CLI tem três modos, definidos na simplificação de 2026-09-18 (`sentinela`, `grupos` e `teste-envio` foram removidos; o histórico vive no git):

| Modo | Entrada de configuração | Efeito efetivo conhecido | Uso conservador |
|---|---|---|---|
| `shadow` | nenhuma; argumentos padrão do container | emite `{"mode":"shadow","status":"ok","adapter":"none"}` e termina; não consulta Canvas, não grava estado e não envia | probe de empacotamento/saúde; usada pelo CI e pelo Docker |
| `demo` | nenhuma; fixtures congeladas | roda a rodada offline com entrega desligada; planeja avisos e imprime relatório, sem Canvas, estado ou ponte | estudo e verificação local do planejamento |
| `rodada` | ambiente; `rodada.main()` | caminho funcional canônico: coleta, planejamento, estado/outbox e entrega condicionada por `SURICATA_ENTREGA` e pelo corte | produção, somente com pré-voo e autorização de deploy/execução |

Argumentos ausentes, inválidos ou configuração inválida falham com código não-zero. Exceções externas são sanitizadas; não se deve interpretar `status: ok` de `shadow` como prova de Canvas, GCS ou WhatsApp saudáveis.

## 2. Configuração: vem do ambiente

Não existe mais arquivo de configuração de modo. Toda configuração funcional vem do ambiente do processo (ou do Secret Manager, que materializa o ambiente no Job); o módulo `config.py` valida e materializa os destinos.

Variáveis observadas no código:

| Variável | Papel | Efeito/risco |
|---|---|---|
| `SURICATA_CANVAS_TOKEN` | credencial Canvas | obrigatória para `rodada`; nunca imprimir, versionar ou passar por argv |
| `SURICATA_ESTADO_URI` | backend de estado/sessão | ausente bloqueia caminhos que precisam de estado |
| `SURICATA_ENTREGA` | liga entrega quando exatamente `ligada` | qualquer outro valor resulta em entrega desligada no caminho da rodada |
| `SURICATA_GRUPO_JID` | destino da rodada | habilita o destino configurado; exige JID confirmado |
| `SURICATA_DESTINOS_JSON` / `SURICATA_DESTINOS` | destinos adicionais | JSON/lista validada; memória e outbox ficam namespaced por destino |
| `SURICATA_LEASE_MINUTOS` | lease da rodada | padrão observado: `6`; valor inválido deve falhar fechado |
| `SURICATA_WA_AUTH_DIR` | diretório de auth usado pela ponte Node | segredo operacional; nunca apontar para caminho versionado ou registrar conteúdo |

A fonte canônica dos valores de ambiente de uma execução é o ambiente do processo/Job. O documento [`infra/isolamento.json`](infra/isolamento.json) é inventário declarativo e não injeta configuração no runtime.

## 3. Caminho canônico `rodada`

```text
rodada.main
  → Canvas (somente GET)
  → coleta compartilhada
  → planejamento público por destino
  → memória/outbox/relatório
  → corte BRT antes de claim e ponte
  → ponte Python → whatsapp/enviar.mjs → Baileys
```

A rodada atual é o caminho funcional canônico local. O envio só é possível quando `SURICATA_ENTREGA=ligada`, há destino/estado/sessão válidos, o evento é elegível e o relógio está na janela permitida. O corte absoluto começa às 21:00 em `America/Sao_Paulo`; acordar por Scheduler não autoriza envio. ACK válido é necessário para marcar `sent`. Falha parcial de coleta não significa ausência.

O contrato de estado e recuperação é: `pending → in_flight → sent`; falha/timeout retorna a `pending`; `sent` e `expirado` são terminais. A sessão é materializada temporariamente e persistida por CAS/read-back no armazenamento Suricata.

## 4. Fronteiras

- **Canvas → domínio:** somente dados públicos; nunca `submission`, nota, quiz aberto ou tentativa iniciada.
- **Python → Node:** lote JSON por stdin; resposta sanitizada por stdout; Node não é dono do estado.
- **Node → WhatsApp:** único efeito externo de mensagem; somente ACK compatível autoriza `sent`.
- **Runtime → GCP:** apenas recursos namespaceados do Suricata. Não importar `scripts.academico`, `academico/estado/`, secrets, bucket ou schedulers do Bot Telegram.
- **Código local → imagem:** Docker copia o contexto `suricata/`, instala dependências Node pelo lockfile e não deve incluir auth, QR, sessão, bancos ou segredos.

## 5. Job e Scheduler: nomenclatura reconciliada

Há nomes divergentes entre o plano histórico e o inventário local. O plano menciona `suricata-sentinela`/`suricata-sentinela-10min`; o `infra/isolamento.json` registra, em **2026-09-16**, `suricata-rodada` e `suricata-rodada-10min` e uma execução `suricata-rodada-hd9gb` concluída. Trate isso somente como **fatos datados, não verificados novamente**. Não deduza que os nomes atuais, imagem, argumentos, agenda ou estado sejam esses; faça read-back com `gcloud` antes de qualquer ação.

## 6. Limites de manutenção

1. A família legada (`sentinela`, `application`, `domain`, `adapter`, `estado`, `grupo`, `delivery`, `lease` legado, `notifiers/`, `legacy/`) foi **removida por decisão do titular em 2026-09-18**, na simplificação que reduziu o CLI a `shadow`/`demo`/`rodada`. O histórico completo — código e testes — vive no git; não reintroduza esses módulos nem fachadas de compatibilidade com eles.
2. Não transformar `shadow` em alias funcional de `demo` ou `rodada`: `shadow` é probe sem coleta, `demo` é rodada offline com fixtures, `rodada` é o caminho canônico com efeitos condicionados. São três contratos diferentes.
3. Não trocar configuração de ambiente por arquivo JSON: a configuração vem do ambiente do processo.
4. Não ligar entrega, parear sessão, atualizar Job/Scheduler, publicar imagem ou fazer deploy como parte de validação local.
5. Fail-closed permanece regra: falta de configuração, estado, lease ou ACK deve falhar a execução, nunca degradar para "sucesso".
6. CAS e outbox são contratos de concorrência; qualquer mudança neles exige prova de equivalência antes.
7. Teste offline verde prova apenas o contrato local. Não prova IAM, build limpo, digest implantado, Cloud Run, Canvas ao vivo, sessão ou WhatsApp.

## 7. Verificação local

```bash
python -m compileall -q suricata
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Para operação humana e gates, use [`RUNBOOK.md`](RUNBOOK.md).