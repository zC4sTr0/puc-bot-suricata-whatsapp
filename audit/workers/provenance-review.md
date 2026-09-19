# Auditoria de proveniência, CI e gates de promoção

**Escopo:** revisão somente leitura da branch `deploy/same-behavior-hardening-20260919` em `e20049f`, sem Docker, Cloud Build, `gcloud`, execução de Job, leitura de secrets ou mutação de infraestrutura.

**Fontes lidas:** `Dockerfile`, `.dockerignore`, `.gcloudignore`, `suricata/Dockerfile`, `suricata/.dockerignore`, `suricata/.gcloudignore`, `.github/workflows/suricata.yml`, `pyproject.toml`, `docker-compose.yml`, `docs/deploy-gcp.md`, `docs/interno/STATUS.md`, `suricata/tests/test_container_layout.py`, histórico e estado Git.

## Estado observado

- Branch atual: `deploy/same-behavior-hardening-20260919`; `HEAD=e20049f` (`ci: trigger on root markdown changes`). Não há upstream configurado para esta branch local.
- A árvore já tinha `audit/` não rastreado; este relatório é o único arquivo criado por este trabalho. Nenhum arquivo de produto foi editado.
- Não há resultado novo de Docker, Cloud Build, Artifact Registry, Cloud Run ou Scheduler neste trabalho. Os relatos em `docs/interno/STATUS.md` são referências históricas e não foram revalidados.

## Achados

### A1 — Gate testa um Dockerfile/contexto diferente do que o CI constrói (alto)

O job `build` executa `docker build ... .` na raiz (`.github/workflows/suricata.yml:49-58`), portanto usa o `Dockerfile` e os ignores da raiz. Porém `suricata/tests/test_container_layout.py:10,48-50` define `ROOT=suricata/` e valida `suricata/Dockerfile`, `suricata/.dockerignore` e `suricata/.gcloudignore`. Os Dockerfiles não são iguais: a raiz copia `suricata/...` para `/app/suricata` e instala `git`; o aninhado espera contexto `suricata/`, copia `whatsapp/...` e instala também `openssh-client`.

**Implicação:** os testes de layout podem passar enquanto o artefato produzido pelo job usa outro conjunto de instruções e fronteiras de contexto. Antes de promover, deve haver uma fonte única de build, ou testes explícitos contra exatamente o Dockerfile/contexto invocados pelo CI e pelo runbook.

### A2 — Runbook e histórico ainda apresentam dois comandos de contexto (médio)

`docs/deploy-gcp.md:90-93` prescreve `gcloud builds submit .`, coerente com o Dockerfile raiz e o workflow. Mas `suricata/Dockerfile:2` documenta `gcloud builds submit suricata`, e documentos históricos também registram esse contexto. O texto histórico não é necessariamente normativo, mas pode induzir uma build diferente da validada pelo CI.

**Correção necessária antes do build:** declarar em um único lugar o par canônico `(contexto, Dockerfile)` e marcar o caminho alternativo como obsoleto ou validá-lo separadamente. Não usar o comando histórico por cópia.

### A3 — Imagem não é completamente reprodutível só por pin da base (médio)

Os dois Dockerfiles fixam a base `node:22-bookworm-slim@sha256:...`, mas fazem `apt-get update`/`apt-get install` sem versões e `npm ci` instala pacotes do lockfile. O comentário de `suricata/Dockerfile:4` reconhece o risco residual. O CI usa `docker build --pull`, e o Cloud Build do runbook também não fixa versão do builder/apt.

**Gate:** registrar digest final, commit/árvore de entrada, Dockerfile/contexto e logs do build; tratar mudanças de pacotes apt ou base como mudança de proveniência. Digest da base não basta para alegar reprodução bit a bit.

### A4 — CI verifica o arquivo do teste, não necessariamente o artefato do job (médio)

O job `tests` roda a suíte que inspeciona o Dockerfile aninhado; o job `build` constrói a raiz. O `docker run` (`.github/workflows/suricata.yml:57-58`) é uma boa prova de que a imagem construída inicia em modo demo, mas não cobre exclusão de secrets/estado na imagem nem compara o conteúdo esperado do runtime.

**Gate:** no clone limpo, validar o contexto efetivo, executar a suíte de layout contra o Dockerfile efetivo e inspecionar a imagem construída antes de qualquer digest ser elegível para canário.

### A5 — Status e documentação não são prova de promoção desta branch (médio)

`docs/interno/STATUS.md:25` cita CI/commit `f3959ae`, e as seções seguintes citam builds/digests de commits anteriores (`203f0a3`, `5ed8313` etc.). O `HEAD` revisado é `e20049f`. `docs/deploy-gcp.md:3-6` corretamente chama os dados de snapshot e exige read-back, mas qualquer digest/execução descrito no STATUS não deve ser associado automaticamente a esta branch.

**Gate:** para esta promoção, anexar a relação verificável `commit exato -> árvore limpa -> contexto/Dockerfile -> build ID -> digest -> inspeção -> canário`. Se algum elo não puder ser lido de volta, bloquear.

### A6 — Trigger cobre o Dockerfile raiz, mas não declara o Dockerfile aninhado como item próprio (baixo/médio)

O `paths` do workflow inclui `suricata/**`, então alterações em `suricata/Dockerfile` disparam CI; contudo o build usa o Dockerfile raiz. Isso é seguro quanto a disparar o workflow, mas não quanto a validar a proveniência do arquivo alterado. Alterações em arquivos fora dos padrões declarados também precisam ser conferidas contra o contexto real antes de promoção.

## Gates obrigatórios antes de construir

1. **Identidade:** confirmar SHA completo, branch, remoto, base pretendida e árvore limpa. Não construir com `audit/` ou qualquer outro untracked presente, salvo se o artefato estiver deliberadamente incluído e registrado.
2. **Fonte única:** decidir e registrar `contexto=.` + `Dockerfile=./Dockerfile` (caminho usado pelo CI e pelo runbook atual), ou mudar o processo antes do build. Não alternar para `suricata/` informalmente.
3. **Diff de proveniência:** revisar mudanças em Dockerfiles, ignores, lockfile, `pyproject.toml`, workflow e scripts de packaging; verificar que o lockfile usado é o mesmo copiado pelo Dockerfile efetivo.
4. **Exclusões:** em um clone limpo, provar que contexto e upload não contêm `auth.json`, `.env*`, `.wa-auth*`, sessões, QR, logs, bancos, chaves, `node_modules` ou caches. Inspeção deve cobrir o contexto efetivo, não apenas os ignores aninhados.
5. **CI:** obter uma execução concluída para o SHA exato, com `lint`, `tests` e `build` verdes. Confirmar que a execução não foi cancelada, não é de outro SHA e não é apenas `workflow_dispatch` de uma ref diferente.
6. **Testes:** repetir lint, pytest, unittest, compileall, Node e smoke da imagem em clone limpo; registrar saídas e versões. Falha, ausência de run ou check inconclusivo bloqueia.
7. **Reprodutibilidade:** registrar digest da base, versão/lock Node, resolução apt observada, builder, contexto e hash do commit. Não chamar o artefato de reproduzível apenas porque a base está digest-pinned.

## Gates obrigatórios antes do canário

1. Confirmar no Artifact Registry, por leitura, que o digest existe e corresponde ao build ID e ao SHA exato; rejeitar tag mutável como identidade.
2. Inspecionar o manifesto/config da imagem por digest: `Entrypoint`, `Cmd`, usuário não-root `suricata`, labels, arquitetura, camadas e ausência de arquivos proibidos.
3. Confirmar que `python3 -m suricata --mode demo` funciona na imagem exata; conferir que o canário usará `--mode rodada`, entrega desligada, estado separado, zero destinos reais, `maxRetries=0` e timeout documentado.
4. Ler de volta configuração do canário antes e depois de qualquer atualização autorizada; conferir imagem por digest, args, env não secretos, service account, retries, timeout e bucket/estado separado.
5. Observar execução e logs sanitizados somente por leitura: sucesso do Job não prova envio. Qualquer evento de entrega, destino inesperado, segredo no log ou divergência de configuração bloqueia.

## Gates obrigatórios antes da promoção

1. CI verde no SHA candidato e clone limpo verde; nenhum check ausente, pendente, cancelado ou pertencente a outro commit.
2. Digest final aprovado pelo canário e comparado novamente com o digest candidato; registrar digest anterior para rollback.
3. Read-back do Job de produção antes da mudança: imagem atual, args, env, retries, timeout, service account e referência ao estado.
4. Confirmar que há exatamente um Scheduler Suricata, frequência/timezone esperados e alvo correto; listar também Jobs para detectar nomes duplicados.
5. Exigir autorização separada para a atualização do Job. A ação de promoção não deve criar Scheduler, mudar IAM, secrets, frequência, estado ou destinos.
6. Após a atualização autorizada, ler de volta o Job exato e comparar campo a campo com o plano. Em divergência, parar; não “corrigir” com comandos adicionais sem nova autorização.
7. Manter rollback pelo digest anterior conhecido e registrar observação. `Succeeded` prova execução, não entrega WhatsApp; contadores/ACK e autorização humana continuam gates distintos.

## Checklist de clone limpo e inspeção do artefato

Executar em diretório temporário, sem copiar sessão ou secrets:

```bash
TMP="$(mktemp -d)"
git clone --branch deploy/same-behavior-hardening-20260919 --no-tags \
  https://github.com/zC4sTr0/suricata-whatsapp.git "$TMP/repo"
cd "$TMP/repo"
git status --short --branch
git rev-parse HEAD
git ls-files -co --exclude-standard
# Deve não haver untracked sensível nem artefato gerado.
python -m pip install --disable-pip-version-check --no-input 'ruff==0.16.8' 'pytest==8.3.5' build
npm ci --prefix suricata/whatsapp --ignore-scripts --no-audit --no-fund
ruff check .
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
python -m compileall -q suricata
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Antes de construir, registrar os arquivos e o par canônico:

```bash
git rev-parse HEAD
git status --porcelain=v1
sha256sum Dockerfile .dockerignore .gcloudignore \
  suricata/whatsapp/package.json suricata/whatsapp/package-lock.json
# Confirmar manualmente que o CI usa: docker build ... . (Dockerfile raiz)
```

Inspeção local, somente se Docker já estiver disponível; estes comandos não publicam nem alteram cloud:

```bash
docker build --pull --file Dockerfile --tag suricata-provenance:<FULL_SHA> .
docker image inspect suricata-provenance:<FULL_SHA> \
  --format '{{json .Config}}'
docker history --no-trunc suricata-provenance:<FULL_SHA>
docker run --rm --entrypoint python3 suricata-provenance:<FULL_SHA> \
  -m suricata --mode demo
# Exportar/inspecionar conteúdo somente em diretório temporário:
docker save suricata-provenance:<FULL_SHA> -o "$TMP/image.tar"
# Usar uma ferramenta de inspeção instalada (ex.: tar/listagem) e procurar:
# auth.json, .env, .wa-auth, session, QR, *.db, *.sqlite, *.pem, *.key,
# node_modules/.bin desnecessário e caches.
```

A inspeção acima é proposta, não resultado deste trabalho: Docker não foi executado aqui.

## Checklist de read-back seguro (sem mutação)

Os comandos abaixo são consultas. Substituir valores por identificadores confirmados; não usar `builds submit`, `jobs update` ou `jobs execute` nesta revisão.

```bash
# GitHub/CI: leitura
SHA="$(git rev-parse HEAD)"
gh run list --workflow suricata.yml --limit 20 \
  --json databaseId,headSha,status,conclusion,event,workflowName,updatedAt
# Para uma run escolhida, conferir logs/status sem aprovar ou disparar nada:
gh run view RUN_ID --json headSha,status,conclusion,jobs,url

gcloud config get-value project
gcloud projects describe PROJECT --format='yaml(projectId,lifecycleState)' --quiet
gcloud run jobs list --region REGION --project PROJECT \
  --format='table(name,latestCreatedExecution)' --quiet
gcloud run jobs describe JOB --region REGION --project PROJECT \
  --format='yaml(name,uid,generation,template.template.containers,template.template.timeout,template.template.maxRetries)' --quiet
gcloud run jobs describe CANARY --region REGION --project PROJECT \
  --format='yaml(name,uid,generation,template.template.containers,template.template.timeout,template.template.maxRetries)' --quiet
gcloud scheduler jobs list --location REGION --project PROJECT \
  --format='table(name,state,schedule,timeZone)' --quiet
gcloud scheduler jobs describe SCHEDULER --location REGION --project PROJECT \
  --format='yaml(name,state,schedule,timeZone,httpTarget.uri)' --quiet
gcloud artifacts repositories list --location REGION --project PROJECT \
  --format='table(name,format)' --quiet
gcloud artifacts docker images list REPOSITORY \
  --include-tags --format='table(package,version,updateTime)' --project PROJECT
# Descrever o digest candidato; não usar tag como prova final.
gcloud artifacts docker images describe REPOSITORY@sha256:DIGEST \
  --project PROJECT --format='yaml(image_summary,build_time,media_type)' \
  --quiet
gcloud storage ls "gs://BUCKET/" --project PROJECT
```

**Restrições:** não usar `gcloud secrets versions access`, não imprimir envs secretos, não baixar sessão/estado, não executar Job e não aceitar snapshot de `STATUS.md` como substituto do read-back. Para logs, usar somente uma consulta sanitizada e autorizada, com filtro mínimo e sem despejar payloads pessoais.

## Veredito

**Promoção bloqueada até resolver A1/A2 e refazer os gates no SHA candidato.** O CI tem boa separação lint → testes → build e usa actions por SHA, mas a revisão encontrou divergência material entre o artefato construído e o Dockerfile/ignores validados pelos testes. Não há evidência produzida nesta tarefa de build de imagem, digest, canário ou estado atual de nuvem.
