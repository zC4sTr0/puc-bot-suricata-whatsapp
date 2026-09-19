# Auditoria do snapshot e da proveniência da produção Suricata

Data da auditoria: 2026-09-19. Escopo somente leitura, exceto a criação deste relatório.

## Âncoras

- HEAD local: `4122d5466bc7f6cc17fa75a37038398c7b87153d` (`4122d54`), branch `deploy/same-behavior-hardening-20260919`.
- `origin/main`: `1fb5907077803e7657f0987801d1e6676cb2ef95` (`1fb5907`).
- Release documentada: `8ca7a51856054dd5d07a2bf97cd751a63d43b7cf` (`8ca7a51`).
- `git merge-base 4122d54 origin/main`: `e30b666364eb405f6d3d2f021ed4b0358755ae3f`.
- Divergência de refs: `4122d54` está 7 commits à frente e `origin/main` 1 commit à frente do ancestral comum (`git rev-list --left-right --count origin/main...4122d54` retornou `1 7`).
- A árvore estava limpa antes da criação deste arquivo; `git diff --check` não reportou erro.

## Comandos executados e outputs resumidos

### Git

```text
git status --short --branch
## deploy/same-behavior-hardening-20260919

git rev-parse HEAD
4122d5466bc7f6cc17fa75a37038398c7b87153d

git show --no-patch --format=fuller 8ca7a51
fix: harden session configuration and deploy gates

git show --no-patch --format=fuller 4122d54
chore(repo): alinhar documentação e fixtures públicas

git log --oneline 8ca7a51..4122d54
4122d54 chore(repo): alinhar documentação e fixtures públicas
d6ebc59 docs: prepare PUC Bot self-hosted launch
eebaf7b docs: record verified production promotion
```

`origin/main` é `1fb5907`; seu único commit após o ancestral comum é a atualização de UX do README. O HEAD local contém, além desse histórico, os três commits acima.

### GCP read-only

A primeira invocação do launcher Unix de `gcloud` falhou por conversão de caminho MSYS. O mesmo SDK foi executado com `cmd.exe`/`gcloud.cmd`; autenticação e consultas read-only funcionaram. Nenhum comando de update, execute, build ou scheduler mutating foi chamado.

```text
cmd.exe /c call "...\gcloud.cmd" auth list --format="table(account,status)"
ACCOUNT                   ACTIVE
<account-redacted>       *

cmd.exe /c call "...\gcloud.cmd" run jobs describe suricata-rodada \
  --project=suricata-college-20260913 --region=southamerica-east1 --format=yaml
```

Read-back efetivo do Job `suricata-rodada`, projeto `suricata-college-20260913`, região `southamerica-east1`:

```text
metadata.generation: 27
spec.template.spec.taskCount: 1
container.args: [--mode, rodada]
container.image: southamerica-east1-docker.pkg.dev/suricata-college-20260913/suricata/suricata@sha256:cd2de3518f28296a0d2ccfdbac3c96a18451da48bc9982a85531f3ff87e8db77
SURICATA_ESTADO_URI: gs://suricata-college-20260913-estado
SURICATA_ENTREGA: ligada
SURICATA_CANVAS_TOKEN: secretKeyRef, valor não lido
SURICATA_GRUPO_JID: <redacted>
SURICATA_DESTINOS_JSON: <redacted>
maxRetries: 1
timeoutSeconds: 240
serviceAccountName: <redacted>
resources: cpu=1, memory=512Mi
status.conditions[Ready]: True
latestCreatedExecution: suricata-rodada-j9gjk
latestCreatedExecution.completionStatus: EXECUTION_FAILED
```

O nome/valor dos destinos e JIDs foi redigido. O valor do secret nunca foi lido.

Scheduler read-back:

```text
cmd.exe /c call "...\gcloud.cmd" scheduler jobs describe suricata-rodada-10min \
  --project=suricata-college-20260913 --location=southamerica-east1 \
  --format="yaml(name,state,schedule,timeZone,httpTarget.uri,httpTarget.body)"
name: projects/suricata-college-20260913/locations/southamerica-east1/jobs/suricata-rodada-10min
state: ENABLED
schedule: */10 * * * *
timeZone: America/Sao_Paulo
httpTarget.uri: https://run.googleapis.com/v2/projects/suricata-college-20260913/locations/southamerica-east1/jobs/suricata-rodada:run
```

### Cloud Build read-only

```text
cmd.exe /c call "...\gcloud.cmd" builds describe 8d81e9ca-59e9-43d2-ae19-2a9598aa6a20 \
  --project=suricata-college-20260913 \
  --format="yaml(id,status,createTime,finishTime,source,images,results.images,substitutions)"
status: SUCCESS
images: .../suricata:8ca7a51
results.images[0].digest: sha256:cd2de3518f28296a0d2ccfdbac3c96a18451da48bc9982a85531f3ff87e8db77
source: storageSource (bucket Cloud Build e objeto de arquivo, sem campo explícito de commit)
```

## Determinação do snapshot produtivo

**Digest/configuração observados no Job no momento da auditoria:**

- imagem imutável: `sha256:cd2de3518f28296a0d2ccfdbac3c96a18451da48bc9982a85531f3ff87e8db77`;
- a imagem está tagueada no Cloud Build como `:8ca7a51`;
- geração do Job: `27`;
- `--mode rodada`, uma task, timeout de 240 s, `maxRetries=1`;
- estado em `gs://suricata-college-20260913-estado`;
- entrega ligada;
- secret Canvas referenciado por Secret Manager, valor não consultado;
- destinos/JIDs configurados, valores redigidos;
- Scheduler único observado como habilitado a cada 10 minutos, timezone `America/Sao_Paulo`;
- o último execution criado no read-back estava `EXECUTION_FAILED`; isso não foi tratado como evidência de sucesso de entrega.

A evidência GCP atual é consistente com o registro posterior de promoção em `eebaf7b`: esse registro associa `8ca7a51` ao build `8d81e9ca-...` e ao digest `cd2de351...`, e afirma Job na geração 27. O read-back atual confirma o digest e a geração.

## Divergência da release e commits posteriores

Há uma inconsistência importante de proveniência documental:

1. No próprio commit `8ca7a51`, `docs/interno/STATUS.md` registrava o build `c4236fa0-...` e o digest `sha256:564bff747f777678b0e4618a09b005f50c7ac7e99ec3440e6f3bbd416f6bcdf4`.
2. O commit posterior `eebaf7b` alterou somente esse registro documental: renomeou a candidata para `8ca7a51`, substituiu o build por `8d81e9ca-...` e o digest por `sha256:cd2de351...`, além de atualizar a geração do Job para 27.
3. O Job atualmente contém `cd2de351...`, não o digest `564bff747...` registrado na árvore original de `8ca7a51`.
4. O Cloud Build consultado confirma `status: SUCCESS`, tag `:8ca7a51` e o digest atual, mas seu `source` é um arquivo em Cloud Storage e não expõe um campo explícito de SHA Git. Portanto, a consulta prova a associação operacional tag/digest, mas não prova sozinha que o conteúdo do arquivo-fonte do build era byte a byte a árvore Git de `8ca7a51`.

Commits depois de `8ca7a51`, em ordem temporal:

- `eebaf7b` — alteração documental de proveniência/promoção; não alterou runtime.
- `d6ebc59` — reorganização e sanitização de documentação/fixtures, além de mudanças em configuração de runtime e testes.
- `4122d54` — saneamento adicional de documentação, fixtures e identificadores públicos; a mensagem declara nenhum runtime de produção alterado, mas o diff contém mudanças de código versionado e configuração.

`git diff --name-status 8ca7a51..4122d54` totalizou 60 arquivos, 1.197 inserções e 3.703 remoções. As mudanças pós-release que atingem runtime/configuração versionada incluem:

- `.env.example`, `suricata/entrypoint.py`, `suricata/ARCHITECTURE.md`, `suricata/README.md`;
- `suricata/rodada/coleta.py`: exclusões de cursos passaram a ser configuráveis, com default legado;
- `suricata/rodada/config.py`: validação de `SURICATA_CURSOS_EXCLUIDOS`;
- `suricata/storage/lease_rodada.py`: validação fail-closed de `SURICATA_LEASE_MINUTOS`;
- `suricata/infra/isolamento.json`: identificadores reais substituídos por placeholders e snapshot marcado como não verificado;
- fixtures e testes correspondentes.

Não há alteração posterior a `8ca7a51` em `suricata/Dockerfile`, `suricata/storage/cas.py` ou `suricata/storage/sessao.py` segundo o diff entre esses dois commits; esses arquivos pertencem à release. A imagem atualmente implantada é a imagem associada ao build/tag de `8ca7a51`, não há evidência no read-back de que tenha sido reconstruída a partir do HEAD `4122d54`.

## Limitações e pontos não provados

- Não foi possível provar pelo campo `source` do Cloud Build qual SHA Git foi empacotado; o build expõe arquivo de origem em Cloud Storage, não commit explícito.
- Não foi possível provar que o digest `cd2de351...` contém exatamente a árvore de `8ca7a51`, apesar de a tag do build ser `8ca7a51` e do registro documental afirmar essa associação.
- Não foi possível provar que o código pós-release de `d6ebc59`/`4122d54` está em produção; o digest atual corresponde ao build documentado como `8ca7a51`.
- Não foi auditado o conteúdo/valor do Secret Manager, sessão WhatsApp, payload dos destinos/JIDs, logs de entrega, ACKs, IAM efetivo, permissões do bucket ou conteúdo do estado GCS.
- A última execução criada (`suricata-rodada-j9gjk`) falhou; esta auditoria não determina a causa nem usa essa execução para inferir entrega.
- O relatório não valida que o Scheduler tenha efetivamente concluído uma invocação com sucesso, apenas que o recurso está `ENABLED` e aponta para o Job correto.

## Conclusão

O snapshot operacional observável é inequívoco: Job `suricata-rodada`, geração 27, digest `sha256:cd2de3518f28296a0d2ccfdbac3c96a18451da48bc9982a85531f3ff87e8db77`, modo `rodada`, entrega ligada, uma task, timeout 240 s, uma tentativa de retry e estado no bucket Suricata. Ele não corresponde ao digest `sha256:564bff...` registrado no commit original `8ca7a51`; corresponde ao registro posterior `eebaf7b` e ao Cloud Build tagueado `8ca7a51`. A proveniência exata do conteúdo do arquivo-fonte do build continua parcialmente não provada, e o HEAD `4122d54` não pode ser declarado como o código implantado.
