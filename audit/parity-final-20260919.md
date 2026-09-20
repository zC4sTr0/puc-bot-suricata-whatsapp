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
8. **Promoção produtiva** — executada com read-back.
   - O primeiro candidato foi descartado porque o contexto de build continha
     artefatos locais e não provava equivalência com o commit aprovado.
   - Foi criado um worktree limpo no commit `b3bc5c5` e um novo digest foi
     construído a partir dele; a comparação do source archive confirmou todos
     os arquivos runtime necessários, sem divergências de bytes.
   - O canário foi atualizado somente para esse digest, permaneceu com entrega
     desligada e terminou com `succeededCount=1`.
   - O Job produtivo foi atualizado somente na imagem; o read-back confirmou
     args, envs, timeout, retries, identidade e estado inalterados.
   - A execução produtiva controlada terminou com `succeededCount=1`; o digest
     novo e a geração produtiva foram confirmados depois da execução.
   - Scheduler, frequência, timezone, IAM, Secret Manager, sessão e estado GCS
     não foram alterados.

## Critérios de aceitação

- **Paridade de código local:** PASS para a matriz focal com mesma entrada.
- **Paridade do demo padrão:** NÃO é comparação válida de produção porque as
  fixtures públicas são diferentes; a comparação de mesma entrada PASSOU.
- **Paridade do lease:** corrigida para o comportamento da release.
- **Suíte completa:** PASS local, condicionada à repetição após este último
  ajuste e ao interpretador suportado pelo projeto.
- **Source-to-digest:** PASS operacional para o candidato final: o source archive
  do build limpo foi comparado contra o commit aprovado em todos os arquivos
  runtime necessários. O Cloud Build ainda não fornece attestation SLSA
  assinada, então a garantia é de comparação de conteúdo e não de provenance
  criptográfica do builder.
- **Imagem candidata:** PASS no build, Artifact Registry e read-back do digest.
- **Canário candidato:** PASS; configuração segura lida de volta e execução
  terminou com uma task concluída.
- **Produção sem quebra:** PASS para a invariância de configuração e para a
  execução produtiva controlada: read-back confirmou digest novo, args, entrega,
  identidade, estado, geração e Scheduler preservados. Isso não constitui prova
  matemática de todas as futuras interações externas, mas fecha os gates
  operacionais executados.

## Segurança do plano

O plano manteve entrega desligada até a aprovação do artefato limpo. A promoção
alterou somente a imagem do Job produtivo; preservou digest anterior para
rollback, canário separado, estado, sessão, Scheduler, IAM, Secret Manager,
timeout, retries e identidade. O read-back da execução produtiva terminou com
sucesso e os logs foram inspecionados de forma sanitizada.

## Veredito honesto

A arquitetura candidata foi validada contra a release nos cenários diferenciais
executados, a divergência de lease foi ajustada, o artefato final foi produzido
em worktree limpo e a promoção foi concluída com read-back. A garantia é forte
para o conteúdo versionado, configuração e execução observados; não é uma
promessa matemática sobre indisponibilidade futura do Canvas/WhatsApp ou sobre
interações que não foram observadas. O rollback permanece disponível pelo
digest anterior imutável.
