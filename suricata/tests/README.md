# Guia humano dos testes do Suricata

Este diretório reúne testes Python (`.py`) e contratos Node (`.mjs`). A organização abaixo é por intenção, não por ordem de execução. O inventário e os comandos refletem os arquivos encontrados localmente em `2026-09-16`; não implicam uma porcentagem de cobertura nem equivalência após refatoração.

Os testes são offline por desenho: usam doubles, fixtures sintéticas, diretórios temporários e transportes falsos. Não conectam ao Canvas, GCS, Cloud Run ou WhatsApp real.

## Escolha rápida do executor

| Quando | Comando | Use porque |
|---|---|---|
| Rodar a suíte Python com saída curta | `python -m pytest -q suricata/tests` | O `pytest` coleta os testes baseados em `unittest`, oferece filtragem, seleção por palavra e relatório compacto. |
| Rodar somente com a biblioteca padrão | `python -m unittest discover -s suricata/tests` | É o executor canônico de `unittest` e não exige pytest; útil para confirmar que a suíte não depende de recursos específicos do pytest. |
| Inspecionar ou rodar uma fatia Python | `python -m unittest -v suricata.tests.test_caminho_real_e2e` | Executa um módulo/classe/caso específico com nomes detalhados. Troque o módulo pelo alvo desejado. |
| Rodar contratos JavaScript | `node --test suricata/tests/*.mjs` | O runner nativo do Node executa os cinco arquivos `.mjs` desta pasta; exige Node `>=20` para o pacote WhatsApp. |
| Rodar o pacote oficial do WhatsApp | `npm run test:package` (em `suricata/whatsapp`) | Executa somente `whatsapp/tests/package.test.mjs`. |
| Rodar todos os contratos Node locais | `npm test` (em `suricata/whatsapp`) ou `node --test tests/*.mjs whatsapp/tests/*.mjs` (em `suricata`) | Inclui os cinco contratos desta pasta e os dois testes do pacote WhatsApp, inclusive `sessao.test.mjs`. |

No Git Bash, os curingas `*.mjs` são expandidos pelo shell. Em outro shell, passe os caminhos explicitamente se a expansão não ocorrer.

## Mapa por intenção

### 1. Domínio, política pública e renderização

Validam normalização, elegibilidade, datas, descrições, observações, IDs determinísticos e a regra de não expor dados pessoais ou instruções indevidas.

- `test_multidestino.py` — configuração, janela BRT e isolamento por destino.
- `test_message_id.py` — `message_id` determinístico e colisões.
- `test_discricao.py` — classificação temporal de provas, recados e surpresas.
- `test_observacoes.py` — observações de calendário e limite de conteúdo.
- `test_audiencia_mentoria.py` — coleta da atividade de mentoria.

Use esta fatia quando alterar regras de negócio, campos públicos, texto gerado, datas ou identidade de evento. As asserções devem observar o contrato externo, não nomes de funções ou a implementação interna.

### 2. Canvas e entrypoint

Validam a fronteira com o Canvas sem fazer requisições reais e a seleção segura dos modos de execução.

- `test_canvas.py` — origem, token, payload, status e sanitização.
- `test_entrypoint.py` — CLI, modos `shadow`/`demo`/`rodada` e erros sanitizados.
- `test_caminho_real_e2e.py` — caminho de produção Python via `main(["--mode", "rodada"])`, com Canvas falsificado, entrega desligada e diretório temporário.

O `test_caminho_real_e2e.py` é E2E do caminho Python, não um E2E com processo Node/WhatsApp real.


### 3. Orquestração, horários e simulação

Validam lease, rodada, janela de Brasília, corte noturno, revalidação e simulação sem efeitos.

- `test_rodada.py` — coleta, decisão, reenvio, expiração, lease e transições da rodada. Os doubles/fakes compartilhados (`JID`, `AGORA`, `iso`, `CanvasFalso`, `PonteFalsa`, `quiz`) vivem em `_fakes.py` e são re-exportados por `test_rodada.py` para compatibilidade dos importadores.
- `test_corte_21h.py` — regras normais do corte das 21:00 e exceção das 07:00.
- `test_corte_21h_adversarial.py` — relógio atravessando o corte, revalidação entre claim e ponte e estados forjados.
- `test_operacao_fail_closed.py` — simulação, coleta parcial, memória/outbox inválidos e bloqueios de segurança.
- `test_simulacao_futura.py` — avanço de sete dias em passos de dez minutos sem entrega nem ponte.

Para mudanças de horário, teste explicitamente `20:59:59`, `21:00`, `21:00` após claim, `06:59:59` e `07:00`. Não use `datetime.now()` nas expectativas: injete o relógio.

### 4. Outbox, durabilidade, CAS e concorrência

Validam persistência, idempotência, fencing, ACK, crash recovery, expiração, atomicidade e concorrência local.

- `test_outbox.py` — transições, `pending`, `in_flight`, `sent`, fencing e expiração.
- `test_outbox_concurrency.py` — múltiplos processos, locks, cache obsoleto e crashes.
- `test_storage.py` — adapter de storage, precondição de geração e ambiente mínimo.
- `test_storage_adversarial_worker.py` — escritores concorrentes, conflito de geração e payload misto.
- `test_storage_cas_revalidation.py` — revalidação de geração, JSON inválido e valores não finitos.
- `test_storage_robustez.py` — geração inexistente e erro de transporte sem repetição indevida.

Ao mudar uma transição, escreva primeiro uma expectativa observável, provoque uma mutação de uma linha/branch para confirmar que o teste fica vermelho e só então restaure a implementação. Nunca substitua a asserção por “não lança exceção” quando o contrato exige estado, geração ou conteúdo específico.

### 5. Integração e isolamento

Validam fronteiras entre componentes, empacotamento e ausência de dependências indevidas.

- `test_bridge.py` — runner/ponte, sessão, timeout, ACK e sanitização.
- `test_bridge_integration.py` — rodada → outbox → `FakeBridge` → ACK; o Node real não é iniciado.
- `test_bridge_node_e2e.py` — fronteira offline com stub Node local, quando presente no checkout.
- `test_isolamento.py` — manifesto, prefixos e ausência de Telegram.
- `test_container_layout.py` — contexto de empacotamento, lockfile e exclusão de sessão, bancos e segredos.

Esses testes demonstram contratos locais e simulados. Ainda não demonstram build Docker real, Cloud Job, IAM, Canvas ao vivo ou WhatsApp real.

### 6. Node/WhatsApp

Os cinco contratos Node desta pasta são executados diretamente pelo Node:

- `test_enviar_contract.mjs` — contrato do envio.
- `test_idempotencia_security.mjs` — idempotência e segurança.
- `test_parear_security.mjs` — pareamento e fronteiras de segurança.
- `test_verificar_contract.mjs` — contrato de verificação.
- `test_whatsapp_ack.mjs` — ACK do WhatsApp.

Há também testes fora deste diretório, em `suricata/whatsapp/tests/`:

- `package.test.mjs` — 4 testes executados por `npm test`.
- `sessao.test.mjs` — 3 testes de configuração, timeout e logout; execute-o explicitamente no comando agregado.

Nenhum desses comandos inicia Baileys conectado ou envia mensagens reais.

## Fixtures e doubles

- Prefira `TemporaryDirectory`/diretório temporário a arquivos no repositório.
- Use tokens, JIDs, URLs e IDs claramente fictícios; nunca copie segredo, cookie, sessão, JID pessoal ou URL assinada para uma fixture.
- A fixture deve representar a entrada do contrato e ser independente da fórmula da implementação. O esperado deve ser literal ou calculado por uma regra independente.
- Injete relógio, transporte, ponte e storage. Mocke somente a fronteira necessária; não substitua todo o caminho que o teste pretende provar.
- Para testes de subprocesso, isole `HOME`, diretório temporário e variáveis de ambiente; confira stdout, stderr, exit code e manifesto final de arquivos.
- Preserve casos de ausência, resposta parcial, status HTTP não-OK, payload inválido, Unicode e campos extras. Ausência de dado não deve virar “sucesso” por conveniência.
- Ao testar persistência, feche conexões SQLite/arquivos em todos os caminhos, inclusive retornos antecipados; isso é especialmente importante no Windows.

## Testes adversariais

Adversarial não significa gerar ruído aleatório: significa atacar uma invariante específica. Inclua pelo menos um caso que tente quebrar cada regra de alto risco:

- inverter ou atravessar o corte 21h;
- aceitar ACK falso, divergente, atrasado ou com `message_id` estrangeiro;
- repetir o mesmo evento ou reutilizar o `event_id` com conteúdo diferente;
- remover allowlist, inserir segredo aninhado ou misturar gerações CAS;
- simular crash antes/depois do envio e timeout do processo;
- usar lease ocupado, payload inválido, valor não finito ou resposta parcial;
- tentar escapar do sandbox por caminho, symlink/junction, ambiente ou arquivo de sessão.

O teste deve falhar quando a mutação correspondente for introduzida. Não relaxe a expectativa para acomodar a mutação; corrija a fixture ou a própria expectativa somente quando a regra observada estiver errada.

## E2E offline: o que existe e o que ainda não existe

Existe um E2E do caminho Python (`test_caminho_real_e2e.py`) e uma simulação futura sem efeitos (`test_simulacao_futura.py`). A integração Python↔Node ainda usa `FakeBridge`/mocks; os testes não constituem prova de um subprocesso Node real atravessando stdin/stdout.

Para uma futura suíte E2E offline, use um stub Node executável local que leia um lote, devolva ACKs controlados e permita cenários de sucesso, timeout, ACK divergente e crash. Execute Python e Node em subprocessos, com `SURICATA_ENTREGA=desligada` quando o caso não for de entrega, sandbox temporário e fixtures Canvas congeladas. O runner deve falhar ao resolver DNS, abrir socket externo, encontrar credencial real ou escrever fora do sandbox.

Normalize artefatos antes de comparar implementações: exit code, stdout/stderr sanitizados, relatório, outbox/memória/heartbeat/CAS, chamadas observáveis e manifesto do filesystem. Ignore somente diferenças explicitamente não observáveis, como caminho temporário e timestamps derivados de relógio injetado. A árvore atualmente não contém baseline old/new nem runner dual; portanto não declare equivalência de refatoração com base apenas nos testes verdes atuais.

## Sequência prática

1. Rode a fatia diretamente afetada.
2. Rode a suíte Python com `pytest` e, quando a mudança for estrutural, confirme com `unittest discover`.
3. Rode `node --test suricata/tests/*.mjs` se a fronteira Node/contrato for afetada.
4. Para mudanças na integração WhatsApp, rode também `npm test` em `suricata/whatsapp` e o agregado `node --test tests/*.mjs whatsapp/tests/*.mjs` em `suricata`.
5. Verifique sintaxe com `python -m compileall -q suricata` e `node --check` nos `.mjs` quando aplicável.
6. Registre lacunas honestamente: teste offline não prova serviço externo, e contagem de testes passantes não é medida de cobertura.
