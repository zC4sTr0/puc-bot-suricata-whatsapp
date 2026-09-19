# Auditoria de segurança de deploy e isolamento Cloud — Suricata

**Escopo:** inspeção local somente leitura do checkout `C:\GIT\suricata-whatsapp`. Nenhum comando `gcloud`, Cloud Build, Cloud Run, Scheduler, IAM, GCS ou WhatsApp foi executado. Nenhum segredo foi lido. Não houve deploy, commit ou alteração de infraestrutura.

**Veredito:** **BLOQUEADO para declarar que um deploy do estado atual é seguro/isolado.** O repositório contém boas barreiras locais e documentação de namespace Suricata, mas há blockers de proveniência/configuração e de privilégio que não podem ser resolvidos por inspeção local: IAM least-privilege, digest realmente implantado, bindings de Secret Manager/GCS, scheduler atual, estado/prefixo efetivo e correspondência entre artefato e commit.

## Identidade da inspeção

- **Fato verificado localmente:** `HEAD=e20049f40d45e219648bd4985ea3729b36cc5482`, branch `docs/readme-rodada-agenda`, árvore sem mudanças reportadas por `git status --short --branch`.
- **Fato verificado localmente:** os caminhos pedidos como `docs/PLANO-*.md` existem neste clone sob `docs/historico/`; o status operacional está em `docs/interno/STATUS.md`.
- **Fato verificado localmente:** `git diff --check` passou.
- **Fato verificado localmente:** `gcloud` está instalado localmente; Docker não foi encontrado no `PATH`. A presença do binário não prova autenticação, projeto selecionado ou autorização, e não foi usado.
- **Não verificado:** qualquer estado atual da nuvem. Snapshots/documentos históricos não substituem read-back.

## Recursos que poderiam ser mutados

| Recurso | Mutação possível | Entradas/caminhos | Situação/evidência |
|---|---|---|---|
| Cloud Build / Artifact Registry | criar build remoto e publicar imagem/tag | `gcloud builds submit . --project=... --tag=...`; contexto raiz e `Dockerfile` | **Documentado, não executado/não verificado.** `docs/deploy-gcp.md:77-101`; o build é billable e exige gate explícito. |
| Cloud Run Job produtivo | trocar imagem/digest, args, env, timeout, retries, service account | `gcloud run jobs update`; alvo documentado `suricata-rodada` | **Potencialmente mutável.** O Dockerfile padrão usa `shadow`, mas o Job pode sobrescrever `--mode rodada` e variáveis. Não há read-back atual. |
| Cloud Run Job canário | trocar configuração e executar uma task | `suricata-canario-prod`; `gcloud run jobs update/execute` | **Potencialmente mutável.** Runbook exige estado separado, `SURICATA_ENTREGA=desligada`, sem JID/destino e `maxRetries=0`; estado real não verificado. |
| Cloud Scheduler | habilitar/desabilitar, trocar cron/alvo ou criar segundo scheduler | `gcloud scheduler jobs update/execute`; alvo `suricata-rodada-10min` | **Blocker de isolamento:** exatamente um scheduler não foi confirmado nesta sessão. Um segundo caminho pode duplicar rodadas/efeitos. |
| GCS estado Suricata | ler/escrever/remover objetos de memória, lease, outbox e sessão WhatsApp | `SURICATA_ESTADO_URI=gs://...`; JSON API em `suricata/storage/objetos_gcs.py`; CAS `ifGenerationMatch` | **Código verificado:** operações de gravação/remoção existem e são mutações externas. Bucket/prefixo efetivo e IAM não verificados. |
| Objeto de sessão WhatsApp | ler/gravar `whatsapp/auth.json` via CAS | `suricata/storage/cas.py`, `AUTH_OBJECT_URI` hardcoded | **Risco concreto:** `gs://suricata-college-20260913-estado/whatsapp/auth.json` está embutido no módulo legado de sessão. Não há prova local de que o Job usa o mesmo bucket desejado nem de que o objeto pertence exclusivamente à Suricata. |
| WhatsApp | enviar mensagens e atualizar sessão | somente quando `SURICATA_ENTREGA=ligada`; bridge Node recebe JID/eventos e pode escrever sessão | **Código verificado, ação não executada.** Sem ACK válido não marca `sent`; ainda assim a configuração de entrega/JID é um boundary externo que não foi revalidado. |
| Canvas | chamadas de coleta, aparentemente leitura | `SURICATA_CANVAS_TOKEN`; `suricata/integracao/canvas.py` | **Código/documentação indicam somente coleta pública/GET; endpoint/token ao vivo não verificados.** Token não foi lido. |
| IAM / Secret Manager | concessão/revogação de acesso e materialização de secrets | configuração do Job/service account, nomes de secrets | **Não verificado.** `suricata/infra/README.md` descreve intenção; não há manifesto IAM executável nem prova de least privilege. |

## Comandos e entradas sensíveis

### Com efeito externo (não executados)

- `gcloud builds submit .`: upload do contexto e build billable; risco de publicar artefato de checkout incorreto/dirty ou incluir arquivo inesperado.
- `gcloud run jobs update ...`: altera o Job; pode mudar digest, modo, env, retries, timeout e identidade.
- `gcloud run jobs execute ...`: inicia uma execução; pode ler/escrever estado e, se `SURICATA_ENTREGA=ligada`, enviar WhatsApp.
- `gcloud scheduler jobs update/run ...`: pode alterar ou disparar a cadência; risco de concorrência/duplicação.
- `gcloud storage ...`/API GCS: pode ler, criar, sobrescrever ou remover estado/sessão; o CAS reduz corrida, mas não restringe bucket errado.
- qualquer operação IAM/Secret Manager: amplia ou altera blast radius de credenciais.

### Inputs que governam o comportamento

- `SURICATA_ESTADO_URI`: seleciona backend local ou GCS. `suricata/storage/gcs.py` escolhe GCS por prefixo `gs://`; URI/namespace errado pode misturar produtos ou canário e produção.
- `SURICATA_ENTREGA`: somente o valor exato `ligada` habilita a ponte (`suricata/rodada/runtime.py:39-43`). Ausência/default é desligado, barreira positiva verificada no código.
- `SURICATA_GRUPO_JID` e `SURICATA_DESTINOS_JSON`: selecionam destinos; há validação de formato, ids e path traversal em `suricata/rodada/config.py`.
- `SURICATA_CANVAS_TOKEN`: pré-condição do modo `rodada`; nunca foi lido.
- `SURICATA_WA_AUTH_DIR`: documentado como externo, mas a ponte materializa a sessão em diretório temporário e o armazenamento usa o objeto CAS.
- `SURICATA_CONFIG`: arquivo externo com precedência parcial sobre destinos; se acessível ao processo, pode redirecionar destinos sem alteração de imagem.
- `SURICATA_GCLOUD_BIN`: permite escolher o executável de `gcloud` em caminhos de sessão legados; aumenta superfície local e deve ser fixado/permitido no runtime.

## Controles positivos verificados no checkout

- **Imagem:** bases Node estão pinadas por digest nos dois Dockerfiles; usuário não-root `uid=10001`; `PYTHONDONTWRITEBYTECODE=1`; sessão/segredos são excluídos por `.dockerignore` e `.gcloudignore`.
- **Modo padrão:** ambos Dockerfiles usam `CMD ["--mode", "shadow"]`; `docker-compose.yml` usa `demo`, sem volumes de sessão e sem rede/credenciais extras.
- **Entrega fail-closed:** `run_from_environment` não cria a ponte quando entrega está desligada; falta de estado/token retorna erro. `WhatsAppBridge` exige ACK/status para aceitar sucesso.
- **Persistência:** GCS usa geração anunciada e `ifGenerationMatch`; erros não incluem token/corpo. Outbox/lease/CAS têm testes locais.
- **Isolamento nominal:** `suricata/infra/isolamento.json` declara projeto/prefixo/bucket/Artifact Registry/service account Suricata e recursos proibidos. O teste de isolamento exclui deliberadamente o próprio manifesto e testes da varredura de strings proibidas; portanto isso prova o contrato do teste, não a nuvem.
- **CI:** `contents: read`, actions pinadas por SHA, entrega desligada nos testes, build local de CI e E2E `demo` dentro do container. O workflow não faz deploy.

## Riscos de cross-product e blockers

### Blocker 1 — IAM e secrets não provados

`docs/interno/STATUS.md` afirma explicitamente que IAM least-privilege continua não verificado. Não há evidência atual de que a service account só possa acessar o bucket/secrets Suricata, nem de que não possa acessar recursos `academico-*`, Telegram ou outro produto. Também não há read-back dos nomes/metadados dos secrets no estado atual.

**Impacto:** um Job com identidade compartilhada ou bindings amplos pode ler/mutar estado de outro produto mesmo que o código tenha nomes Suricata.

### Blocker 2 — Digest/origem do artefato não provados para este HEAD

O status documenta digests de snapshots anteriores e também diz que a main moderna ainda não foi necessariamente deployada. O checkout atual está em `e20049f...` e não foi associado localmente a digest por build/verificação. Docker não está disponível localmente; nenhum Cloud Build foi chamado.

**Impacto:** um deploy pode executar código diferente do auditado, inclusive uma imagem antiga com configuração/contrato diferente.

### Blocker 3 — Estado atual e scheduler não revalidados

`suricata/infra/isolamento.json` marca o snapshot como `historical_snapshot_not_revalidated_2026-09-16`; `docs/deploy-gcp.md` também exige read-back. Não foi possível afirmar localmente projeto, região, Job, Scheduler único, bucket, prefixo, env, args, timeout, retries ou service account atuais.

**Impacto:** alvo errado, segundo scheduler, canário apontando para produção ou estado compartilhado podem causar cross-product, duplicação ou mutação irreversível.

### Blocker 4 — Bucket de sessão hardcoded e contrato de estado dividido

`suricata/storage/objetos_gcs.py` usa URI configurável para estado geral, enquanto `suricata/storage/cas.py:15-16` fixa `BUCKET_URI` e `AUTH_OBJECT_URI` para sessão. Isso é uma configuração separada do `SURICATA_ESTADO_URI` e não há prova de que os dois apontem para o mesmo namespace autorizado.

**Impacto:** sessão WhatsApp pode ser gravada em bucket inesperado; canário e produção podem compartilhar a sessão; ou um Job com identidade que só possui acesso ao bucket configurado falhar/usar fallback diferente. O teste local não comprova a configuração cloud efetiva.

### Blocker 5 — Configuração de destino é mutável por ambiente

Mesmo com imagem imutável, `SURICATA_ENTREGA`, JID, destinos JSON e `SURICATA_CONFIG` mudam o comportamento. O runbook exige read-back e gate humano, mas o repositório não contém um mecanismo de autorização criptográfica/allowlist do destino. A validação de JID comprova forma, não identidade do grupo.

**Impacto:** uma atualização de env/secret pode enviar para outro grupo sem mudar o digest; sucesso do read-back de um JID ainda não prova que é o grupo autorizado.

### Riscos residuais adicionais

- `gcloud` é instalado na imagem raiz (`Dockerfile:5`) embora o caminho GCS moderno use HTTP/metadata; o módulo de sessão legado usa subprocesso e URI hardcoded. Isso amplia binários disponíveis e exige revisão de qual caminho está ativo.
- `apt-get` e `npm ci` não estão fixados por digest/versões completas em relação ao conteúdo baixado; a base é pinada, mas o Dockerfile admite variação de pacotes instalados. Isso reduz reprodutibilidade do artefato.
- `infra/isolamento.json` contém nomes/IDs de projeto, bucket e budget históricos. É manifesto informativo e explicitamente não revalidado; não deve ser usado como autorização nem como input automático de deploy.
- `docker-compose.yml` é seguro como estudo (`demo`), mas não prova o caminho `rodada`, GCS, IAM, sessão ou Cloud Run.

## Evidência não suficiente para promover

- Testes Python/Node, `compileall`, lint ou `demo` verde provam somente contratos locais.
- `Dockerfile` parseável ou build de CI sem publicação não prova digest implantado, IAM, env/secrets, scheduler ou estado.
- `Succeeded` de uma execução não prova entrega WhatsApp; o próprio runbook exige ACK/relatório.
- Documentos `STATUS.md`, `deploy-gcp.md` e `isolamento.json` registram snapshots; não são read-back atual.

## Ação segura possível (ainda não executada)

Antes de qualquer alteração externa, exigir um read-back somente leitura e sanitizado, a partir de uma identidade autorizada, de: projeto/região, lista de Jobs e Schedulers, descrição completa do Job Suricata (digest, args, env names, secrets names, timeout, retries, service account), bucket/prefixo, Artifact Registry/digest, bindings IAM e nomes de secrets. Comparar tudo com o commit auditado; depois construir imagem por commit limpo, inspecionar contexto/imagem, executar apenas canário isolado com entrega desligada e `maxRetries=0`, e ler de volta cada mudança. Não ligar entrega, não criar scheduler e não tocar IAM/segredos durante a auditoria.

**Conclusão:** o estado atual tem controles locais relevantes e intenção clara de isolamento, mas a resposta segura para “este estado pode alterar comportamento cloud sem risco cross-product?” é **sim, pode** — principalmente por configuração externa, recursos mutáveis por `gcloud`, ausência de prova IAM/segredos e falta de read-back atual. Portanto o deploy deve permanecer **BLOQUEADO** até os blockers acima serem verificados e reconciliados.
