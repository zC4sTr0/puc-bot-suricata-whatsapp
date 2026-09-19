# Auditoria de paridade: empacotamento, CI e promoção

**Escopo:** somente leitura sobre cloud; sem Docker, Cloud Build, `gcloud`, deploy ou leitura de secrets.
**Base:** `8ca7a51` (release prod documentada), `HEAD=4122d54`, `origin/main=1fb5907`.
**Branch local:** `deploy/same-behavior-hardening-20260919`.

## Veredito

**NÃO PROMOVER `HEAD` diretamente.** O empacotamento Python/Node e os contratos locais estão coerentes e o wheel foi construído/instalado com Python 3.11, mas o caminho de promoção ainda não está comprovado: a suíte completa local não concluiu dentro do limite, o build Docker não foi executado por escopo, a origem remota diverge de `HEAD`, e não há verificação de source archive.

A recomendação segura é promover apenas após integrar/reconciliar a branch com a linha que será publicada, obter CI verde no checkout final e executar os gates remotos documentados somente com autorização explícita. Não mutar cloud nesta auditoria.

## Matriz de evidências

| Área | Status | Evidência executada / inspeccionada | Observação |
|---|---|---|---|
| Baseline release → HEAD | PASS | `git rev-list --left-right --count 8ca7a51...HEAD` = `0 3`; `git diff --check 8ca7a51..HEAD` = rc 0 | HEAD contém três commits após o release documentado; não houve alteração relevante em `Dockerfile`, `pyproject.toml`, workflow ou lockfile nesse intervalo. |
| HEAD ↔ origin/main | FAIL | `git rev-list --left-right --count HEAD...origin/main` = `7 1`; merge-base = `e30b666` | Histórico divergente: HEAD tem sete commits que `origin/main` não tem e remoto tem um commit que HEAD não tem. Não é uma linhagem segura para promoção sem reconciliação/CI no commit final. |
| Manifesto Python | PASS | `pyproject.toml:1-37`; `python` do shell é 3.10, mas `py -3.11`/uv Python 3.11.15 disponível | `requires-python >=3.11`, setuptools discovery `suricata.*`, entry point `suricata`, package-data para transporte Node e fixtures. |
| Wheel | PASS | `python -m pytest -q suricata/tests/test_wheel.py` → `3 passed in 29.06s`; wheel manual com Python 3.11 → rc 0, 214067 bytes | Wheel contém `entrypoint.py`, `package.json`, `package-lock.json`, fixture JSON e metadata. O teste também valida execução shadow fora do checkout. |
| Source archive | UNKNOWN | `python -m build` não disponível no Python padrão 3.10; `pip wheel` funcionou com Python 3.11; `pip download --no-binary` não deixou `.tar.gz` verificável | O CI instala `build`, mas o workflow não publica nem inspeciona um sdist explicitamente. Validar sdist no CI antes de tratá-lo como artefato suportado. |
| Lockfile Node | PASS | `suricata/whatsapp/package-lock.json` rastreado; `npm ci --prefix suricata/whatsapp --ignore-scripts --no-audit --no-fund` → rc 0 | `package.json:13-17` fixa dependências diretas; Docker e CI usam `npm ci`. |
| Testes Node | PASS | `node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs` → 39/39 pass; pacote → 7/7 pass | Avisos de experimental JSON não causaram falha. |
| Compile/shadow | PASS | `python -m compileall -q suricata` → rc 0; `python -m suricata --mode shadow` → `{"mode":"shadow","status":"ok","adapter":"none"}` | Caminho offline mínimo comprovado. |
| Ruff local | UNKNOWN | `ruff check .` não executável no ambiente local: `command not found` | Workflow instala `ruff==0.16.8` em runner Ubuntu; precisa de CI real para fechar. O teste unitário de lint isolado passou, mas isso não substitui o binário do job. |
| Pytest completo | FAIL/UNKNOWN | `358 tests collected`; execução completa excedeu 300 s. Execução por arquivo identificou timeout em `test_outbox_concurrency.py` e `test_simulacao_futura.py` com teto de 35 s; demais arquivos individuais concluíram, incluindo wheel | Não declarar suíte verde. Investigar os dois timeouts em ambiente Linux/CI, pois o workflow roda ambos pytest e unittest. |
| Unittest completo | UNKNOWN | `python -m unittest discover -s suricata/tests` excedeu 180 s com saída contínua | A execução isolada por arquivo não substitui o comando literal do CI. |
| Dockerfile raiz | PASS estrutural / UNKNOWN execução | `Dockerfile:3-14`; testes de layout passaram (`test_container_layout.py`, `test_root_container_layout.py`) | Base Node digest-pinned, lockfile copiado antes de `npm ci`, contexto copia `suricata`, usuário não-root, shadow default. Build/run reais não executados por escopo. |
| Dockerfile compatibilidade | PASS estrutural | `suricata/Dockerfile:1-37`; `test_container_layout.py` → 10 pass | Contexto `suricata/` tem COPY relativo correto. O arquivo informa que produção/CI usam o Dockerfile raiz; isso evita promover a imagem standalone por engano. |
| Exclusão de estado/secrets | PASS estático | `.dockerignore:1-23`, `.gcloudignore:1-22`; testes de layout | Exclui `.env`, auth, sessão, QR, logs, bancos e `node_modules`. Não é inspeção de conteúdo de cloud. |
| Workflow CI | PASS estrutural / UNKNOWN verde | `.github/workflows/suricata.yml:18-58` | Actions pinadas por SHA; lint → tests → Docker build/run. O build da imagem e o gate remoto não foram executados localmente. |
| Runbook de promoção | PASS como guardrail documental | `docs/deploy-gcp.md:118-213` | Documenta commit/árvore limpa, build por tag seguido de digest, canário sem entrega, read-back, corte separado e rollback por digest. Não prova estado real da cloud. |
| Não mutação cloud | PASS | Nenhum comando `gcloud`, `docker`, Cloud Build, update/execute de Job ou Scheduler executado | Auditoria limitada ao checkout e artefatos locais. |

## Divergências relevantes

1. **Histórico de promoção divergente:** `HEAD` é descendente de `8ca7a51`, mas não é descendente de `origin/main`; há sete commits locais ausentes do remoto e um commit remoto ausente localmente. A promoção deve partir do commit final reconciliado, não de uma comparação nominal de branches.
2. **Runbook mudou de inventário real para procedimento sanitizado:** em `8ca7a51`, `docs/deploy-gcp.md` continha snapshot operacional; em `HEAD`, o documento remove nomes/identificadores e exige placeholders + read-back (`docs/deploy-gcp.md:1-10`, `96-116`). Isso é mais seguro para publicação, mas elimina do clone público a prova de estado real; a evidência privada precisa existir fora do Git.
3. **Dockerfile canônico é o da raiz:** CI executa `docker build ... .` (`.github/workflows/suricata.yml:54-58`) e o runbook usa `gcloud builds submit .` (`docs/deploy-gcp.md:134-148`). `suricata/Dockerfile` é compatibilidade para contexto alternativo, não deve ser usado como caminho de produção sem uma decisão explícita.
4. **CI promete mais do que foi possível fechar localmente:** o workflow chama `pytest`, `unittest`, compile, Node e shadow; pytest/unittest completos não concluíram localmente. O job `build` depende de `tests`, logo não existe evidência suficiente para promoção.
5. **Empacotamento Python é melhor coberto que source distribution:** o wheel tem guard dedicado e passou; não há um guard equivalente para `.tar.gz`, nem artifact/upload de distribuição no workflow.
6. **Ambiente local mascarou requisito de versão:** o `python` padrão é 3.10.11 e corretamente não pode construir este pacote (`requires-python >=3.11`); Python 3.11.15 conseguiu construir. O CI usa 3.12, portanto o resultado local deve ser interpretado por interpretador, não pelo alias `python`.

## Compatibilidade observada

- O contrato do `pyproject.toml` inclui os subpacotes e dados necessários para a execução instalada.
- O lockfile Node está versionado e é aceito tanto pelo `npm ci` local quanto pelos comandos do Docker/CI.
- O wheel contém o transporte Node e fixtures, evitando depender do checkout para o modo shadow/demo.
- Os dois Dockerfiles usam a mesma base digest-pinned e o mesmo entrypoint shadow; diferem somente pelo contexto e pelo conjunto de pacotes apt.
- `.dockerignore` e `.gcloudignore` mantêm a fronteira de sessão/credencial/estado, confirmada pelos testes de layout.

## Gaps antes da promoção

- **P0 — resolver/reproduzir os timeouts:** `suricata/tests/test_outbox_concurrency.py` e `suricata/tests/test_simulacao_futura.py` não concluíram com limite de 35 s isoladamente; o comando completo também excedeu 300 s. Rodar no runner Python 3.12 do CI, identificar se é dependência de Windows/clock/concurrency e só então aceitar verde.
- **P1 — reconciliar branch:** decidir qual commit será publicado, integrar `origin/main` e os três commits pós-release conforme a política do repositório, e rodar CI no resultado. Não usar `HEAD` divergente como prova de paridade com a main.
- **P1 — fechar artefato sdist:** adicionar verificação explícita de `python -m build --sdist`/inspeção do `.tar.gz` (ou declarar formalmente que somente wheel é suportado). O estado atual é UNKNOWN.
- **P1 — executar gates de imagem em CI:** Docker build e `docker run --mode demo` continuam UNKNOWN nesta auditoria por escopo; o job existente é o gate apropriado e não deve ser substituído por testes estáticos.
- **P2 — manter uma única instrução canônica:** preservar o Dockerfile raiz para Cloud Build/CI e rotular o `suricata/Dockerfile` como compatibilidade, evitando que operadores interpretem os dois contextos como imagens equivalentes de produção.

## Caminho seguro recomendado

1. Preservar a arquitetura atual: wheel Python + dependências Node lockadas, imagem raiz digest-pinned, runtime shadow por padrão, canário sem entrega e promoção por digest.
2. Reconciliar `HEAD` com a base remota que será publicada; não fazer reset/force-push nem mutação cloud durante a reconciliação.
3. No checkout final limpo, executar os comandos literais do workflow: lint com `ruff==0.16.8`, `npm ci`, pytest completo, unittest completo, compileall, Node, shadow e, no runner Linux, Docker build/run.
4. Validar wheel e source archive no mesmo Python suportado pelo CI; inspecionar os conteúdos sem instalar credenciais ou dados de sessão.
5. Somente com CI verde, digest candidato conhecido, canário aprovado e autorização separada, seguir `docs/deploy-gcp.md:168-183`; fazer read-back após cada alteração e manter digest anterior para rollback.

## Estado final da auditoria

- Arquivo criado: `audit/workers/parity-build-and-promotion.md`.
- Nenhum arquivo versionado foi editado e nenhum commit foi criado.
- Relatórios não rastreados já existentes `audit/workers/parity-behavior-diff.md` e `audit/workers/parity-production-snapshot.md` foram preservados.
- Não foram executados Docker, Cloud Build, `gcloud`, deploy, update/execute de Job/Scheduler ou qualquer operação cloud.
