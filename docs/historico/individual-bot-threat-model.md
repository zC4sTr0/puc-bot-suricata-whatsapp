# Modelo de ameaças e privacidade — bot individual por estudante

> **DRAFT / NÃO IMPLEMENTADO.** Este documento é uma análise de viabilidade e
> requisitos de segurança para uma possível evolução. Não descreve uma
> capacidade disponível, não concede autorização de acesso e não é política
> institucional ou parecer jurídico.
>
> **Data da análise:** 2026-09-19
> **Escopo:** autenticação/leitura Canvas, configuração de destinos, estado,
> outbox, lease/CAS, ponte WhatsApp/Baileys e testes existentes.

## 1. Veredito curto

O repositório atual sustenta um **modelo coletivo**: lê dados tratados como
coletivos do Canvas e prepara avisos para destinos de grupo. Ele não implementa
identidade de estudante, consentimento, seleção pessoal de cursos, destino
privado por pessoa, revogação ou exclusão por pessoa. Portanto, **não é viável
ativar um bot individual apenas adicionando JIDs, tokens ou uma lista de
estudantes**.

A evolução só deve avançar depois de um desenho de identidade, autorização,
isolamento de tenant/estudante, ciclo de vida de dados e resposta a incidentes,
seguido de implementação mínima e validação adversarial. Os controles atuais
reduzem alguns riscos de transporte e concorrência, mas não constituem uma
garantia de privacidade individual.

## 2. Evidência lida e limites da evidência

| Área | Evidência observada | O que ela prova | O que ela não prova |
|---|---|---|---|
| Canvas | `suricata/integracao/canvas.py`; `suricata/tests/test_canvas.py` | Origem HTTPS em allowlist, somente GET, DTOs que descartam campos não modelados, erros sanitizados | Que todo conteúdo retornado seja público, correto ou permitido para republicação; não há autorização individual |
| Destinos/configuração | `suricata/rodada/config.py`; `docs/configuracao.md` | JIDs são validados e vêm da configuração; ambiente/arquivo são fail-closed em vários erros | Que o operador que configura um JID está autorizado; não há vínculo estudante→destino |
| Outbox | `suricata/storage/outbox.py`; `suricata/tests/test_outbox.py` | Estados, expiração, idempotência, fencing por `attempt_id` e exigência de ACK | Que conteúdo, JID, `event_id` ou estado sejam isolados entre estudantes |
| Estado/CAS | `suricata/storage/cas.py`; `suricata/storage/lease_rodada.py`; `test_storage_cas_revalidation.py` | Revalidação de geração, escrita condicional e lease para concorrência | Que IAM, bucket, retenção ou exclusão estejam corretos em uma nuvem real |
| Ponte WhatsApp | `suricata/integracao/bridge.py`; `suricata/whatsapp/enviar.mjs` | Subprocesso com ambiente mínimo, sessão fora do clone, validação de lote e ACK associado ao `message_id` | Que o destino esteja sob controle do estudante, que o WhatsApp preserve confidencialidade ou que um ACK prove leitura |
| Pareamento | `suricata/whatsapp/parear.mjs`; `auth-dir.mjs`; testes Node | Pareamento é local/interativo, diretório dentro do repo é rejeitado, logs são reduzidos | Que logout/revogação por estudante exista; a sessão atual é uma sessão operacional da instância |
| Escopo declarado | `AGENTS.md`, `docs/privacidade.md`, `docs/interno/CONTRACTS.md`, `suricata/infra/isolamento.json` | O produto atual é coletivo, não oficial, e não deve usar notas/submissões; há separação nominal do produto | Que a separação nominal substitua IAM, isolamento de dados ou aprovação institucional |

A árvore já contém alterações não relacionadas e não foi modificada nesta
análise, salvo o arquivo deste DRAFT.

## 3. Ativos e classificação

| Ativo | Confidencialidade | Integridade | Disponibilidade | Impacto se exposto/alterado |
|---|---:|---:|---:|---|
| Identidade do estudante e vínculo com cursos | alta | alta | média | perfil acadêmico, exposição de matrícula e direcionamento indevido |
| Consentimento, escopo escolhido e preferências | alta | alta | média | envio sem base autorizadora ou perda de controle pelo titular |
| Token/credencial Canvas | crítica | crítica | média | acesso indevido à conta ou coleta fora do escopo |
| Sessão WhatsApp, QR e credenciais Baileys | crítica | crítica | alta | tomada da conta, mensagens em nome do usuário e logout |
| JID/telefone e destino privado | alta | alta | média | identificação, spam, envio para pessoa errada |
| Conteúdo de atividade, link, disciplina e prazo | média/alta | alta | alta | inferência de rotina acadêmica e desinformação |
| Outbox, memória, dead-letter, lease e logs | alta | alta | alta | replay, duplicata, investigação contaminada e vazamento de conteúdo |
| Configuração, chaves de namespace e IAM | alta | crítica | alta | mistura entre estudantes, exfiltração ou envio em massa |
| ACK e histórico de entrega | média/alta | alta | alta | falsa afirmação de envio/leitura e retries perigosos |
| Código, imagens e fixtures | média | alta | média | supply-chain, backdoor ou publicação acidental de dados reais |

## 4. Fronteiras e atores

- **Estudante titular:** pode consentir, escolher escopo, receber mensagens e
  revogar; não deve conseguir ler dados de outro estudante.
- **Operador/mantenedor:** administra o serviço, mas deve ter acesso mínimo e
  auditável; não deve usar a arquitetura para vigilância ou enriquecimento de
  perfil.
- **Administrador Canvas:** pode controlar a origem e seus próprios registros;
  o bot não deve presumir autorização além do token e dos termos aplicáveis.
- **Administrador WhatsApp/cloud:** pode ter poder técnico amplo; esse poder é
  um risco, não uma justificativa para coleta irrestrita.
- **Atacante externo:** tenta obter token, sessão, JID, conteúdo ou provocar
  envio/replay.
- **Estudante malicioso ou conta comprometida:** tenta cadastrar destino de
  terceiro, ampliar cursos, exfiltrar conteúdo ou transformar o bot em spam.
- **Fonte externa comprometida:** Canvas, payload, link ou biblioteca pode
  carregar conteúdo enganoso, XSS no consumidor ou instruções para o operador.

## 5. Ameaças e abusos prioritários

| ID | Ameaça/abuso | Caminho plausível | Risco atual |
|---|---|---|---|
| IND-01 | Mistura entre estudantes | namespace compartilhado, chave previsível, consulta sem `student_id` ou outbox comum | **crítico**; não há modelo individual para avaliar |
| IND-02 | Cadastro de JID de terceiro | aceitar telefone informado sem prova de posse/consentimento | **alto**; configuração atual valida formato, não titularidade |
| IND-03 | Ampliação de escopo Canvas | token com cursos além dos escolhidos ou rota futura de dados pessoais | **alto**; cliente atual modela dados coletivos, mas não aplica escopo por estudante |
| IND-04 | Reuso após revogação | outbox pendente, retry ou lease continuar válido após cancelamento | **alto**; expiração existe, revogação por pessoa não existe |
| IND-05 | Tomada da sessão WhatsApp | sessão/QR vazado, bucket/IAM amplo ou auth materializado indevidamente | **crítico**; sessão fica fora do Git, mas não há prova de IAM/retensão reais |
| IND-06 | Envio ao destino errado | configuração sobreposta por env, namespace incorreto, erro de associação | **alto**; há validação de JID e namespace, não autorização semântica |
| IND-07 | Vazamento por logs/erros | payload, texto, JID, URL assinada ou identificador em stdout/stderr/dead-letter | **alto**; há sanitização testada, mas não cobertura de todos os logs/provedores |
| IND-08 | Replay/duplicata | crash entre envio e persistência, retry fora do fencing, `message_id` não único | **médio/alto**; outbox e ACK reduzem o risco, não o eliminam em integrações reais |
| IND-09 | Falso sucesso | ACK técnico interpretado como entrega/leitura ou ACK forjado | **alto**; contrato exige ACK compatível, mas ACK não prova leitura |
| IND-10 | Abuso de custo/rate | cada estudante gerar consultas Canvas, retries ou mensagens sem teto | **alto**; não foi encontrado limite por estudante/tenant |
| IND-11 | Conteúdo malicioso do Canvas | HTML, link ou texto usado para phishing, tracking ou instrução ao operador | **médio/alto**; HTML é limpo no adapter, mas links/conteúdo ainda exigem política |
| IND-12 | Exclusão ou investigação impossível | apagar estado antes de preservar evidência mínima, ou retenção indefinida | **alto**; política de retenção individual não existe |
| IND-13 | Supply-chain/operador privilegiado | dependência Node, imagem ou administrador acessa sessões/conteúdo | **alto**; testes locais não provam build, IAM ou imagem implantada |
| IND-14 | Correlação indevida | combinar JID, curso, horários e mensagens para inferir rotina | **alto**; minimização atual é coletiva, não uma garantia contra correlação |

### Abusos que devem ser explicitamente proibidos

- monitorar presença, desempenho, notas, tentativas, submissões ou respostas;
- enviar mensagem para familiar, professor ou terceiro sem autorização verificável;
- usar o bot para cobrança, constrangimento, vigilância ou decisão acadêmica;
- aceitar comandos recebidos no WhatsApp como autorização de acesso ao Canvas;
- cadastrar uma sessão ou destino para vários estudantes sem isolamento e
  consentimento individual;
- transformar links de atividade em rastreamento, perfil comercial ou ranking;
- continuar enviando depois de logout, revogação, expiração do consentimento ou
  pedido de exclusão.

## 6. Isolamento obrigatório por estudante

A unidade mínima de isolamento deve ser um **tenant de estudante**, não apenas um
campo adicional em um JSON compartilhado. O desenho ainda não existe; os itens
abaixo são gates de arquitetura:

1. **Identificador interno não derivado do telefone:** gerar um identificador
   opaco e estável. Separar identidade/autorização do conteúdo acadêmico e do
   JID.
2. **Namespace físico e lógico:** cada estudante deve possuir prefixo/objeto
   ou partição verificável para consentimento, escopo, outbox, memória, sessão,
   auditoria e limites. Uma leitura deve exigir o tenant no contexto, não
   confiar em um caminho recebido do usuário.
3. **Chave de autorização no servidor:** o worker não pode escolher livremente
   `student_id`, bucket, prefixo, JID ou token. Resolver a associação a partir
   de uma política assinada e validada, com deny-by-default.
4. **Sessão WhatsApp explicitamente modelada:** decidir se o titular conecta a
   própria conta ou se existe uma conta de serviço. Não tratar a sessão atual
   da instância como se fosse automaticamente uma sessão individual.
5. **Outbox por tenant e por destino:** `event_id`/`message_id` devem ter
   escopo e unicidade documentados; transições e retries devem verificar
   estudante, destino autorizado e versão de consentimento.
6. **CAS/lease por namespace:** leases não podem bloquear ou autorizar outro
   estudante. Um conflito deve negar a operação, sem fallback para namespace
   global.
7. **Testes de não-vazamento:** fixtures com A/B devem provar que cada API,
   log, consulta, retry, erro, exportação e dead-letter de A não contém dados de
   B. Testar também `student_id` adulterado, path traversal, troca de JID e
   replay de token de revogado.
8. **Operação sem acesso lateral:** IAM, service accounts, Secret Manager,
   bucket e observabilidade devem impedir leitura cruzada; revisão de código
   não substitui essa prova.

Até esses pontos serem implementados e testados, não há base para alegar
isolamento por estudante.

## 7. Minimização, finalidade e retenção

### Dados permitidos no MVP individual (proposta)

- identificador opaco do tenant;
- cursos explicitamente escolhidos e seus IDs;
- fatos mínimos necessários: título, tipo, prazo e URL canônica permitida;
- preferências de horário/canal estritamente necessárias;
- estado técnico mínimo: `event_id`, hash/versão do conteúdo, tentativa,
  ACK, timestamps e motivo sanitizado;
- registro de consentimento/revogação com versão da política, não o texto
  integral de conversas privadas.

### Dados que devem ficar fora

Notas, frequência, presença, submissões, tentativas, respostas, mensagens
privadas, lista de contatos, histórico completo do Canvas, conteúdo de QR,
tokens em logs, texto de erro bruto, payloads desnecessários, cópias integrais
de páginas e qualquer atributo usado apenas para curiosidade ou perfil.

### Retenção a decidir antes do código

Definir, por tipo de dado, prazo curto e finalidade: sessão, outbox pendente,
mensagem enviada, erro, auditoria de consentimento e backup. A exclusão deve
ser verificável e considerar caches, objetos versionados, temporários, logs,
backups e dead-letter. Preservar somente evidência mínima necessária para um
incidente, com acesso restrito e prazo definido. Hoje o repositório não fixa
esses prazos nem prova exclusão em todos os provedores.

## 8. Autorização, consentimento e revogação

### Gates de autorização

- consentimento explícito, informado, granular por finalidade e curso;
- prova de que a pessoa controla o destino WhatsApp (não apenas um JID digitado);
- autorização separada para leitura do Canvas e para envio ao WhatsApp;
- escopo, finalidade, versão da política e data de expiração persistidos;
- nenhum consentimento inferido de estar em um grupo ou de possuir conta Canvas;
- reautorização quando mudar escopo, finalidade, provedor ou versão relevante.

O serviço deve recusar a execução se consentimento, identidade, escopo,
destino, sessão ou política estiverem ausentes, expirados, ambíguos ou
incompatíveis.

### Revogação obrigatória

A revogação deve ser uma transição atômica e observável: marcar o tenant como
revogado, impedir novas consultas e claims, cancelar/expirar pendências,
invalidar tokens/sessão autorizada quando aplicável, interromper retries,
confirmar read-back e registrar apenas o mínimo para auditoria. Um `logout`
do WhatsApp, um erro do Canvas ou uma exclusão de objeto **não equivalem
automaticamente** à revogação completa; esse mapeamento deve ser especificado.

Devem existir testes de revogação durante cada estado (`pending`, `in_flight`,
`sent`), durante crash/restart e em corrida com CAS/lease. O comportamento de
uma mensagem já aceita pelo WhatsApp também deve ser declarado: não é possível
prometer apagá-la do aparelho do destinatário apenas removendo o outbox.

## 9. Rate limits, limites de custo e segurança operacional

Antes de uma implementação, fixar limites fechados e observáveis, por
estudante, tenant, token, curso, destino e serviço:

- máximo de estudantes ativos, cursos por estudante e destinos por estudante;
- máximo de requisições Canvas por janela e concorrência por token;
- máximo de mensagens, bytes, retries e tempo de ponte por estudante/dia;
- teto global de custo e orçamento de Cloud Run, GCS, logs e egress;
- tamanho máximo de texto, idade máxima de evento e TTL de outbox;
- circuit breaker para 401/403/429, falhas repetidas, logout e anomalia de
  volume; não fazer retry infinito;
- bloqueio automático/quarentena em mudança brusca de JIDs, cursos, volume,
  custo ou taxa de erro;
- alertas que não revelem conteúdo, telefone ou token.

Os valores atuais de timeout, lease e expiração do outbox são controles
operacionais existentes, não substitutos de limites de abuso por estudante.

## 10. Incidente: detectar, conter, recuperar, verificar

1. **Detectar:** alertar por erro de autenticação, leitura cruzada, JID novo,
   volume/custo anômalo, log com padrão secreto, ACK inconsistente, mudança de
   IAM ou sessão em local inesperado.
2. **Conter:** desligar a entrega (`SURICATA_ENTREGA`), congelar claims e
   retries do tenant afetado, revogar token/sessão, preservar evidência mínima
   e separar o tenant sem parar investigações independentes.
3. **Erradicar:** remover segredo comprometido, revisar IAM/prefixos, corrigir
   causa, invalidar caches/temporários e bloquear o caminho de reentrada.
4. **Comunicar:** identificar o alcance provável sem expor dados; notificar
   titular, operador, provedor e responsáveis institucionais conforme obrigação
   aplicável. Não declarar ausência de impacto sem evidência.
5. **Recuperar:** restaurar somente a partir de artefato conhecido, com escopo
   explícito, canário sem envio e nova autorização; não reprocessar outbox
   automaticamente sem verificar revogação e idempotência.
6. **Verificar:** read-back de IAM/namespace/estado, varredura de logs e
   backups, teste de não-vazamento A/B, reconciliação de mensagens e registro
   append-only do incidente, decisões e lacunas.

O runbook atual orienta sanitização e parada, mas não contém ainda um fluxo
individual completo, contatos, SLA, matriz de severidade ou procedimento de
notificação.

## 11. Gates obrigatórios antes de implementação

Nenhum código de bot individual deve ser ativado antes de todos os gates abaixo
terem evidência revisável:

- [ ] decisão de produto e base legal/institucional documentadas; o serviço
      independente não é apresentado como oficial;
- [ ] modelo de ameaça revisado por segurança e privacidade, incluindo abuso
      interno e comprometimento de provedor;
- [ ] identidade, consentimento granular, expiração, reautorização e revogação
      implementados como estados fail-closed;
- [ ] esquema de tenant, chaves, namespaces e IAM testados contra leitura
      cruzada e path/key confusion;
- [ ] destino WhatsApp verificado por posse/consentimento e separado da
      identidade acadêmica sempre que possível;
- [ ] token Canvas com escopo mínimo, allowlist de rotas e cursos, e prova de
      que nenhum dado individual é coletado;
- [ ] outbox, memória, lease/CAS, sessão, logs, backups e dead-letter com
      retenção/exclusão por tenant definida e testada;
- [ ] rate/cost limits, circuit breakers, quotas e alertas testados com abuso;
- [ ] matriz de testes negativos: A/B, revogado, expirado, corrida, crash,
      retry, ACK falso, JID trocado, token errado, payload malicioso e 429;
- [ ] revisão da ponte e dependências; build reproduzível, imagem por digest,
      segredo fora da imagem e IAM read-back confirmado;
- [ ] canário shadow sem entrega, depois canário limitado, com rollback
      exercitado; promoção condicionada a métricas de vazamento, erro,
      duplicata, custo e volume;
- [ ] runbook de incidente, responsáveis, contatos e procedimento de parada
      testados em simulação;
- [ ] aviso de privacidade e UX de consentimento publicados, em linguagem
      clara, sem prometer entrega, leitura ou exclusão impossível;
- [ ] aprovação explícita para sair do DRAFT e registro de que a capacidade
      individual foi realmente implementada — não inferida de configuração.

## 12. Perguntas em aberto (não assumir respostas)

1. Quem é o responsável jurídico/operacional pelo serviço e qual autorização
   institucional existe para acessar o Canvas?
2. O estudante autoriza uma conta WhatsApp própria ou uma conta de serviço?
   Quem controla a sessão e pode revogá-la?
3. Qual mecanismo de autenticação liga uma pessoa a seu tenant sem armazenar
   mais identidade do que o necessário?
4. O Canvas permite e autoriza o uso pretendido de token, cursos e conteúdo?
   Quais campos são realmente públicos no contexto de cada curso?
5. Como comprovar posse do destino privado sem armazenar telefone em claro?
6. Qual é a unidade de exclusão: mensagem, curso, tenant, sessão, backup e
   logs? Qual prazo e qual evidência de conclusão?
7. Quais provedores mantêm cópias, logs, metadados ou backups e por quanto
   tempo?
8. O que acontece com uma mensagem já aceita pelo WhatsApp após revogação?
9. Quais quotas e orçamento são aceitáveis por estudante e globalmente?
10. Quem pode acessar suporte, IAM, sessão, estado e auditoria, e como esse
    acesso será justificado e registrado?
11. Como tratar estudantes menores de idade, procurações, contas compartilhadas
    e pedidos de titular?
12. Que conteúdo pode conter link, nome de disciplina ou prazo sem permitir
    inferência indevida sobre a vida acadêmica?
13. Qual é a política para indisponibilidade parcial do Canvas: silenciar,
    alertar ou pedir confirmação direta ao estudante?
14. Qual evidência independente será exigida para declarar isolamento, exclusão
    e revogação efetivos em produção?

## 13. Conclusão

O código atual oferece bons pontos de partida técnicos — allowlist do Canvas,
DTOs minimizados, ambiente mínimo no subprocesso, sessão fora do clone,
namespace de estado, CAS/lease, outbox idempotente, ACK validado e testes de
sanitização. Esses pontos são **controles parciais**, não garantias de que um
bot individual seja privado ou autorizado.

A decisão segura neste estado é manter o produto coletivo e este documento como
DRAFT. A implementação individual somente pode ser considerada depois de
responder as perguntas em aberto e fechar todos os gates com artefatos,
testes negativos e verificação externa dos recursos reais.
