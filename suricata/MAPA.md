# Mapa humano da árvore Suricata

> **Escopo e proveniência:** fotografia histórica da árvore lida em 2026-09-17. Este mapa descreve o código e os documentos da revisão daquela data; não é prova do estado atual da nuvem nem substitui o branch/commit atual. Caminhos deste arquivo foram conferidos no disco, excluindo `__pycache__/` e `node_modules/`. Onde a relação de chamada é inferida por imports, `main()` ou testes, isso está marcado como **hipótese estática**.

## 1. Leitura em uma frase

O caminho funcional de produção é `python -m suricata --mode rodada`: Python consulta somente dados públicos do Canvas, normaliza e coleta atividades, decide avisos, persiste memória/outbox/relatório via objetos locais ou GCS com CAS, revalida o corte de 21h e, somente com entrega ligada, chama a ponte Python que executa `whatsapp/enviar.mjs`; o Node abre uma sessão Baileys, envia e só retorna sucesso quando há ACK compatível. O modo `shadow` é apenas um probe local sem adapter; `sentinela` é sombra funcional; `grupos` e `teste-envio` são utilitários de compatibilidade/operacionais.

## 2. Árvore relevante

```text
suricata/
├── __main__.py                 entrada `python -m suricata`
├── entrypoint.py               roteador CLI e validação de configuração
├── Dockerfile                  imagem Python + dependências Node/lockfile
├── config.example.json         exemplo público do modo sentinela
├── adapter.py                  fronteira pública Canvas/adapter
├── canvas.py                   cliente HTTP Canvas e normalização de respostas
├── coleta.py                   coleta de produção por cursos/assignments/anúncios
├── sentinela.py                coleta/projeção/decisão em sombra
├── planejamento.py             planejador puro da rodada, chamado pela fachada
├── application.py              caso de uso da sombra com writers injetáveis
├── domain.py                   entidade e política pública de eventos
├── publico.py                  horários, tipos, elegibilidade e textos
├── grupo.py                    política/textos da audiência pública
├── agenda_manual.py            complementos anotados manualmente
├── configuracao.py             destinos e janela BRT por ambiente
├── rodada.py                   composição canônica e fachada histórica
├── execucao.py                 outbox, corte, entrega e destinos
├── outbox.py                   máquina de estados durável
├── persistencia_rodada.py      outbox temporário publicado por CAS
├── lease_rodada.py             lease ativo `locks/rodada.lock`
├── lease.py                    lease legado, contrato separado
├── estado.py                   memória/heartbeat/JSONL local
├── delivery.py                 orquestrador de entrega compatível
├── bridge.py                   Python → subprocesso Node
├── message_id.py               identidade determinística de mensagem
├── notifiers/whatsapp.py       notificador público de compatibilidade
├── storage/cas.py              CAS legado de `whatsapp/auth.json` via gcloud
├── storage/gcs.py              objetos GCS/locais e CAS ativo
├── grupos.py                   inventário de grupos via sessão temporária
├── teste_envio.py              teste externo de idempotência (não é pré-voo)
├── whatsapp/
│   ├── auth-dir.mjs            impede auth dentro do repositório
│   ├── sessao.mjs               abre/fecha Baileys e classifica logout/timeout
│   ├── enviar.mjs               lote stdin → mensagens → ACK stdout
│   ├── grupos.mjs               lista grupos, sem publicar
│   ├── verificar.mjs            verifica sessão/grupos
│   ├── parear.mjs               pareamento controlado por código
│   ├── parear_terminal.mjs      pareamento terminal legado
│   ├── teste_idempotencia.mjs   experimento local/real de reenvio
│   └── tests/*.mjs              testes do pacote
└── tests/*.py, tests/*.mjs      contratos offline e testes adversariais
```

## 3. Arquivos Python de produção: o que são, quem chama, o que chamam

| Arquivo | Frase humana | Quem chama | O que chama |
|---|---|---|---|
| `__main__.py` | Converte `python -m suricata` em chamada da CLI. | Interpretador Python; **hipótese estática**. | `entrypoint.main()` e `SystemExit`. |
| `entrypoint.py` | Valida `--mode/--config`, separa probe, sombra e utilitários, e encaminha a execução. | `__main__.py`; testes de entrypoint. | `executar_config`, `executar_sombra`, `rodada.main`, `grupos.main`, `teste_envio.main`, `CanvasClient`, `EstadoLocal`. |
| `adapter.py` | Impõe a fronteira de dados públicos e normaliza respostas do Canvas; o adapter legado só entra com opt-in. | `entrypoint.py`, `sentinela.py`, testes de adapter. | `_normalize_response`, `unavailable_planner`, cliente injetado ou `FakeCanvasAdapter`. |
| `canvas.py` | Faz GETs allowlisted de cursos, assignments e anúncios e converte payloads para tipos públicos. | `coleta.py`, `entrypoint.py`, `rodada.py`; testes de Canvas. | Transporte `urllib`, validadores de origem/status e conversores `PublicAssignment/PublicCourse/PublicAnnouncement`. |
| `coleta.py` | Busca cursos/assignments/anúncios de produção; preserva coleta parcial e não confunde falha com vazio. | `rodada.py`; **hipótese estática** `sentinela.py` usa outro coletor. | `CanvasClient.courses/assignments/announcements`, `atividade_de`, `Anuncio`. |
| `sentinela.py` | Executa sombra funcional: coleta pública → projeção de domínio → decisão → relatório, sem WhatsApp. | `application.py`; aliases `rodada_sombra`, `coletar`, `projetar`; testes de sombra/sentinela. | `adapter`, `domain.normalizar_evento`, `grupo.decidir_grupo_publico`, `grupo.renderizar_evento`. |
| `planejamento.py` | Mantém o planejamento puro, com eventos, avisos de prova, véspera e predicado da janela matinal. | `rodada.py`, que preserva a fachada pública; testes também importam pela fachada. | `coleta.Anuncio`, `persistencia_rodada.RETENCAO`, `publico` e helpers de tempo/texto. |
| `application.py` | Caso de uso de sombra com persistência e transporte somente quando dependências são explicitamente injetadas. | `entrypoint.py`; testes de application. | `executar_rodada_sombra`, writers de `EstadoLocal`, notifier/delivery injetados, hash para dedup. |
| `domain.py` | Define `EventoPublico`, valida a fronteira pública, identifica elegibilidade e renderiza texto público. | `sentinela.py`, `delivery.py`, `notifiers/whatsapp.py`; testes de domínio. | Normalização de datas/texto, filtros de termos privados e `renderizar_publico`. |
| `publico.py` | Mantém o vocabulário operacional da rodada: tipos, datas, horários, silêncio, lembretes e mensagens. | `rodada.py`, `agenda_manual.py`, `coleta.py`; testes de domínio/horário. | `ZoneInfo("America/Sao_Paulo")`, parsers e helpers puros; não chama rede. |
| `grupo.py` | Política pública de audiência e renderização usada pela sombra/compatibilidade. | `sentinela.py`, testes de grupo. | Normalização e decisão de grupo; não chama WhatsApp. |
| `agenda_manual.py` | Lê agenda JSON de objetos de estado e transforma itens válidos em atividades complementares. | `rodada.py`; testes de audiência/hardening. | `Objetos*.ler`, `publico.Atividade`, `dia/dia_provavel`; rejeita números não finitos/negativos. |
| `configuracao.py` | Interpreta `SURICATA_GRUPO_JID` e destinos JSON/lista, validando JIDs, prefixos e janela BRT. | `rodada.main`/`executar_destinos`; testes de multidestino/configuração. | `Destino.elegivel`, `datetime` em `America/Sao_Paulo`, validação de ambiente. |
| `rodada.py` | Compõe o runtime e mantém a fachada de imports históricos; o fluxo detalhado está nos módulos especializados. | `entrypoint.py`; testes de rodada/E2E. | `execucao`, `coleta`, `planejamento`, `agenda_manual`, Canvas, storage e ponte. |
| `execucao.py` | Executa a rodada: lease → coleta pronta → memória/planejamento → outbox → corte → ponte → relatório. | `rodada.py`; testes de rodada, entrega, corte e caminho real. | `coleta`, `planejamento`, `agenda_manual`, `OutboxSincronizado`, `lease_rodada.Lease`, storage, `message_id` e bridge. |
| `outbox.py` | Máquina durável `pending → in_flight → sent` ou `pending → expirado`, com lock, fencing, retry idempotente e corte atômico. | `rodada.py`, `delivery.py`, `notifiers/whatsapp.py`; testes de outbox/concurrency. | `storage.locking.lock_arquivo`, JSON temporário/fsync/replace; só ACK válido permite `sent`. |
| `persistencia_rodada.py` | Carrega `grupo/outbox.json` para arquivo temporário, poda terminais antigos e publica por geração CAS. | `rodada.py`; testes de rodada/outbox/storage. | `Outbox`, `objetos.ler/gravar`, retenção de 30 dias. |
| `lease_rodada.py` | Serializa a rodada ativa no objeto `locks/rodada.lock`, abandonando leases antigos por CAS. | `rodada.py`, `teste_envio.py`; testes de lease/caminho real. | `objetos.ler/gravar/apagar`, `CASConflict`; `SURICATA_LEASE_MINUTOS` (padrão 6). |
| `lease.py` | Implementa contrato legado de lease com `get/put_if_absent/delete_if_owner`. | Testes de `lease`; **não verificado no caminho canônico**. | `LeaseStore` injetada, relógio e UUID; não chama GCS diretamente. |
| `estado.py` | Mantém heartbeat, memória, dedup e diário JSONL local com locks e escrita atômica, sem dados privados. | `application.py`, testes de estado/application. | filesystem local (`os.replace`, lock nativo), sanitizadores e aliases de compatibilidade. |
| `delivery.py` | Compatibilidade de entrega que registra/reivindica eventos e reconcilia respostas do bridge com o outbox. | Testes de delivery; **uso direto pela produção não foi confirmado** (a rodada usa `entregar`). | `domain`, `message_id`, `Outbox`, `bridge_runner`, `Outbox.aplicar_resultado`. |
| `bridge.py` | Valida lote, materializa auth temporária, executa Node por stdin e só aceita resposta sanitizada/compatível. | `rodada.py`, `notifiers/whatsapp.py`, `grupos.py`; testes de bridge. | `node whatsapp/enviar.mjs`, `storage.cas.SessaoWhatsApp`, `message_id`, subprocesso sem payload em argv. |
| `message_id.py` | Deriva identidade determinística de destino/evento para reenvio sem duplicação. | `rodada.py`, `bridge.py`, `delivery.py`, `notifiers/whatsapp.py`, `teste_envio.py`. | Hash/normalização local; não chama rede. |
| `notifiers/whatsapp.py` | Fachada de notificação pública e compatível que valida payload, usa bridge e devolve ACK/estado seguro. | Testes de notifier e consumidores legados; **não verificado como chamada direta por `rodada.py`**. | `WhatsAppBridge`, `Outbox`, `domain`, `message_id`, CAS/Bridge errors. |
| `storage/gcs.py` | Implementa objetos GCS por JSON API com geração, read-back, retry limitado e equivalente local para testes/sombra. | `rodada.py`, `grupos.py`, `teste_envio.py`, `persistencia_rodada.py`; testes de storage. | metadata server ou `gcloud auth print-access-token`, HTTP Storage API, `ObjetosLocais`, locks. |
| `storage/locking.py` | Fornece lock cross-processo portátil: mutex nomeado no Windows e `fcntl` no POSIX. | `storage/gcs.py`, `outbox.py`; testes de storage/outbox. | filesystem, `ctypes`/Kernel32 no Windows, `fcntl` no POSIX e retry limitado. |
| `storage/cas.py` | Compatibilidade de sessão WhatsApp baseada em `gcloud storage`, com leitura de geração antes/depois e escrita condicional. | `bridge.py`, `grupos.py`, testes de storage. | subprocesso `gcloud`, `whatsapp/auth.json`; não expõe token/sessão em erro. |
| `notifiers/__init__.py` | Exporta a fachada pública do notificador WhatsApp. | Imports de consumidores/testes; **chamada direta não verificada**. | Reexporta `WhatsAppGrupo` e `entregar_grupo` de `notifiers/whatsapp.py`. |
| `grupos.py` | Modo read-only de inventário: materializa auth, roda o Node de grupos e devolve auth por CAS se atualizada. | `entrypoint.py`; testes de grupos/isolamento. | `SessaoWhatsApp`, `WhatsAppBridge._materializar/_ler_auth`, `whatsapp/grupos.mjs`. |
| `teste_envio.py` | Utilitário externo que manda a mesma mensagem duas vezes com o mesmo ID para medição de idempotência. | `entrypoint.py`; teste de caminho/contratos. | `lease_rodada.Lease`, `WhatsAppBridge.enviar_lote`, `message_id`, `SessaoWhatsApp`; requer gate H3. |

### Python não produtivo ou de apoio

- `tests/*.py` são testes offline, não workers de runtime. Cada arquivo está enumerado na seção 6.
- Não há outro `.py` dentro de `suricata/` fora das linhas acima e de `tests/` na árvore conferida.

## 4. Arquivos Node/WhatsApp: o que são, quem chama, o que chamam

| Arquivo | Frase humana | Quem chama | O que chama |
|---|---|---|---|
| `whatsapp/auth-dir.mjs` | Resolve o repositório e bloqueia diretório de autenticação dentro dele. | `sessao.mjs`, `enviar.mjs`, `parear.mjs`, `parear_terminal.mjs`, `teste_idempotencia.mjs`, `verificar.mjs`; testes de segurança. | `fs/path/url`, `realpathAncestro`, `estaDentro`, `validarAuthDir`. |
| `whatsapp/sessao.mjs` | Abre/fecha socket Baileys, espera conexão e classifica timeout/logout. | `enviar.mjs`, `grupos.mjs`, `verificar.mjs`; testes de sessão. | `useMultiFileAuthState`, `fetchLatestBaileysVersion`, `makeWASocket`, eventos de conexão e `saveCreds`. |
| `whatsapp/enviar.mjs` | Lê um lote JSON do stdin, envia cada texto e aguarda ACK; imprime apenas resposta segura. | `bridge.py`; `npm test`/testes de contrato. | `sessao.abrirSessao/fecharSessao`, `sock.sendMessage`, `esperarAck`, timeout. |
| `whatsapp/grupos.mjs` | Abre sessão e lista nome/JID/contagem de grupos, sem conteúdo de mensagens. | `grupos.py`; testes de pacote. | `sessao`, `groupFetchAllParticipating`, stdout JSON. |
| `whatsapp/verificar.mjs` | Verifica se a sessão abre e quantos grupos são visíveis. | Operação humana/testes de contrato; **não chamado pela rodada**. | `sessao`, `groupFetchAllParticipating`, sanitização de erro. |
| `whatsapp/parear.mjs` | Faz pareamento controlado por código, salva QR opcional e lista grupos após conexão. | Operação humana H1/H2; testes de segurança/pacote. | Baileys, `auth-dir`, filesystem temporário, `listarGrupos`. |
| `whatsapp/parear_terminal.mjs` | Variante terminal interativa/legada de pareamento por código. | Operação humana legada; **não verificado como chamada por outro arquivo**. | Baileys, `qrcode-terminal`, `validarAuthDir`, grava `grupos.json` ao lado de auth. |
| `whatsapp/teste_idempotencia.mjs` | Envia duas vezes a mesma mensagem em modo real ou mock local para verificar deduplicação. | Testes `test_whatsapp_ack.mjs`; operação manual; **não é a ponte canônica**. | Baileys, auth temporária, `enviarComAck`, `esperarAck`, `hashDir`, rollback de sessão. |
| `whatsapp/package.json` | Declara scripts/dependências do pacote autocontido. | npm. | `npm test` agrega `../tests/*.mjs` e `./tests/*.mjs`; `test:package` roda apenas pacote. |
| `whatsapp/tests/package.test.mjs` | Testa parser/erros, diretório de auth, ACK e restrições de pareamento. | `npm test`; Node test runner. | Importa `enviar.mjs`, `parear.mjs`, `teste_idempotencia.mjs`, fixtures temporárias. |
| `whatsapp/tests/sessao.test.mjs` | Testa conexão, timeout e logout com socket/funções Baileys falsas. | `npm test`; Node test runner. | `sessao.mjs` e doubles de `EventEmitter`. |

### Fronteira Python → Node → WhatsApp

1. `rodada.entregar` agrupa claims e calcula `message_id` estável.
2. `WhatsAppBridge.enviar_lote` valida `event_id`, `message_id`, texto e lote; lê `whatsapp/auth.json` pelo storage; cria auth temporária fora do repo.
3. A ponte escreve um único JSON no stdin de `whatsapp/enviar.mjs` e limita stdout a JSON parseável; detalhes de stderr são sanitizados.
4. `enviar.mjs` abre Baileys, chama `sendMessage` com o mesmo `message_id` e aguarda ACK/status.
5. A ponte devolve resultados. A rodada só chama `Outbox.aplicar_resultado(..., ack=True)` se sessão `ok`, `message_id` igual, ACK `true` e status inteiro `>= 2`.
6. Sem ACK, timeout, logout, divergência ou crash: estado retorna a `pending`; não há promoção para `sent`.

## 5. Produção, sombra, legado e compatibilidade

### Produção canônica

`entrypoint.main` → `rodada.main` → `executar_destinos` ou `executar` → `CanvasClient`/`coletar` → `agenda_manual` + `planejar` → memória/outbox/relatório → `entregar` → `WhatsAppBridge` → `whatsapp/enviar.mjs` → ACK → CAS/read-back.

- `rodada.py`, `coleta.py`, `publico.py`, `configuracao.py`, `persistencia_rodada.py`, `lease_rodada.py`, `outbox.py`, `storage/gcs.py` e `bridge.py` pertencem ao caminho funcional atual.
- Configuração de produção vem do ambiente: `SURICATA_CANVAS_TOKEN`, `SURICATA_ESTADO_URI`, `SURICATA_ENTREGA`, destinos/JID, `SURICATA_LEASE_MINUTOS` e `SURICATA_WA_AUTH_DIR`.
- `SURICATA_ENTREGA=desligada` impede o efeito externo; não prova que Canvas/GCS estejam ausentes.

### Sombra

- `--mode shadow`: retorna `{"mode":"shadow","status":"ok","adapter":"none"}` e termina. Não consulta Canvas, não grava estado, não chama Node.
- `--mode sentinela --config ...`: lê JSON explícito sem segredo, valida ofertas/origin/timeout/estado, cria `CanvasClient` + `CanvasPublicAdapter` e chama `executar_sombra`. Pode persistir estado se `estado.path`/`state_path` foi explicitamente configurado. Continua sem caminho de produção e sem entrega padrão.
- `application.SentinelaApplication`: permite notifier/delivery injetados em testes ou compatibilidade; isso não torna o modo `sentinela` produção.

### Legado e caminhos de compatibilidade

- `lease.py` é um lease legado com contrato diferente de `lease_rodada.py`; testes cobrem ambos, mas o uso produtivo atual apontado por `rodada.py` é `lease_rodada.Lease`.
- `sentinela.coletar_candidatos_publicos(..., legacy_collector=True)` aceita nomes antigos (`planner`, `assignments`) e callable; o padrão não aceita esses nomes.
- `application.py` mantém `notifier` textual injetado e aliases `executar_sombra`/`run_shadow`; `estado.py` mantém `EstadoSuricata`/`EstadoOperacional` e aliases de escrita.
- `delivery.py` e `notifiers/whatsapp.py` preservam fachadas/outbox anteriores; não há evidência estática de que sejam a chamada principal de `rodada.py`.
- `storage/cas.py` e `whatsapp/teste_idempotencia.mjs` oferecem contratos antigos/operacionais para auth e teste; não substituir `storage/gcs.py`/`rodada.py` sem prova.
- `whatsapp/parear_terminal.mjs` é caminho terminal interativo; `parear.mjs` é o caminho controlado documentado para gates H1/H2.
- `grupos.py` e `verificar.mjs` consultam sessão; não são envio de produção.

## 6. Mapa dos testes `.py` e `.mjs`

Todos são offline por desenho: doubles, fixtures sintéticas, diretórios temporários e transportes falsos. A relação “quem chama” abaixo significa executor (`pytest`, `unittest`, `node --test` ou `npm test`), não runtime de produção.

### Python

| Arquivo | Frase → quem chama → o que chama |
|---|---|
| `tests/test_adapter.py` | Testa adapter/allowlist/fail-closed → pytest/unittest → `adapter.py`. |
| `tests/test_application_integration.py` | Testa persistência/dedupe/heartbeat/entrega injetada → pytest/unittest → `application.py`. |
| `tests/test_application_shadow.py` | Testa sombra, parcial/indisponível e ausência de efeitos → pytest/unittest → `application.py`/`sentinela.py`. |
| `tests/test_audiencia_mentoria.py` | Testa coleta de atividade de mentoria → pytest/unittest → `coleta.py`/`publico.py`. |
| `tests/test_bridge.py` | Testa subprocesso ponte, sessão, timeout, ACK e sanitização → pytest/unittest → `bridge.py`. |
| `tests/test_bridge_integration.py` | Testa rodada → outbox → `FakeBridge` → ACK, sem Node real → pytest/unittest → `rodada.py`/`outbox.py`. |
| `tests/test_bridge_node_e2e.py` | Testa fronteira offline com stub Node local quando presente → pytest/unittest → `bridge.py` e fixture. |
| `tests/test_caminho_real_e2e.py` | Executa `main([--mode, rodada])` com Canvas/entrega/estado falsos → pytest/unittest → `entrypoint.py`/`rodada.py`. |
| `tests/test_canvas.py` | Testa origem, token, payload, status e sanitização → pytest/unittest → `canvas.py`. |
| `tests/test_container_layout.py` | Testa Docker/contexto, lockfile e exclusão de auth/sessão/segredos → pytest/unittest → `Dockerfile`/árvore. |
| `tests/test_corte_21h.py` | Testa corte normal e exceção 07:00 → pytest/unittest → `rodada.py`/`outbox.py`. |
| `tests/test_corte_21h_adversarial.py` | Atravessa relógio, claim/ponte e estados forjados → pytest/unittest → corte/entrega. |
| `tests/test_corte_21h_current_event.py` | Testa evento atual e autorização explícita na janela → pytest/unittest → `rodada.py`. |
| `tests/test_delivery.py` | Testa entrega, ACK, timeout, duplicata e IDs → pytest/unittest → `delivery.py`/`outbox.py`. |
| `tests/test_destinos_validacao.py` | Testa destinos, JID, prefixos e validação → pytest/unittest → `configuracao.py`. |
| `tests/test_discricao.py` | Testa classificação temporal de prova/recado/surpresa → pytest/unittest → `publico.py`. |
| `tests/test_domain.py` | Testa entidade, tipos, datas, elegibilidade e fronteira pública → pytest/unittest → `domain.py`. |
| `tests/test_entrypoint.py` | Testa CLI, modos, config e erros sanitizados → pytest/unittest → `entrypoint.py`. |
| `tests/test_entrypoint_runtime.py` | Testa montagem de cliente/adapter/writer → pytest/unittest → `entrypoint.py`. |
| `tests/test_estado.py` | Testa dedup, memória append-only, heartbeat e escrita atômica → pytest/unittest → `estado.py`. |
| `tests/test_grupo.py` | Testa agrupamento, diário e texto público → pytest/unittest → `grupo.py`. |
| `tests/test_idempotencia_security.mjs` | Contrato de idempotência/segurança → Node test runner → `whatsapp/teste_idempotencia.mjs`. |
| `tests/test_isolamento.py` | Testa manifesto/prefixos e ausência de Telegram → pytest/unittest → `infra/isolamento.json`/árvore. |
| `tests/test_lease.py` | Testa aquisição, expiração, payload e falha fechada → pytest/unittest → `lease.py`. |
| `tests/test_message_id.py` | Testa ID determinístico e colisões → pytest/unittest → `message_id.py`. |
| `tests/test_multidestino.py` | Testa configuração, janela BRT e isolamento por destino → pytest/unittest → `configuracao.py`/`rodada.py`. |
| `tests/test_notifier_whatsapp.py` | Testa notificador, ACK, sessão e `pending` → pytest/unittest → `notifiers/whatsapp.py`. |
| `tests/test_observacoes.py` | Testa observações de calendário/limite de conteúdo → pytest/unittest → `publico.py`. |
| `tests/test_operacao_fail_closed.py` | Testa simulação, coleta parcial, memória/outbox inválidos e bloqueios → pytest/unittest → `rodada.py`/`application.py`. |
| `tests/test_outbox.py` | Testa estados, fencing e expiração → pytest/unittest → `outbox.py`. |
| `tests/test_outbox_concurrency.py` | Testa processos, locks, cache e crashes → pytest/unittest → `outbox.py`/locking. |
| `tests/test_parear_security.mjs` | Contrato de segurança do pareamento → Node test runner → `whatsapp/parear.mjs`/`auth-dir.mjs`. |
| `tests/test_rodada.py` | Testa coleta, decisão, reenvio, lease e transições → pytest/unittest → `rodada.py`. |
| `tests/test_sentinela.py` | Testa compatibilidade sentinela/adapter e legacy opt-in → pytest/unittest → `sentinela.py`. |
| `tests/test_simulacao_futura.py` | Avança sete dias em passos de dez minutos sem entrega → pytest/unittest → caminho de simulação/rodada. |
| `tests/test_storage.py` | Testa storage, precondição de geração e ambiente mínimo → pytest/unittest → `storage/cas.py`. |
| `tests/test_storage_adversarial_worker.py` | Testa escritores concorrentes, CAS e payload misto → pytest/unittest → `storage/cas.py`. |
| `tests/test_storage_cas_revalidation.py` | Testa revalidação de geração, JSON inválido e não finito → pytest/unittest → `storage/cas.py`. |
| `tests/test_storage_local_concurrency.py` | Testa CAS/locks locais entre processos/threads → pytest/unittest → `storage/gcs.py`. |
| `tests/test_storage_local_hardening.py` | Testa atomicidade local e agenda manual hardening → pytest/unittest → `storage/gcs.py`/`agenda_manual.py`. |
| `tests/test_storage_robustez.py` | Testa GCS sem geração e ausência de retry após POST → pytest/unittest → `storage/gcs.py`. |
| `tests/test_whatsapp_ack.mjs` | Testa ACK e deduplicação do envio → Node test runner → `whatsapp/teste_idempotencia.mjs`. |

> `tests/fixtures/bridge_ack_stub.mjs` é um stub Node chamado pelos testes de fronteira; `tests/fixtures/descricoes_computabilidade.json` é fixture de descrição. Não são entrypoints de produção.

### Node/WhatsApp

| Arquivo | Frase → quem chama → o que chama |
|---|---|
| `tests/test_enviar_contract.mjs` | Contrato do envio/parser/sanitização → `node --test` → `whatsapp/enviar.mjs`. |
| `tests/test_idempotencia_security.mjs` | Segurança/idempotência → `node --test` → `whatsapp/teste_idempotencia.mjs`. |
| `tests/test_parear_security.mjs` | Segurança de pareamento/auth-dir → `node --test` → `whatsapp/parear.mjs`/`auth-dir.mjs`. |
| `tests/test_verificar_contract.mjs` | Contrato de verificação e erros → `node --test` → `whatsapp/verificar.mjs`. |
| `tests/test_whatsapp_ack.mjs` | ACK controlado → `node --test` → `whatsapp/teste_idempotencia.mjs`. |
| `whatsapp/tests/package.test.mjs` | Pacote agregado: parser, auth-dir, ACK e guards → `npm test` → módulos WhatsApp. |
| `whatsapp/tests/sessao.test.mjs` | Conexão, timeout e logout com doubles → `npm test` → `whatsapp/sessao.mjs`. |

## 7. Docker, configuração e documentação

- `Dockerfile` fixa `ENTRYPOINT ["python3", "-m", "suricata"]` e `CMD ["--mode", "shadow"]`; instala o runtime Python, faz instalação Node pelo lockfile e copia o contexto `suricata/`. O `CMD` pode ser substituído pelo runtime. **Não verificado:** build Docker limpo, digest publicado, Job/Cloud Run/IAM e sessão real.
- `config.example.json` é somente exemplo do modo sentinela; a oferta `00000000` é placeholder. Não contém token e não é configuração de produção.
- `infra/isolamento.json` é inventário declarativo datado, não injeção de ambiente. `infra/README.md` descreve o isolamento.
- `ARCHITECTURE.md` é a referência de contratos/modos/fonte de configuração e confirma que o estado de nuvem só vale com data/read-back.
- `RUNBOOK.md` é pré-voo/parada/gates H1–H3; comandos de nuvem nele são read-only salvo blocos explicitamente marcados como efeito.
- `DOCUMENTATION.md` roteia produto, arquitetura, runbook, testes, WhatsApp, plano e isolamento.
- `tests/README.md` define executores e limites: suíte offline não prova Canvas/GCS/Cloud Run/WhatsApp reais.
- `whatsapp/README.md` define `npm ci --ignore-scripts --omit=dev`, `npm test` e o bloqueio conhecido da dependência Git `libsignal` do Baileys. **Não verificado aqui:** instalação de rede reproduzível.

## 8. Corte das 21h e janela de envio

- O relógio operacional é `America/Sao_Paulo`; `publico.SILENCIO=(23,7)` impede mensagens entre 23:00 e 06:59.
- O corte absoluto em `rodada._corte_21h` começa em 21:00: depois dele, a rodada não reivindica nem chama a ponte.
- Eventos novos claramente públicos do Canvas que começam e terminam no dia corrente podem ser registrados como exceção para a janela de 07:00; a autorização é validada pelo conteúdo atual, não por uma flag persistida sozinha.
- Às 07:00, apenas o que está explicitamente autorizado pode atravessar; os demais pendentes são expirados pelo corte. Entre 07:00 e 21:00, eventos pendentes podem ser reivindicados; entre 21:00 e 07:00, ficam aguardando ou expiram conforme contrato.
- O relógio é revalidado depois do claim e antes do efeito externo. Se cruzar 21:00 nesse intervalo, claims voltam a `pending`, o outbox é publicado e nenhum envio ocorre.
- O Scheduler acordar um Job não autoriza envio por si só. O corte é uma decisão em runtime, revalidada antes de claim/ponte.

## 9. Outbox, ACK, CAS e recuperação

1. `rodada.entregar` registra eventos no outbox antes de chamar a ponte; reenvio usa o mesmo `event_id`/`message_id`.
2. `Outbox.reivindicar` muda `pending` para `in_flight`, atribui `attempt_id` e incrementa tentativas; a rodada publica essa geração antes do efeito externo.
3. A ponte/Node devolve item correspondente. `sent` exige sessão `ok`, `message_id` idêntico, ACK booleano verdadeiro e status inteiro `>=2`.
4. Qualquer falha/timeout/ACK ausente/divergente usa `aplicar_resultado(... ack=False)` e retorna a `pending` na política idempotente. `sent` e `expirado` são terminais.
5. Uma nova rodada chama `recuperar_interrompidos` para devolver `in_flight` abandonados a `pending`, expira os vencidos e tenta novamente com o mesmo ID.
6. `OutboxSincronizado` publica o arquivo temporário `grupo/outbox.json` por `generation`; `storage/gcs.py` usa `ifGenerationMatch`, detecta 412 como `CASConflict` e o chamador para sem sobrescrever concorrência.
7. Memória e relatório também são gravados com geração; o read-back/geração é a evidência de publicação. **Não verificado:** concorrência real contra bucket Cloud Storage.

## 10. Caminho canônico passo a passo e limites

```text
python -m suricata --mode rodada
  1. entrypoint roteia para rodada.main
  2. rodada exige SURICATA_ESTADO_URI e SURICATA_CANVAS_TOKEN
  3. cria ObjetosGCS/ObjetosLocais e adquire locks/rodada.lock por CAS
  4. cria CanvasClient e coleta cursos, assignments e anúncios públicos
  5. lê memória e agenda_manual; planeja eventos e textos determinísticos
  6. para cada destino elegível, grava/recupera/poda grupo/outbox.json
  7. aplica corte 21h, silêncio noturno e revalidação do relógio
  8. reivindica pending → in_flight e publica antes do efeito
  9. bridge materializa auth temporária e executa whatsapp/enviar.mjs
 10. Node envia via Baileys e aguarda ACK
 11. Python reconcilia ACK: sent ou pending; publica por CAS
 12. grava memória/relatório e libera lease
```

Limites confirmados nos documentos: primeira rodada é linha de base e não anuncia; coleta parcial nunca equivale a ausência; Canvas não fornece `submission`, nota, quiz aberto ou tentativa; Node não é dono do estado; auth/QR/sessão/segredos ficam fora do Git; testes verdes são evidência local apenas.

## 11. Hipóteses e não verificado

- As relações “quem chama” foram derivadas de imports, `main()` e referências locais; não foi usado tracing em produção.
- `infra/isolamento.json` registra nomes históricos de Job/Scheduler divergentes do plano (`suricata-rodada*` versus `suricata-sentinela*`); não há read-back de nuvem neste mapa.
- Não foi provado build Docker real, instalação npm com rede, digest implantado, IAM, Cloud Run, Scheduler ativo, GCS atual, Canvas ao vivo, sessão Baileys conectada ou envio real.
- `delivery.py`, `notifiers/whatsapp.py`, `lease.py`, aliases e pareamento terminal permanecem por compatibilidade/testes; ausência de chamada direta no caminho descrito não prova que nenhum consumidor externo os use.
- `test_bridge_node_e2e.py` depende da presença/configuração do stub local; não é prova de subprocesso Node real com Baileys.
- O nome humano “produção” segue a arquitetura/documentação local; confirmação operacional exige o read-back do `RUNBOOK.md` antes de qualquer efeito.
