# Auditoria diferencial de comportamento: prod vs candidato

**Escopo**

- Release produtiva/oráculo: `8ca7a51` (`8ca7a51856054dd5d07a2bf97cd751a63d43b7cf`).
- Candidato: `HEAD` `4122d54` (`4122d5466bc7f6cc17fa75a37038398c7b87153d`).
- Repositório auditado: `C:/GIT/suricata-whatsapp`.
- Execução: 2026-09-19, Windows/MSYS, Python 3.10.11, Node 22.11.0.
- Somente leitura nos commits; cópias temporárias usadas em `C:/Users/C4sTr/orca/parity-audit-20260919/{oracle2,candidate2}`. Este relatório é o artefato solicitado; outro arquivo untracked (`audit/workers/parity-production-snapshot.md`) apareceu durante a auditoria e foi preservado sem alteração.

## Comandos executados

Snapshot:

```sh
cd /c/GIT/suricata-whatsapp
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
git status --short --branch
git rev-parse HEAD
git rev-parse 8ca7a51
git diff --name-status 8ca7a51..4122d54
```

As cópias foram materializadas sem checkout mutável do repositório canônico:

```sh
git archive 8ca7a51 | tar -x -C C:/Users/C4sTr/orca/parity-audit-20260919/oracle2
cp -a . C:/Users/C4sTr/orca/parity-audit-20260919/candidate2
```

Matriz Python focal, igual nos dois lados:

```sh
python -m pytest -q \
  suricata/tests/test_entrypoint.py \
  suricata/tests/test_caminho_real_e2e.py \
  suricata/tests/test_rodada.py \
  suricata/tests/test_corte_21h.py \
  suricata/tests/test_corte_21h_adversarial.py \
  suricata/tests/test_corte_21h_current_event.py \
  suricata/tests/test_operacao_fail_closed.py \
  suricata/tests/test_lease_rodada.py \
  suricata/tests/test_storage.py \
  suricata/tests/test_storage_adversarial_worker.py \
  suricata/tests/test_storage_cas_revalidation.py \
  suricata/tests/test_storage_robustez.py \
  suricata/tests/test_storage_compatibility.py \
  suricata/tests/test_message_id.py \
  suricata/tests/test_bridge.py \
  suricata/tests/test_bridge_integration.py \
  suricata/tests/test_bridge_node_e2e.py \
  suricata/tests/test_outbox.py \
  suricata/tests/test_memoria_compatibility.py \
  suricata/tests/test_lotes_compatibility.py
```

Matriz de CLI, em cada cópia:

```sh
python -m suricata --help
python -m suricata --mode shadow
python -m suricata --mode demo
python -m suricata --mode nope
python -m suricata
SURICATA_LEASE_MINUTOS=0 python -c 'import suricata.storage.lease_rodada'
SURICATA_LEASE_MINUTOS=nao-numero python -c 'import suricata.storage.lease_rodada'
```

Matriz Node:

```sh
node --test suricata/tests/*.mjs
(cd suricata/whatsapp && npm test)
```

## Resultados observados

| Área | Oráculo `8ca7a51` | Candidato `4122d54` | Classificação |
|---|---:|---:|---|
| Coleta Python | 350 testes coletados | 358 testes coletados | Divergência estrutural: +8 casos no candidato |
| Python focal: planejamento, coleta, parcial/erro, 07/12/18/21, lease, estado, outbox/CAS, IDs, entrega desligada, duplicação | 145 passed; 24 subtests; rc 0; 11,74 s | 153 passed; 27 subtests; rc 0; 14,58 s | PASS na matriz comum; candidato inclui 8 casos adicionais |
| Suíte Python completa | 350 passed; 90 subtests; rc 0; 227,58 s | Não concluída: execução excedeu 300 s, rc observado pelo timeout 124 | NOT VERIFIED; o verbose parou em `test_outbox_concurrency.py::...quarenta_processos...` |
| CLI `--help` | rc 0 | rc 0 | PASS no rc; texto só diverge no caminho documental (`docs/CONFIGURATION.md` vs `docs/configuracao.md`) |
| CLI `--mode shadow` | rc 0, JSON `{"mode":"shadow","status":"ok","adapter":"none"}` | mesmo rc e JSON | PASS |
| CLI inválida/ausente | rc 2 em ambos; JSON de erro sanitizado | rc 2 em ambos; mesmo JSON | PASS |
| CLI `--mode demo` | rc 0 | rc 0 | DIVERGENTE; primeira divergência observável da sequência CLI |
| Import do lease com `SURICATA_LEASE_MINUTOS=0` | rc 0 | rc 1, `ValueError: ... inteiro positivo` | DIVERGENTE real |
| Import do lease com `SURICATA_LEASE_MINUTOS=nao-numero` | rc 1 | rc 1 | Mesmo rc, mensagem/validação diferem |
| Node agregado | rc 1 | não completado após timeout da suíte Python | BLOQUEADO para paridade completa |
| Node isolado/`npm test` | rc 1 em ambos | resultado equivalente não-materializável | BLOQUEADO: dependência ausente `@whiskeysockets/baileys` nas cópias temporárias |

## Primeira fronteira divergente

A sequência CLI (`--help`, `shadow`, erro inválido, erro ausente) permanece igual. A primeira divergência observável ocorre em `python -m suricata --mode demo`:

- release imprime IDs sintéticos legados `grupo:novo:292184:{901,902,903}`;
- candidato imprime IDs sintéticos novos `grupo:novo:100001:{901,902,903}`;
- release imprime URLs `https://pucminas.instructure.com/courses/292184/assignments/{901,902,903}`;
- candidato não imprime essas URLs no texto demo, porque a fixture candidata usa `https://canvas.example.test/...` e o renderizador não os inclui no texto público;
- o JSON do relatório acompanha a mudança de `event_id` e de `texto`.

Isso não é apenas diferença de documentação: é stdout e JSON diferentes com a mesma invocação e relógio fixo. A causa está na fixture/doubles alterados em `suricata/tests/fixtures/canvas_demo.json` e `suricata/tests/_fakes.py`, com IDs/URLs sintéticos diferentes; há também mudança de comportamento efetivo no filtro de URL/texto para o domínio sintético.

A segunda divergência comportamental independente é a validação de configuração do lease: o release aceita `SURICATA_LEASE_MINUTOS=0` no import porque materializa `LEASE_MINUTOS=0`; o candidato falha fechado durante o import. Para valor não numérico, ambos retornam rc 1, mas o caminho candidato produz a mensagem explícita `SURICATA_LEASE_MINUTOS deve ser inteiro positivo`.

A terceira mudança de política observável é nova configuração de coleta: `cursos_excluidos_do_ambiente()` e `SURICATA_CURSOS_EXCLUIDOS` existem apenas no candidato. O teste `test_config_cursos_excluidos.py` é candidato-only; portanto não é uma linha comum de paridade. O default preserva `104959`, mas lista explícita, lista vazia e duplicatas agora são validadas/rejeitadas.

## Fronteiras solicitadas

- **CLI:** executada; `help`, `shadow`, erro e ausência passaram iguais. `demo` divergiu em IDs/URLs/texto/JSON.
- **Planejamento:** executado na matriz focal; 145/153 testes passaram.
- **Coleta:** executada na matriz focal, incluindo coleta parcial e erro; passou na matriz comum.
- **Estado/memória/outbox:** executados na matriz focal; passou na matriz comum.
- **Lease:** executado; divergência real para TTL zero e validação adicional para TTL não numérico.
- **CAS:** `test_storage_cas_revalidation.py`, storage adversarial e robustez executados; passaram na matriz comum.
- **Entrega desligada:** `test_operacao_fail_closed.py`, caminho real offline e demo executados; matriz comum passou; demo divergiu no conteúdo impresso.
- **IDs sintéticos:** divergência confirmada no primeiro comando `demo` (292184 → 100001).
- **Fronteiras 07/12/18/21:** testes de corte e eventos atuais executados; passaram na matriz comum. A suíte focal não substitui a suíte completa.
- **Parcial/erro:** `test_operacao_fail_closed.py`, `test_storage_robustez.py`, integração bridge e caminho real executados; passaram na matriz comum.
- **Duplicação/idempotência:** `test_outbox.py`, `test_memoria_compatibility.py`, `test_bridge_integration.py` e IDs executados; passaram na matriz comum. A parte pesada de concorrência da suíte completa ficou sem verificação do candidato por timeout.
- **Arquivos produzidos:** o modo demo usa estado temporário e não deixou arquivo de produção; não houve arquivo comparável persistente fora dos artefatos temporários. O relatório JSON foi comparado via stdout; sua diferença consta acima.

## Limitações e veredito

1. Não há veredito de equivalência total: a suíte Python completa do candidato não terminou dentro de 300 s; a primeira operação pesada observada foi o teste de 40 processos de `test_outbox_concurrency.py`.
2. A matriz Node não foi executável de forma válida nas cópias porque `@whiskeysockets/baileys` não está instalado; os dois lados falharam no mesmo primeiro import, portanto isso é bloqueio de ambiente, não evidência de paridade funcional Node.
3. Veredito conservador: **DIVERGENTE / NÃO VERIFICADO**. A matriz focal comum passou, mas existem divergências reais no demo (stdout/JSON/IDs/URLs) e na validação de lease, além da cobertura de concorrência completa ainda não fechada.
