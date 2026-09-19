# Verificação empírica local da prontidão de deploy

- Data/hora local: 2026-09-19 09:53:21 -0300
- Escopo: somente leitura operacional; nenhum deploy, cloud, pareamento, envio ou alteração de Git remoto.
- Repositório: `C:/GIT/suricata-whatsapp`

## Resultado executivo

**Prontidão local de deploy: UNKNOWN / bloqueada para declaração de pronta.**

Os gates de código passaram, mas a verificação não prova um build/deploy reproduzível porque:

1. Docker não está instalado/disponível (`docker: command not found`), portanto o build e o E2E da imagem definidos no CI não foram executados.
2. O ambiente local usa Python 3.10.11, enquanto `pyproject.toml` exige `>=3.11` e o CI usa Python 3.12. Os testes passaram em 3.10, mas essa execução não é representativa do runtime suportado; o gate de compatibilidade de ambiente é **UNKNOWN**.
3. Não houve consulta nem validação de recursos cloud, conforme escopo.

## Identidade e estado Git — PASS

Comandos executados:

```bash
git status --short --branch
git rev-parse HEAD
git branch --show-current
git rev-parse --show-toplevel
git diff --check
git ls-files | wc -l
git ls-files | grep -E '(^|/)__pycache__/|\.pyc$'
git ls-files | grep -E '(^|/)node_modules/'
git ls-files | grep -Ei '(^|/)(auth\.json|\.wa-auth|.*\.pem|.*\.key|.*\.db|.*\.sqlite)'
```

Resultados reais:

- Branch: `docs/readme-rodada-agenda`, alinhada a `origin/docs/readme-rodada-agenda`.
- HEAD: `e20049f40d45e219648bd4985ea3729b36cc5482`.
- Árvore estava limpa antes do relatório.
- `git diff --check`: rc 0.
- 155 arquivos rastreados.
- Arquivos rastreados com `__pycache__`/`.pyc`: 0.
- Arquivos rastreados em `node_modules`: 0.
- Arquivos rastreados com padrões de segredo/sessão consultados: 0.
- Ao final, o único item não rastreado esperado é este artefato `audit/`.

## Ferramentas locais — PASS/UNKNOWN

```text
Python 3.10.11                         disponível, mas fora do requisito >=3.11 (UNKNOWN)
pytest 9.1.1                           disponível (CI fixa 8.3.5)
ruff 0.16.8                            disponível via `python -m ruff`
Node v22.11.0                          disponível (CI usa Node 22)
npm 10.9.0                             disponível
Docker                                 indisponível (`docker: command not found`)
```

## Dependências Node — PASS

Comando exato:

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts --no-audit --no-fund
```

Resultado: rc 0. Duração aproximada: 1 s. O `package-lock.json` está rastreado e não houve alteração de conteúdo reportada.

## Gates obrigatórios do `AGENTS.md`

### `compileall` — PASS (com ressalva de versão)

```bash
python -m compileall -q suricata
```

Resultado: rc 0. Duração aproximada: 0 s. Executado também no clone limpo, rc 0. Ressalva: interpretador local é Python 3.10.11, abaixo do `requires-python = ">=3.11"`.

### `pytest` — PASS (com ressalva de versão)

```bash
python -m pytest -q
```

Resultado real: `333 passed, 80 subtests passed in 83.21s (0:01:23)`. rc 0; duração aproximada: 84 s. Ressalva: executado em Python 3.10.11; CI fixa pytest 8.3.5/Python 3.12.

### `unittest` — PASS (com ressalva de versão)

```bash
python -m unittest discover -s suricata/tests
```

Resultado real: `Ran 331 tests in 83.160s` / `OK`. rc 0; duração aproximada: 83 s. Ressalva: executado em Python 3.10.11.

### Testes Node — PASS

```bash
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Resultado real: `1..39`, `# tests 39`, `# pass 39`, `# fail 0`. rc 0; duração aproximada: 1 s. Houve apenas `ExperimentalWarning` de importação JSON do Node.

### Shadow — PASS

```bash
python -m suricata --mode shadow
```

Resultado real: `{"mode":"shadow","status":"ok","adapter":"none"}`. rc 0; duração aproximada: 0 s. Não houve entrega nem acesso cloud.

## Lint do CI — PASS via módulo

O workflow executa `ruff check .`. O binário `ruff` não está no PATH do shell (`ruff: command not found`, rc 127), mas o módulo instalado foi validado com o equivalente funcional:

```bash
python -m ruff check .
```

Resultado: `All checks passed!`, rc 0; duração aproximada: 0 s.

Classificação do comando literal do CI: **FAIL de disponibilidade do executável no PATH**. Classificação do lint efetivamente executado: **PASS**. Em CI o workflow instala `ruff==0.16.8`, portanto o ambiente local não reproduz exatamente o passo de instalação.

## Rastreabilidade Docker/CI — PASS estrutural / UNKNOWN execução

Arquivos relevantes rastreados:

```text
.github/workflows/suricata.yml
Dockerfile
docker-compose.yml
suricata/Dockerfile
suricata/whatsapp/package.json
suricata/whatsapp/package-lock.json
.dockerignore
suricata/.dockerignore
pyproject.toml
ruff.toml
```

Checagens estruturais:

- `Dockerfile` raiz copia `suricata/whatsapp/package.json`, `package-lock.json` e `suricata`; todas as fontes existem.
- `suricata/Dockerfile` copia `whatsapp/package.json`, `package-lock.json` e o contexto `.`; todas as fontes existem no contexto `suricata`.
- `docker-compose.yml` constrói a raiz e usa `--mode demo`, sem volume de sessão/credencial.
- `.dockerignore` e `suricata/.dockerignore` excluem `.wa-auth`, `auth.json`, sessões, logs, bancos, chaves, QR e `node_modules`.
- CI instala Node 22, executa npm ci, os quatro gates Python/Node/shadow e depois `docker build --pull` seguido de `docker run ... --mode demo`.

Execução do build/teste de imagem:

```bash
docker --version
docker build --pull --tag suricata-ci:<sha> .
docker run --rm suricata-ci:<sha> --mode demo
```

Classificação: **UNKNOWN** para build/E2E de imagem; não foi possível executar porque Docker não está disponível. Nenhum comando Docker foi tentado além da verificação de disponibilidade.

## Clone limpo — PASS

Comando efetivamente usado, com destino temporário fora da árvore:

```bash
git clone --no-local --branch docs/readme-rodada-agenda C:/GIT/suricata-whatsapp <temp>
```

Resultado: rc 0, duração aproximada: 1 s; HEAD do clone `e20049f40d45e219648bd4985ea3729b36cc5482`, 155 arquivos rastreados, `git status --porcelain` vazio e `python -m compileall -q suricata` rc 0. O diretório temporário foi removido e confirmado ausente (`temp_removed=yes`). A árvore original não foi destruída nem resetada.

Este foi um teste de clonabilidade e compilação limpa; a matriz completa de testes no clone não foi repetida para evitar duplicar os gates pesados, e permanece dependente de Python suportado e Docker para a prova completa.

## Falhas, ressalvas e próximos gates

- **FAIL/UNKNOWN:** Docker ausente bloqueia a prova local da imagem exatamente como o CI a constrói e executa.
- **UNKNOWN:** Python 3.10 passa os testes, mas não atende o requisito declarado `>=3.11`; repetir em Python 3.12 (mesma versão do CI) antes de declarar prontidão.
- **FAIL literal de ambiente:** `ruff check .` não foi encontrado no PATH; `python -m ruff check .` passou. O CI instala o binário explicitamente.
- **PASS:** testes Python, testes Node, compileall, shadow, lint via módulo, `git diff --check`, estado Git limpo inicial e clone limpo.
- **Não verificado por escopo:** cloud, Artifact Registry, Cloud Run Job, Scheduler, bucket, digest publicado, canário e deploy real.

Nenhuma alteração de código, configuração, Git ou cloud foi feita por este worker. Este worker criou apenas `audit/workers/empirical-gates.md`; os demais arquivos já existentes em `audit/workers/` não foram tocados.
