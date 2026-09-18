# Status Suricata

Última verificação: **2026-09-17**, read-back GitHub/GCP e execução controlada do Job.

## Modernização open-source plug-and-play — evidência local (2026-09-18)

O branch `refactor/clean-architecture-domain-seams` recebeu a onda de modernização de estudante (`5191a05..fbe82da`, 9 commits): guards de contrato novos (lease ativo da rodada, contrato CLI por subprocesso, schema do `_emit`, modos `grupos`/`teste-envio` fail-closed, E2E da ponte Node incondicional com stub versionado), correção de regressão real (`teste-envio` quebrado por `ImportError` desde `dd89264`), modo `--mode demo` offline zero-config, mensagens fail-closed acionáveis com `--help`, LICENSE MIT, packaging (`[build-system]`, classifiers, instalação do pacote verificada), CONTRIBUTING, `.env.example`, trilha do estudante de 4 níveis, quickstart com badges e `scripts/bootstrap.py`.

**Segunda onda** (`be9cc00..680ed02`, 4 commits): decomposição do `storage/gcs.py` em backends próprios com facade identica (`assertIs`); quarentena dos legados em `suricata/legacy/` atrás de facades; **correção de defeito real de empacotamento** (`packages = ["suricata"]` excluía todos os subpacotes e dados de runtime do wheel — o guard `test_wheel.py` nasceu vermelho e fechou verde com find de subpacotes + package-data); pin de digest da imagem base `node:22-bookworm-slim@sha256:83f487e0...` nos dois Dockerfiles + `docker-compose.yml` (serviço `--mode demo`, sem sessão, entrega nunca ligada); fronteiras de leases e `EXCLUIDAS` documentadas em CONTRACTS.

**Verificado localmente nesta data** (execução real, não auto-relato): pytest `399 passed, 92 subtests`; unittest `397 OK`; `node --test` `39/39`; `compileall`, `shadow` e `demo` exit 0 (demo determinístico byte a byte); wheel construído, inspecionado, instalado e executado de cwd neutro; guards de storage/legacy/wheel/container verdes em seleção focada (33 passed). **Não verificado:** CI no GitHub deste HEAD (push em andamento), build de imagem local (Docker ausente no host — pin e compose validados estaticamente/YAML), `docker compose config`, e qualquer estado de nuvem — os fatos de produção abaixo permanecem a referência mais recente por read-back. Nota: 3 arquivos de lint do agente concorrente (`canvas.py`, `rodada.py`, `locking.py`) permanecem não-commitados na árvore local por ownership.

## Evidência mais recente — refatoração `5ed8313`

Em **2026-09-18**, a `main` foi atualizada pelo merge squash do PR `#7` (`5ed8313eab7b96dc3168408570a5b1078cadbbbb`). O build Cloud Build `6d73fced-fe0e-4ecd-bc8a-c6efc558e4ff` terminou com `SUCCESS` e publicou a imagem por digest `sha256:f67059b591ab39021ecbcff6ffb4e85df46f5e964dddb10c922f26454c121925`.

O canário existente `suricata-canario-prod` foi atualizado para esse digest e lido de volta na geração `3`, mantendo `--mode rodada`, `maxRetries=0`, timeout `300s`, service account Suricata, estado separado e entrega desligada. A execução `suricata-canario-prod-6qbwd` terminou com `succeededCount=1` entre `17:26:01Z` e `17:26:15Z`. O Job produtivo não foi alterado e continua exigindo novo read-back antes de qualquer decisão; esta evidência não prova entrega WhatsApp.

Código local e GitHub: **verificados** — PR `#1` foi aprovado por `zc4str0-revisor-bot` (identidade distinta do autor), com CI verde no SHA `561aa0b0656a83a37a94cd1be3bab33d92f6e199`, e merge squash confirmado no commit `30c5b2ff310a49a5cd57acd659676a0973cdeee6` da `main`. A árvore local permanece sem alterações de código.

Build independente: **concluído** — Cloud Build `1e200017-3da4-4c6e-8302-12f478b2e636`, commit de origem `203f0a3`, imagem `southamerica-east1-docker.pkg.dev/suricata-college-20260913/suricata/suricata`, digest `sha256:6071de09eb357e35f091173407760aabda091b5eb8f0f3e2c533dae9caa32f98`. O Artifact Registry confirmou o digest. A árvore de entrada da imagem permaneceu idêntica entre `203f0a3` e a `main` promovida.

Infraestrutura: **verificada por read-back** — projeto `suricata-college-20260913`, região `southamerica-east1`, Job `suricata-rodada` na geração `24`, uma task, `maxRetries=1`, timeout `240s`, args `--mode rodada` e service account Suricata existente. IAM least-privilege não verificado.

Canário: **concluído sem entrega** — Job existente `suricata-canario-prod`, geração `2`, digest novo, args `--mode rodada`, `SURICATA_ENTREGA=desligada`, `maxRetries=0`, timeout `300s`; execução anterior terminou com `succeededCount=1`. Nenhum Scheduler aponta para o canário.

Corte controlado: **concluído sem entrega real** — o Job de produção foi atualizado somente para o digest candidato e `SURICATA_ENTREGA=desligada`; nenhum secret, IAM, args, frequência ou sessão foi alterado. O digest anterior de rollback é `sha256:9622db22436d366a2b1b6224479eb5b3b6c5a66da4f5a8fe5da468216de763c3`.

Observação: **passou** — execução controlada `suricata-rodada-t2nsm` completou com `succeededCount=1`, entre `20:21:35Z` e `20:21:50Z`. Foram encontrados dois relatórios sanitizados, `eventos=[]`, `coleta.falhas=[]` e erro nulo; não houve chamada/ACK de entrega observável nos logs. A observação posterior também confirmou `suricata-rodada-4w22x` com `succeeded=1`. Isso não prova entrega WhatsApp, que permaneceu desligada.

Scheduler: **verificado** — existe exatamente um Scheduler Suricata, `suricata-rodada-10min`, `ENABLED`, `*/10 * * * *`, timezone `America/Sao_Paulo`, apontando para o Job de produção.

Verificação adicional em **2026-09-18**: o Job canário `suricata-canario-prod` foi lido de volta antes da execução e confirmou imagem por digest `sha256:6071de09eb357e35f091173407760aabda091b5eb8f0f3e2c533dae9caa32f98`, `--mode rodada`, `SURICATA_ENTREGA=desligada`, ausência de `SURICATA_GRUPO_JID`/`SURICATA_DESTINOS_JSON`, `maxRetries=0` e timeout de 300s. A execução `suricata-canario-prod-b6tsb` terminou com `succeededCount=1`; a leitura sanitizada de 3 entradas de log encontrou somente `INFO`, sem termos `sent`, `ack`, `delivery`, `logged_out` ou `error`. Isso valida o caminho real do Job sem validar entrega WhatsApp.

Repositório acadêmico: **intocado** — a limpeza permanece bloqueada até os gates finais de proveniência, rollback e validação completa.

Segredos: **não lidos nem expostos** — somente nomes/metadados necessários foram consultados.
