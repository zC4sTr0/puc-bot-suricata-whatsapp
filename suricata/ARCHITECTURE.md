# Arquitetura do Suricata

> **Status:** documentação reconciliada por leitura estática do código e dos documentos locais. O estado da nuvem só é afirmado quando acompanhado de data e como fato não verificado novamente.

## 1. Entrada e contrato do container

```text
python -m suricata [--mode MODO] [--config ARQUIVO]
  __main__.py → entrypoint.main()
```

O [`Dockerfile`](Dockerfile) usa:

```text
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
```

`ENTRYPOINT` fixa o módulo Python; `CMD` é apenas o argumento padrão e pode ser substituído pelo runtime. O container não recebe automaticamente o arquivo de configuração.

### Modos observados no `entrypoint.py`

| Modo | Entrada de configuração | Efeito efetivo conhecido | Uso conservador |
|---|---|---|---|
| `shadow` | nenhum arquivo; argumentos padrão do container | emite `{"mode":"shadow","status":"ok","adapter":"none"}` e termina; não consulta Canvas, não grava estado e não envia | probe de empacotamento/saúde |
| `sentinela` | exige `--config ARQUIVO`; token fica em `SURICATA_CANVAS_TOKEN` | valida JSON, cria cliente Canvas e chama `application.executar_sombra`; é uma sombra **funcional**, com coleta/planejamento e estado local opcional, sem entrega de produção | compatibilidade e simulação funcional; não chamar de probe `shadow` |
| `rodada` | ambiente; `rodada.main()` | caminho funcional canônico: coleta, planejamento, estado/outbox e entrega condicionada por `SURICATA_ENTREGA` e pelo corte | produção, somente com pré-voo e autorização de deploy/execução |
| `grupos` | ambiente, incluindo `SURICATA_ESTADO_URI` | consulta a sessão/estado para inventariar grupos; não é envio, mas pode tocar GCS/WhatsApp | diagnóstico read-only, com escopo explícito |
| `teste-envio` | ambiente, incluindo estado e JID | envia mensagem de teste; é efeito externo | proibido no pré-voo; somente gate humano explícito |

Argumentos ausentes, inválidos ou configuração inválida falham com código não-zero. Exceções externas são sanitizadas; não se deve interpretar `status: ok` de `shadow` como prova de Canvas, GCS ou WhatsApp saudáveis.

## 2. Configuração por fonte e por efeito

### `sentinela`: arquivo explícito

`--config` aceita JSON público com `ofertas` não vazio, `canvas.origin` allowlisted, `canvas.timeout` positivo e `estado.path` ou `state_path` opcional. Chaves de segredo (`token`, `access_token`, `authorization`, `secret`) são rejeitadas. O exemplo é [`config.example.json`](config.example.json).

O arquivo seleciona ofertas e parâmetros de consulta; o token continua sendo obtido internamente pelo cliente a partir de `SURICATA_CANVAS_TOKEN`. O relatório é emitido em stdout sanitizado. O modo é sombra funcional: não equivale ao pipeline `rodada` nem prova que um Job de produção o utiliza.

### `rodada`, `grupos` e `teste-envio`: ambiente

Variáveis observadas no código:

| Variável | Papel | Efeito/risco |
|---|---|---|
| `SURICATA_CANVAS_TOKEN` | credencial Canvas | obrigatória para `rodada`; nunca imprimir, versionar ou passar por argv |
| `SURICATA_ESTADO_URI` | backend de estado/sessão | ausente bloqueia caminhos que precisam de estado |
| `SURICATA_ENTREGA` | liga entrega quando exatamente `ligada` | qualquer outro valor resulta em entrega desligada no caminho da rodada |
| `SURICATA_GRUPO_JID` | destino legado | habilita o destino configurado; exige JID confirmado |
| `SURICATA_DESTINOS_JSON` / `SURICATA_DESTINOS` | destinos adicionais | JSON/lista validada; memória e outbox ficam namespaced por destino |
| `SURICATA_LEASE_MINUTOS` | lease da rodada | padrão observado: `6`; valor inválido deve falhar fechado |
| `SURICATA_WA_AUTH_DIR` | diretório de auth usado pela ponte Node | segredo operacional; nunca apontar para caminho versionado ou registrar conteúdo |

A fonte canônica dos valores de ambiente de uma execução é o ambiente do processo/Job, não `config.example.json`. O documento [`infra/isolamento.json`](infra/isolamento.json) é inventário declarativo e não injeta configuração no runtime.

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

1. Não remover `sentinela`, `application`, `domain`, `grupo`, `delivery`, `estado` ou `storage/cas` por parecerem legados: os testes ainda os cobrem e a equivalência não foi provada.
   - Os legados em quarentena (`delivery`, `notifiers/whatsapp`, `lease`, `grupo`) vivem em `suricata/legacy/`, atrás de facades de compatibilidade nas origens; a regra de não-remoção permanece.
2. Não transformar `shadow` em alias funcional de `sentinela`; são contratos diferentes.
3. Não trocar configuração de ambiente por JSON sem alterar e testar explicitamente o contrato.
4. Não ligar entrega, parear sessão, executar `teste-envio`, atualizar Job/Scheduler, publicar imagem ou fazer deploy como parte de validação local.
5. Teste offline verde prova apenas o contrato local. Não prova IAM, build limpo, digest implantado, Cloud Run, Canvas ao vivo, sessão ou WhatsApp.

## 7. Verificação local

```bash
python -m compileall -q suricata
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Para operação humana e gates, use [`RUNBOOK.md`](RUNBOOK.md).