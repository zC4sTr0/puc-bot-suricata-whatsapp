# Paridade com produção — plano executado e estado final

Data: 2026-09-19

## Objetivo

Comparar a arquitetura candidata com a release operacional associada ao Job
produtivo, corrigir divergências comprovadas sem alterar produção e separar
claramente as provas locais, do artefato e da nuvem.

## Plano e execução

1. **Congelar âncoras** — executado.
   - Candidato inicial: `4122d54`; release/oráculo: `8ca7a51`.
   - Produção foi lida somente por read-back.
2. **Capturar produção** — executado.
   - Job `suricata-rodada`, geração 27, digest operacional registrado no
     relatório `audit/workers/parity-production-snapshot.md`.
   - Scheduler, argumentos, retries, timeout e execução mais recente foram
     lidos sem mutação.
3. **Comparar comportamento** — executado.
   - Matriz focal comum: release 145 passed; candidato inicial 153 passed.
   - Com a mesma fixture sintética nos dois trees, `demo` terminou com stdout
     idêntico.
   - A divergência de IDs/URLs no demo padrão é deliberadamente de fixture
     pública: os dois trees consumiam dados diferentes. Não representa uma
     divergência do pipeline quando a entrada é a mesma e não altera Canvas
     real, sessão, estado ou entrega.
4. **Corrigir contrato real divergente** — executado.
   - A validação nova de `SURICATA_LEASE_MINUTOS` foi removida do runtime para
     restaurar exatamente o contrato da release: `int(env, default=6)`.
   - Foi mantido teste explícito de que TTL `0` continua aceito.
5. **Reconciliar histórico** — executado.
   - `origin/main` foi integrado na branch candidata.
   - Conflitos foram resolvidos preservando a documentação pública sanitizada e
     a arquitetura atual.
6. **Gates locais finais** — PASS.
   - `python3 -m pytest -q`: **357 passed, 1 skipped, 90 subtests**.
   - `python3 -m unittest discover -s suricata/tests -q`: **356 tests OK, 1 skipped**.
   - compileall, shadow, Node agregado (**39/39**) e npm ci/npm test (**39/39**) passaram.
   - Matriz focal comum: release **145 passed**; candidato final **147 passed**.
   - Com a mesma fixture sintética nos dois trees, `demo` terminou com stdout
     idêntico.
7. **Build e canário sem entrega** — PASS.
   - Cloud Build autorizado executou a partir da árvore limpa em `b3bc5c5` e
     publicou um digest imutável; o digest foi confirmado novamente no Artifact
     Registry.
   - O canário existente foi atualizado somente na imagem, mantendo estado
     separado, `--mode rodada`, entrega desligada, retries 0 e timeout 300 s.
   - Read-back pós-update confirmou a configuração segura; a execução do
     canário terminou com `succeededCount=1`.
   - Read-back independente confirmou produção sem alteração e Scheduler
     habilitado com a frequência/timezone existentes.
8. **Promoção produtiva** — NÃO executada.
   - O Job produtivo permaneceu no digest anterior e a entrega real não foi
     tocada.
   - A última execução produtiva observada antes do canário estava falha; isso
     continua exigindo diagnóstico separado antes de qualquer promoção.

## Critérios de aceitação

- **Paridade de código local:** PASS para a matriz focal com mesma entrada.
- **Paridade do demo padrão:** NÃO é comparação válida de produção porque as
  fixtures públicas são diferentes; a comparação de mesma entrada PASSOU.
- **Paridade do lease:** corrigida para o comportamento da release.
- **Suíte completa:** PASS local, condicionada à repetição após este último
  ajuste e ao interpretador suportado pelo projeto.
- **Source-to-digest:** UNKNOWN; o Cloud Build histórico expõe armazenamento
  de origem e tag, mas não prova sozinho o SHA Git byte a byte.
- **Imagem candidata:** PASS no build e no Artifact Registry; source-to-SHA
  Git ainda é parcialmente UNKNOWN porque o Cloud Build histórico não expõe
  commit no campo `source`.
- **Canário candidato:** PASS; configuração lida de volta e execução terminou
  com uma task concluída.
- **Produção sem quebra:** PASS para a invariância de configuração: read-back
  confirmou digest, args, entrega e geração produtiva inalterados. Isso não é
  prova de entrega WhatsApp nem substitui diagnóstico da execução produtiva
  falha.

## Segurança do plano

O plano não chama entrega real, não altera Scheduler, Job, IAM, Secret Manager,
sessão WhatsApp ou estado GCS. O próximo passo de promoção exige aprovação
de custo para Cloud Build e deve manter: digest anterior para rollback, canário
separado, entrega desligada, estado separado, ausência de destinos reais,
timeout/retries explícitos e read-back após cada mutação.

## Veredito honesto

A arquitetura candidata está localmente compatível com a release nos cenários
comuns verificados e a divergência de lease foi ajustada. Ainda não existe
prova responsável de que a imagem candidata é 100% igual à imagem em produção:
a produção está em um digest já publicado, o candidato não foi construído, e a
proveniência histórica não contém uma ligação criptográfica completa entre o
arquivo de origem do Cloud Build e o SHA Git. Não promover sem fechar esses
estados UNKNOWN.
