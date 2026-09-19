# Plano técnico faseado — bot individual por estudante

> **DRAFT / NÃO IMPLEMENTADO / NÃO É PROMESSA DE LANÇAMENTO**
>
> Este documento é um plano de implementação futura. Não altera o modelo coletivo,
> não cria identidade de estudante, não autoriza acesso a Canvas/WhatsApp e não
> afirma que exista API institucional, aprovação jurídica, suporte do WhatsApp ou
> operação cloud por estudante. O produto atual continua independente e não oficial.
>
**Objetivo:** evoluir o ciclo coletivo da Suricata para instâncias isoladas por estudante, com identidade/tenant local da instância, escopo Canvas, destino WhatsApp confirmado, estado separado, revogação e limites operacionais verificáveis. O alvo de operação é **self-hosted por estudante**: cada estudante administra sua própria conta/projeto cloud, seus secrets, seu Job/Scheduler, seu estado e seus custos. Não haverá um serviço multi-tenant central como requisito do MVP.

**Contrato de compatibilidade com o repositório atual:** a primeira instância individual deve continuar usando os entrypoints `shadow`, `demo` e `rodada`, as variáveis `SURICATA_*`, os backends local/GCS, o ciclo Python → ponte Node e os contratos de outbox/CAS/lease/ACK já testados. O onboarding novo não deve exigir um servidor central, trocar o formato de destino coletivo por mágica ou alterar o comportamento de uma instância legada configurada corretamente.

**Regra de execução:** cada fase só pode começar depois do gate anterior. Falha de identidade, consentimento, escopo, sessão, namespace, CAS, ACK, orçamento ou autorização deve permanecer fail-closed. Nenhuma fase inclui pareamento real, envio real, alteração de IAM, Job, Scheduler ou recurso cloud sem autorização explícita e read-back.

---

## 1. Estado atual e fronteira do plano

### 1.1 O que já existe e pode ser reutilizado

| Área | Evidência no repositório | Estado atual | Reuso planejado |
|---|---|---|---|
| Entrypoint e modos | `suricata/entrypoint.py:9-63`, `suricata/rodada/` | `shadow`, `demo` e `rodada`; configuração por ambiente | adicionar um fluxo de primeira configuração/administração somente quando o contrato estiver definido; não transformar `shadow` em onboarding |
| Configuração | `suricata/rodada/config.py:23-169`, `docs/configuracao.md` | `SURICATA_CANVAS_TOKEN`, `SURICATA_ESTADO_URI`, `SURICATA_ENTREGA`, destinos/JIDs e cursos excluídos; destino atual aceita grupos `@g.us` | manter compatibilidade coletiva durante migração; introduzir um resolvedor de tenant antes de aceitar configuração individual |
| Rodada | `suricata/rodada/execucao.py:263-371` | coleta uma vez, processa destinos, memória por `destino_prefixo`, lease global, entrega condicional | extrair contexto de tenant e lease/estado por namespace sem alterar a semântica de `pending → in_flight → sent` |
| Canvas | `suricata/integracao/canvas.py:18-134` | origem fixa `https://pucminas.instructure.com`, somente `GET`, rotas `assignments`, `announcements`, `courses`, DTOs minimizados | reutilizar transporte/allowlist e criar escopo de cursos por tenant; não inventar endpoint, OAuth, SSO ou escopo institucional |
| CAS/objetos | `suricata/storage/objetos_gcs.py`, `objetos_locais.py`, `cas.py` | geração explícita, `ifGenerationMatch`, leitura por geração, locks locais e falha sanitizada | namespace físico do tenant deve ser resolvido pelo servidor/política, não por caminho arbitrário recebido do estudante |
| Lease | `suricata/storage/lease_rodada.py:17-77` | `locks/rodada.lock`, TTL configurável por `SURICATA_LEASE_MINUTOS`, CAS e dono aleatório | trocar o lease global por escopo definido (tenant/worker) apenas após provar concorrência e não-vazamento; preservar fencing |
| Outbox | `suricata/storage/outbox.py:27-328`, `persistencia_rodada.py` | estados fechados, lock/releitura, `attempt_id`, ACK obrigatório, idempotência, retenção de 30 dias | incluir tenant, destino e versão de consentimento no contrato; rejeitar replay cross-tenant |
| Sessão WhatsApp | `suricata/storage/sessao.py`, `suricata/storage/cas.py`, `suricata/integracao/bridge.py` | auth JSON fora do clone ou em `whatsapp/auth.json` no namespace; CAS/read-back; subprocesso Node com ambiente mínimo | uma sessão por instância/tenant, com ciclo de vida e revogação explícitos; não assumir que a sessão atual já é individual |
| Ponte WhatsApp | `suricata/whatsapp/enviar.mjs`, `sessao.mjs` | Baileys, validação do diretório, lote, ACK técnico e estado de sessão | manter Node como adaptador; a autorização semântica do destino deve ser decidida antes da ponte |
| Pareamento e grupos | `suricata/whatsapp/parear.mjs:130-214` | apenas terminal local explícito; lista grupos participantes em `grupos.json`; limpa inventário após confirmação | reaproveitar como ferramenta de primeira configuração local, acrescentando confirmação de posse/autorização; não colocar pareamento no Job cloud |
| Testes | `suricata/tests/`, `suricata/whatsapp/tests/` | contratos Canvas, bridge, ACK, outbox, CAS, lease, concorrência, cortes e isolamento coletivo | ampliar com fixtures A/B, revogado, corrida, custo e migração; preservar a matriz atual |

### 1.2 O que está ausente e bloqueia o bot individual

- identidade autenticada do estudante e vínculo seguro com um tenant opaco;
- consentimento versionado, granular, expirável e revogável;
- autoridade para resolver `tenant → estado, segredo, cursos e destinos`;
- separação de credencial Canvas por estudante, com política de escopo e retenção;
- fluxo definido para número pessoal de configuração e número/chip da conta do bot;
- prova de posse/autorização do número, conversa privada ou grupo;
- seleção de cursos individual; hoje `CanvasClient.courses()` apenas lista cursos ativos e a coleta coletiva não aplica seleção por tenant;
- estado de adesão (`rascunho`, `aguardando_consentimento`, `ativa`, `pausada`, `revogada`);
- revogação atômica que invalide coleta, claims, retries e sessão;
- quotas por tenant, limites de custo, circuit breaker e orçamento verificável;
- IAM, Secret Manager, bucket/prefixos, backups, logs e observabilidade multi-tenant testados;
- migração/rollback do destino coletivo sem misturar memória, outbox, sessão ou mensagens.

A spec existente confirma essas lacunas em `docs/historico/individual-bot-product-spec.md` e o modelo de ameaças em `docs/historico/individual-bot-threat-model.md`. Não implementar por simples adição de JIDs, tokens ou lista de estudantes.

---

## 2. Fase 0 — decisões e contratos antes do código

**Objetivo:** fechar as decisões externas que não podem ser deduzidas do código.

**Artefatos a criar ou aprovar:**

- decisão do responsável pelo serviço, base legal, privacidade e natureza não oficial;
- decisão registrada: cada estudante conecta e opera um número/chip próprio do bot; conta de serviço compartilhada não é o alvo do MVP;
- contrato de autenticação da pessoa e confirmação do número pessoal, sem pedir segredo no chat;
- fonte autorizada e limites reais do Canvas; somente rotas verificadas podem entrar no adapter;
- política de retenção/exclusão para token Canvas, auth Baileys, cursos, eventos, outbox, logs e backups;
- matriz de suporte/incidente e responsável pelo orçamento;
- limites provisórios aprovados como configuração explícita, não como valores inventados no código.

**Gate G0:** cada decisão tem fonte, responsável, versão, data e teste/read-back previsto. Sem G0, o único produto permitido continua sendo coletivo.

---

## 3. Fase 1 — primeira configuração local segura

**Objetivo:** criar um onboarding local reproduzível e sem efeito externo, separado do ciclo de produção.

**Arquivos prováveis:**

- `suricata/entrypoint.py` e novo módulo de primeira configuração somente se o contrato CLI for aprovado;
- `suricata/rodada/config.py` para validação estrutural, sem segredos no arquivo;
- `docs/configuracao.md`, `docs/guia.md` e `suricata/whatsapp/README.md`;
- testes em `suricata/tests/test_entrypoint.py`, `test_cli_contract.py`, `test_session_namespace.py` e `suricata/whatsapp/tests/`.

**Implementação planejada:**

1. Gerar identificador interno opaco, estável e não derivado do telefone/JID.
2. Criar diretório local descartável fora do clone; validar raiz real e ancestrais, como `auth-dir.mjs` já faz em `validarAuthDir`.
3. Persistir somente metadados mínimos do estado de onboarding; segredos entram por vault/ambiente autorizado, nunca por argv, Git ou chat.
4. Permitir `shadow`/fixture sem rede e com `SURICATA_ENTREGA=desligada`; não usar `demo` como prova de conta real.
5. Exercitar `parear.mjs` apenas como ferramenta local interativa autorizada. QR/código nunca vai para log, fixture ou relatório.

**Testes/gate G1:** primeira configuração repetida é idempotente; traversal, symlink, diretório no repo, tenant adulterado e segredo falso falham; o processo filho recebe ambiente mínimo; `python -m suricata --mode shadow`, `python -m pytest -q` e `node --test` seguem verdes; zero chamada Canvas/WhatsApp em modo offline.

---

## 4. Fase 2 — identidade, tenant e consentimento

**Objetivo:** introduzir a unidade de isolamento antes de tocar coleta ou entrega.

**Arquivos prováveis:** novo módulo de identidade/adesão; `suricata/storage/` para objetos e CAS; `suricata/rodada/execucao.py`; testes A/B.

**Contrato mínimo a definir:**

- tenant opaco não derivado de telefone, JID ou curso;
- adesão com estados `rascunho → aguardando_consentimento → ativa → pausada → revogada`;
- versão de política, finalidade, fontes, cursos, destino, retenção, criação, expiração e revogação;
- resolução autorizada de tenant a partir da identidade autenticada, nunca de um `student_id` arbitrário na requisição;
- reativação após `revogada` exige nova adesão/consentimento; não há reativação silenciosa.

**Invariantes:** nenhuma rodada consulta Canvas, cria claim ou chama bridge sem identidade, consentimento vigente, escopo e destino compatíveis. Identidade, conteúdo acadêmico e JID são campos/fronteiras diferentes.

**Testes/gate G2:** matriz A/B prova que leitura, relatório, erro, dead-letter, retry e exportação de A não contêm B; adulteração de tenant, replay de token revogado, expiração e concorrência CAS falham fechados.

---

## 5. Fase 3 — segredo Canvas e seleção de cursos

**Objetivo:** transformar a coleta coletiva em coleta limitada ao escopo confirmado do tenant.

**Pontos de integração reais:** `CanvasClient.__init__`, `CanvasClient.courses`, `assignments`, `announcements`, `ROUTES`, `coletar` em `suricata/rodada/coleta.py` e `cursos_excluidos_do_ambiente` em `suricata/rodada/config.py`.

**Implementação planejada:**

1. Definir materialização do token por tenant via Secret Manager/vault, sem alterar `SURICATA_CANVAS_TOKEN` global até existir compatibilidade/migração segura.
2. Validar token ausente, errado, expirado, 401, 403, 429 e transporte indisponível como estados explícitos; nunca converter falha parcial em “sem atividade”.
3. Exibir cursos retornados por `CanvasClient.courses()` somente no fluxo autorizado; seleção inicial mínima, sem “todos” por padrão.
4. Persistir apenas IDs/nome mínimo e versão da seleção; revalidar curso removido, arquivado, duplicado, sem permissão ou não encontrado.
5. Filtrar assignments/anúncios pelos cursos selecionados antes do planejamento, mantendo a proveniência, momento e estado de coleta.
6. Proibir rotas ou campos individuais não presentes nos contratos atuais; não inventar OAuth, SSO, endpoint ou escopo institucional.

**Testes/gate G3:** fixtures sintéticas verificam curso selecionado/removido, token de tenant A nunca usado para B, campos proibidos (notas, frequência, submissões, tentativas e respostas) ausentes, rate limit sem retry infinito, origem Canvas allowlisted e coleta parcial visível no relatório.

---

## 6. Fase 4 — número pessoal, número do bot e sessão WhatsApp

**Objetivo:** estabelecer posse, finalidade e ciclo de vida dos números sem confundir identidade da pessoa com conta do bot.

**Decisões obrigatórias:**

- número pessoal: apenas configuração/confirmacão/suporte, ou também destino privado? Registrar a finalidade separadamente;
- número/chip do bot: conta conectada por tenant, controle da sessão, troca, logout e comprometimento;
- destino: conversa privada, grupo autorizado ou ambos; a capacidade coletiva atual valida apenas JIDs de grupo (`@g.us`), não posse.

**Reuso e mudanças prováveis:** `parear.mjs`/`auth-dir.mjs` para bootstrap local, `SessaoWhatsApp`, `SuricataSessionStorage`, `WhatsAppBridge`, `enviar.mjs` e `sessao.mjs`.

**Implementação planejada:**

1. Confirmar o número por mecanismo não inventado e guardar somente prova/metadado mínimo.
2. Manter sessão Baileys em namespace exclusivo do tenant, com CAS/read-back e IAM dedicado.
3. Tornar troca de número, logout, sessão ausente, sessão comprometida e revogação estados explícitos.
4. Não aceitar JID digitado, nome de grupo ou presença como prova de autorização; o inventário de `listarGrupos` é evidência de participação técnica, não consentimento semântico.
5. Exigir confirmação do destino antes do primeiro conteúdo acadêmico; manter destino mascarado em suporte/logs.

**Testes/gate G4:** QR/código/token nunca aparece em stdout/stderr; auth de A não materializa em B; sessão dentro do repo, symlink e caminho externo indevido são rejeitados; troca de destino cria nova confirmação; logout/revogação impede ponte e retry; ACK continua sendo prova técnica de envio, não de leitura.

---

## 7. Fase 5 — grupos autorizados e destinos

**Objetivo:** permitir seleção de grupos somente quando houver autorização demonstrável.

**Pontos atuais:** `Destino` e `destinos_do_ambiente` em `suricata/rodada/config.py` validam forma e prefixo; `executar_destinos` em `suricata/rodada/execucao.py:338-371` separa estado por destino; `message_id()` e `WhatsAppBridge._validar_entrada()` associam lote a JID.

**Implementação planejada:**

- separar `tenant_id`, identidade do grupo, JID técnico e prova de autorização;
- substituir configuração global de `SURICATA_GRUPO_JID`/`SURICATA_DESTINOS_JSON` por uma resolução autorizada por tenant, mantendo o formato coletivo durante migração;
- fazer baseline de um grupo novo não enviar novidade, anúncio, véspera ou lembrete sem consentimento;
- namespacear memória, outbox, relatório, chave de deduplicação e mensagem por tenant e destino;
- impedir dois IDs que apontem ao mesmo JID dentro do mesmo tenant;
- impedir qualquer fallback para grupo coletivo quando o destino individual estiver ausente ou revogado.

**Testes/gate G5:** dois tenants com o mesmo `event_id` produzem registros isolados; JID trocado, duplicado, grupo não participante, autorização expirada e destino revogado não chamam a ponte; `message_id` permanece determinístico dentro do namespace correto; corte 21:00 é revalidado imediatamente antes do efeito externo.

---

## 8. Fase 6 — namespaces, CAS, lease e outbox multi-tenant

**Objetivo:** garantir isolamento físico/lógico e concorrência correta sob crash, retry e múltiplos estudantes.

**Desenho a validar antes de codificar:**

```text
<tenant-opaco>/
  consentimento.json
  escopo-cursos.json
  destinos/<destino-opaco>/
    memoria.json
    outbox.json
    ultima-rodada.json
  whatsapp/auth.json
  locks/rodada.lock
  falhas/
```

O formato acima é proposta de namespace, não contrato existente. `ObjetosGCS._nome`, `ObjetosLocais._caminho`, `SessaoWhatsApp._nome_sessao`, `OutboxSincronizado` e `Lease` devem aceitar apenas nomes derivados de contexto autorizado. Não permitir que o usuário forneça prefixo/bucket/objeto para atravessar tenant.

**Mudanças planejadas:**

- decidir lease por tenant, por lote ou scheduler global; evitar um lease global que bloqueie estudantes ou autorize escrita lateral;
- adicionar tenant/destino/versão de adesão a todo registro mutável e validar no carregamento;
- preservar geração CAS, read-back, lock de arquivo e retry Windows já presentes;
- impedir que `in_flight` de uma versão antiga seja reaplicado após revogação ou troca de destino;
- definir retenção e exclusão de `sent`, `expirado`, dead-letter, memória, logs e backups por tenant.

**Testes/gate G6:** pelo menos 40 processos `spawn` em cada interpretador suportado para outbox/storage; crash entre claim e bridge; CAS obsoleto; corrupção; path traversal; symlink; duplicata; foreign `attempt_id`; A/B com leitura física e lógica. O gate exige zero vazamento, não apenas testes unitários verdes.

---

## 9. Fase 7 — revogação, pausa, exclusão e recuperação

**Objetivo:** tornar a retirada de autorização atômica, observável e irreversível para aquela adesão.

**Implementação planejada:**

1. Sob CAS/lock, marcar adesão `pausada` ou `revogada` e incrementar uma versão/fence de autorização.
2. Antes de coletar, planejar, reivindicar ou enviar, revalidar o estado e a versão.
3. Cancelar/expirar `pending`; devolver/invalidar `in_flight` conforme política, sem afirmar que mensagem já aceita pelo WhatsApp foi apagada.
4. Bloquear novas consultas Canvas, retries, bridge e reativação silenciosa.
5. Revogar/invalidar segredo e sessão quando aplicável; não confundir logout com revogação completa.
6. Executar exclusão verificável em estado local/GCS, temporários, logs, caches, backups e dead-letter segundo prazos aprovados.

**Testes/gate G7:** revogação em `pending`, `in_flight` e `sent`; corrida com lease/CAS; restart; retry obsoleto; destino trocado; exclusão parcial; read-back da versão revogada. O relatório de suporte deve expor só metadados sanitizados e `message_id` técnico.

---

## 10. Fase 8 — limites de custo, abuso e observabilidade

**Objetivo:** impedir que uma instância ou conta comprometida gere custo, spam ou carga sem teto.

**Limites a fixar antes de ativar:** estudantes ativos, cursos/ destinos por tenant, requisições Canvas por janela, concorrência por token, mensagens/bytes/retries por dia, tempo de ponte, TTL de eventos, custo por rodada e orçamento global.

**Comportamento seguro:** exceder quota, orçamento, 401/403/429, logout, volume anômalo ou mudança brusca de cursos/JIDs deve pausar/quarentenar novas coletas/entregas e informar o titular sem degradar para o destino coletivo.

**Observabilidade:** métricas/logs estruturados por estado (`coleta parcial`, `outbox inválido`, `sem ACK`, `custo/quota`, `revogado`), com tenant mascarado/opaco e sem conteúdo, token, QR, sessão, JID real ou telefone. Configurar filtros/alertas estreitos por recurso e fazer read-back; não disparar o Job ativo apenas para testar alertas.

**Gate G8:** teste de carga e abuso com fixtures; retry finito; circuit breaker; custo estimado reproduzível; alerta não reidentificante; orçamento e conta/projeto confirmados separadamente. Valores ausentes continuam `não verificado`, não são inventados.

---

## 11. Fase 9 — migração do modelo coletivo

**Objetivo:** introduzir o individual sem alterar ou contaminar a instância coletiva existente.

**Estratégia:**

1. congelar o contrato coletivo atual (`SURICATA_GRUPO_JID`/destinos e namespace `grupo`);
2. criar namespace/tenant canário completamente distinto, com bucket/prefixo/segredo/sessão próprios;
3. adicionar resolução explícita de modo coletivo versus individual; ausência/ambiguidade falha fechado;
4. não migrar automaticamente token, sessão, memória, outbox ou consentimento coletivo para estudante;
5. executar backfill somente de configuração mínima aprovada, com dupla leitura e reconciliação, nunca de conteúdo ou segredo;
6. manter rollback para o executor coletivo e verificar que nenhum tenant individual cai no grupo coletivo;
7. promover por digest e ambiente canário, com read-back de projeto, imagem, args, env não secreto, IAM, estado e Scheduler.

**Gate G9:** clone limpo contém somente artefatos rastreados; testes de paridade do coletivo continuam verdes; testes A/B provam isolamento após migração; canário shadow não chama Canvas real nem ponte; promoção só após execução posterior usar o digest esperado. Nenhum Job/Scheduler/Cloud Build real é alterado sem autorização específica.

---

## 12. Fase 10 — gates de teste e operação antes de sair do DRAFT

### Gate técnico local

```bash
python -m compileall -q suricata
python -m pytest -q
python -m unittest discover -s suricata/tests
cd suricata/whatsapp && npm ci && node --test
cd ../.. && python -m suricata --mode shadow
```

Executar também os testes focados existentes: `test_canvas.py`, `test_bridge.py`, `test_bridge_integration.py`, `test_outbox.py`, `test_outbox_concurrency.py`, `test_storage_cas_revalidation.py`, `test_session_namespace.py`, `test_lease_rodada.py`, `test_multidestino.py`, `test_corte_21h_adversarial.py`, `test_e2e_rodada_offline.py` e testes Node de pareamento/ACK. Acrescentar a matriz individual sem remover regressões coletivas.

### Gate adversarial

- tenant A/B e segredo/sessão/destino trocados;
- identidade ausente, consentimento expirado/revogado e reativação silenciosa;
- curso removido, token errado, 401/403/429, resposta inválida e coleta parcial;
- JID de terceiro, grupo não autorizado, duplicata e path traversal;
- crash em claim/bridge/persistência, ACK falso, resposta extra/fora de ordem e retry obsoleto;
- symlink, corrupção CAS/outbox, concorrência Windows e 40 processos `spawn`;
- corte no minuto anterior/exato/posterior de 21:00;
- teto de mensagens, bytes, Canvas, custo e sessão;
- logs/stdout/stderr sem conteúdo sensível.

### Gate operacional e humano

- identidade, fonte Canvas, destino, sessão, IAM, segredo, retenção, orçamento e suporte têm evidência própria;
- build limpo, imagem por digest e entrypoint efetivo são verificados;
- canário shadow, canário limitado e rollback são exercitados;
- pareamento e envio real exigem autorização explícita e confirmação humana fora deste plano;
- somente após esses gates a documentação pode deixar de dizer `DRAFT / NÃO IMPLEMENTADO`.

---

## 13. Arquivos que provavelmente mudarão (não alterar nesta tarefa)

**Runtime Python:** `suricata/entrypoint.py`, `suricata/rodada/config.py`, `suricata/rodada/coleta.py`, `suricata/rodada/execucao.py`, novos módulos de identidade/adesão/escopo/limites, `suricata/storage/cas.py`, `objetos_gcs.py`, `objetos_locais.py`, `sessao.py`, `lease_rodada.py`, `outbox.py`, `persistencia_rodada.py`, `integracao/canvas.py` e `integracao/bridge.py`.

**WhatsApp Node:** `suricata/whatsapp/parear.mjs`, `auth-dir.mjs`, `sessao.mjs`, `enviar.mjs`, possivelmente `verificar.mjs`, além dos testes em `suricata/whatsapp/tests/` e `suricata/tests/*.mjs`.

**Infra/configuração:** `.env.example`, `docs/configuracao.md`, `docs/arquitetura.md`, `docs/privacidade.md`, `docs/deploy-gcp.md`, `suricata/infra/isolamento.json`, manifests e runbooks somente depois de decisões e autorização cloud.

**Testes:** adicionar suítes de tenant/consentimento/escopo/revogação/custo/migração e fixtures sintéticas A/B; preservar os testes coletivos atuais.

Nenhum desses arquivos foi modificado por este plano.

---

## 14. Perguntas que permanecem abertas

1. Qual mecanismo autorizado autentica a pessoa e quem opera o provedor?
2. O Canvas permite o uso pretendido do token e dos dados para este produto independente?
3. O número pessoal é só de configuração ou também destino? Quem controla o número do bot?
4. Como provar posse/autorização de um grupo sem tratar JID como consentimento?
5. Qual é a unidade de exclusão e quais cópias ficam em logs/backups/provedores?
6. Quem paga, qual teto por estudante e qual ação ocorre quando o teto acaba?
7. Qual política vale para mensagens já aceitas pelo WhatsApp no instante da revogação?
8. Qual revisão independente autoriza sair de DRAFT e qual evidência externa prova o isolamento?

Na ausência de resposta verificável, registrar `não verificado` e bloquear a fase dependente. Este plano não inventa APIs, escopos, recursos cloud, nomes de secrets, valores de quota ou aprovação institucional.
