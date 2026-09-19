# Status Suricata
> **Interno — não normativo para lançamento público.** Contém contratos e orientação operacional genérica; valores reais exigem read-back autorizado.


Última verificação histórica (não revalidada para este lançamento): **2026-09-19**, read-back GCP, build Cloud Build e canário controlado.

## Release candidata `<id-nao-versionado>` — deploy verificado (2026-09-19)

A fonte foi validada localmente com pytest `350 passed, 90 subtests`, unittest `348 OK`, Node `39/39`, Ruff, `compileall`, `shadow` e `git diff --check`. O runtime deixou de possuir fallback para bucket real: `SuricataSessionStorage` exige `session_object` ou `SURICATA_WA_SESSION_OBJECT`; testes usam apenas URI sintética `.invalid`.

O Cloud Build `<id-nao-versionado>` terminou `SUCCESS` e publicou o digest `sha256:<digest-nao-versionado>`. O canário `<job-canario-confirmado>` foi atualizado somente para esse digest, mantendo estado separado, `--mode rodada`, `SURICATA_ENTREGA=desligada`, `maxRetries=0`, timeout `300s` e <service-account-suricata-confirmada>. A execução `<job-canario-confirmado>-rcblw` terminou `succeededCount=1`; logs sanitizados registraram somente saída normal e `exit(0)`, sem envio/ACK.

Após o canário, o Job produtivo `<job-suricata-confirmado>` foi atualizado somente para o mesmo digest, na geração `27`. Read-back confirmou `--mode rodada`, estado `gs://<projeto-suricata-confirmado>-estado`, entrega ligada, secret Canvas, destinos existentes, uma task, `maxRetries=1`, timeout `240s` e <service-account-suricata-confirmada>. O Scheduler único `<scheduler-suricata-confirmado>` continua `ENABLED`, `*/10 * * * *`, `America/Sao_Paulo`, apontando para esse Job. Não houve execução manual do Job produtivo.

## Padronização GitHub, lint, e2e e dead-letter (2026-09-18, PRs #13-#16)

Onda de padronização (decisão do titular): ruff adotado como lint oficial (193 findings corrigidos, gate no CI), higiene (.gitattributes LF, .editorconfig), README raiz reescrito no padrão GitHub (banner/badges/mermaid), docs reorganizadas para humanos (guia/arquitetura/deploy-gcp + interno/ + historico/), deploy/publicar_agenda com primeira cobertura e --dry-run, SURICATA_CONFIG opcional (env > arquivo), e2e full-stack offline com subprocesso Node real, suíte de propriedade (240 amostras), dead-letter falhas/falhas.jsonl (aditiva, fail-safe) e CI em 3 jobs (lint → tests → build com e2e de imagem). Merge squash dos PRs #13-#16; revisão independente do bot no SHA exato de cada PR; CI verde em todos os merges. Matriz final local: pytest `333+80`, unittest `331`, node `39/39`, ruff verde.

## Simplificação do CLI e subpastas (2026-09-18, PR #11)

Decisão do titular: CLI reduzido a `shadow`/`demo`/`rodada` — sentinela, teste-envio e grupos removidos com a família inteira (19 arquivos de produção + 14 de teste, `whatsapp/grupos.mjs` órfão). Runtime reorganizado em subpastas (`rodada/`, `dominio/`, `integracao/`, `storage/` consolidado) com `suricata/rodada` como pacote-fachada. Verificado localmente: matriz idêntica antes/depois (pytest `285+75`, unittest `283`, node `39/39`), clone limpo reproduzível (incl. `npm ci` do cache), shadow/demo exit 0, rodada sem env exit 5, modos removidos exit 2. Merge squash em `<id-nao-versionado>` com revisão independente do bot no SHA `<id-nao-versionado>`; CI verde no branch e na `main` pós-merge.

## Modernização open-source plug-and-play — evidência local (2026-09-18)

### Simplificação de modos (2026-09-18, decisão do titular)

CLI reduzido a `shadow`/`demo`/`rodada`; família sentinela (`sentinela`, `application`, `domain`, `adapter`, `estado`, `legacy`, `notifiers`, `delivery`, lease legado, `grupos`, `teste-envio`) removida; detalhes e provas no PR subsequente.

### Ondas anteriores

O branch `refactor/clean-architecture-domain-seams` recebeu a onda de modernização de estudante (`<id-nao-versionado>..<id-nao-versionado>`, 9 commits): guards de contrato novos (lease ativo da rodada, contrato CLI por subprocesso, schema do `_emit`, modos `grupos`/`teste-envio` fail-closed, E2E da ponte Node incondicional com stub versionado), correção de regressão real (`teste-envio` quebrado por `ImportError` desde `<id-nao-versionado>`), modo `--mode demo` offline zero-config, mensagens fail-closed acionáveis com `--help`, LICENSE MIT, packaging (`[build-system]`, classifiers, instalação do pacote verificada), CONTRIBUTING, `.env.example`, trilha do estudante de 4 níveis, quickstart com badges e `scripts/bootstrap.py`.

**Segunda onda** (`<id-nao-versionado>..<id-nao-versionado>`, 4 commits): decomposição do `storage/gcs.py` em backends próprios com facade identica (`assertIs`); quarentena dos legados em `suricata/legacy/` atrás de facades; **correção de defeito real de empacotamento** (`packages = ["suricata"]` excluía todos os subpacotes e dados de runtime do wheel — o guard `test_wheel.py` nasceu vermelho e fechou verde com find de subpacotes + package-data); pin de digest da imagem base `node:22-bookworm-slim@sha256:<id-nao-versionado>...` nos dois Dockerfiles + `docker-compose.yml` (serviço `--mode demo`, sem sessão, entrega nunca ligada); fronteiras de leases e `EXCLUIDAS` documentadas em CONTRACTS.

**Verificado localmente nesta data** (execução real, não auto-relato): pytest `399 passed, 92 subtests`; unittest `397 OK`; `node --test` `39/39`; `compileall`, `shadow` e `demo` exit 0 (demo determinístico byte a byte); wheel construído, inspecionado, instalado e executado de cwd neutro; guards de storage/legacy/wheel/container verdes em seleção focada (33 passed). **CI verificado por read-back:** verde no HEAD do branch (`<id-nao-versionado>`, runs `35403913433`/`35403910008`) e na `main` pós-merge (run `35404149614`); merge squash do PR `#9` em `<id-nao-versionado>` (2026-09-18) com revisão independente do `zc4str0-revisor-bot` aprovando exatamente o SHA `<id-nao-versionado>`. **Não verificado:** build de imagem local (Docker ausente no host — pin e compose validados estaticamente/YAML), `docker compose config`, e qualquer estado de nuvem — os fatos de produção abaixo permanecem a referência mais recente por read-back. Nota: 3 arquivos de lint do agente concorrente (`canvas.py`, `rodada.py`, `locking.py`) permanecem não-commitados na árvore local por ownership.

## Evidência mais recente — refatoração `<id-nao-versionado>`

Em **2026-09-18**, a `main` foi atualizada pelo merge squash do PR `#7` (`<sha-nao-versionado>`). O build Cloud Build `<id-nao-versionado>` terminou com `SUCCESS` e publicou a imagem por digest `sha256:<digest-nao-versionado>`.

O canário existente `<job-canario-confirmado>` foi atualizado para esse digest e lido de volta na geração `3`, mantendo `--mode rodada`, `maxRetries=0`, timeout `300s`, <service-account-suricata-confirmada>, estado separado e entrega desligada. A execução `<job-canario-confirmado>-6qbwd` terminou com `succeededCount=1` entre `17:26:01Z` e `17:26:15Z`. O Job produtivo não foi alterado e continua exigindo novo read-back antes de qualquer decisão; esta evidência não prova entrega WhatsApp.

Código local e GitHub: **verificados** — PR `#1` foi aprovado por `zc4str0-revisor-bot` (identidade distinta do autor), com CI verde no SHA `<sha-nao-versionado>`, e merge squash confirmado no commit `<sha-nao-versionado>` da `main`. A árvore local permanece sem alterações de código.

Build independente: **concluído** — Cloud Build `<id-nao-versionado>`, commit de origem `<id-nao-versionado>`, imagem `<registry-suricata-confirmado>/suricata/suricata`, digest `sha256:<digest-nao-versionado>`. O Artifact Registry confirmou o digest. A árvore de entrada da imagem permaneceu idêntica entre `<id-nao-versionado>` e a `main` promovida.

Infraestrutura: **verificada por read-back** — projeto `<projeto-suricata-confirmado>`, região `southamerica-east1`, Job `<job-suricata-confirmado>` na geração `24`, uma task, `maxRetries=1`, timeout `240s`, args `--mode rodada` e <service-account-suricata-confirmada> existente. IAM least-privilege não verificado.

Canário: **concluído sem entrega** — Job existente `<job-canario-confirmado>`, geração `2`, digest novo, args `--mode rodada`, `SURICATA_ENTREGA=desligada`, `maxRetries=0`, timeout `300s`; execução anterior terminou com `succeededCount=1`. Nenhum Scheduler aponta para o canário.

Corte controlado: **concluído sem entrega real** — o Job de produção foi atualizado somente para o digest candidato e `SURICATA_ENTREGA=desligada`; nenhum secret, IAM, args, frequência ou sessão foi alterado. O digest anterior de rollback é `sha256:<digest-anterior-nao-versionado>`.

Observação: **passou** — execução controlada `<execucao-nao-versionada>` completou com `succeededCount=1`, entre `20:21:35Z` e `20:21:50Z`. Foram encontrados dois relatórios sanitizados, `eventos=[]`, `coleta.falhas=[]` e erro nulo; não houve chamada/ACK de entrega observável nos logs. A observação posterior também confirmou `<execucao-nao-versionada>` com `succeeded=1`. Isso não prova entrega WhatsApp, que permaneceu desligada.

Scheduler: **verificado** — existe exatamente um Scheduler Suricata, `<scheduler-suricata-confirmado>`, `ENABLED`, `*/10 * * * *`, timezone `America/Sao_Paulo`, apontando para o Job de produção.

Verificação adicional em **2026-09-18**: o Job canário `<job-canario-confirmado>` foi lido de volta antes da execução e confirmou imagem por digest `sha256:<digest-nao-versionado>`, `--mode rodada`, `SURICATA_ENTREGA=desligada`, ausência de `SURICATA_GRUPO_JID`/`SURICATA_DESTINOS_JSON`, `maxRetries=0` e timeout de 300s. A execução `<job-canario-confirmado>-b6tsb` terminou com `succeededCount=1`; a leitura sanitizada de 3 entradas de log encontrou somente `INFO`, sem termos `sent`, `ack`, `delivery`, `logged_out` ou `error`. Isso valida o caminho real do Job sem validar entrega WhatsApp.

Repositório acadêmico: **intocado** — a limpeza permanece bloqueada até os gates finais de proveniência, rollback e validação completa.

Segredos: **não lidos nem expostos** — somente nomes/metadados necessários foram consultados.
