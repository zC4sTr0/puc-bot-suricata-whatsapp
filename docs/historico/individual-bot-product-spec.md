# Produto futuro: bot individual por estudante

> **DRAFT / NÃO IMPLEMENTADO / NÃO É PROMESSA DE LANÇAMENTO**
>
> Este documento descreve uma hipótese de produto para uma evolução futura do
> PUC Bot da Suricata. Não altera o comportamento atual, não autoriza acesso a
> contas ou cursos e não representa a PUC Minas. O projeto continua sendo
> independente e não oficial; prazos, regras e comunicados devem ser
> confirmados no Canvas e nos canais oficiais da disciplina.

## 1. Finalidade e limites

O produto futuro permitiria que uma pessoa estudante recebesse, em um destino
privado sob seu controle, avisos acadêmicos relativos apenas aos cursos e às
fontes que ela escolheu. A finalidade seria organizar avisos informativos,
não substituir o Canvas nem criar um assistente acadêmico com acesso ao perfil
individual.

O produto **não** deveria:

- acessar, expor ou inferir notas, frequência, presença, submissões,
  tentativas, respostas, feedback privado ou desempenho;
- fazer ações de estudante no Canvas, como entregar atividade, iniciar quiz,
  responder, enviar mensagem ou alterar configurações;
- se apresentar como serviço oficial, integração institucional aprovada ou
  canal da universidade;
- transformar uma falha de coleta em afirmação de que não há atividade;
- usar a seleção de cursos como autorização para acessar dados individuais;
- compartilhar avisos de uma pessoa com outra pessoa ou grupo sem autorização
  separada.

O modelo atual permanece coletivo: uma instância atende destino autorizado de
turma/grupo, consulta dados coletivos e não oferece consentimento, seleção
individual, destino privado ou revogação por estudante.

## 1.1 Decisão de direção do produto

A direção escolhida para o MVP futuro é **um bot operado por estudante**. Cada
estudante deverá configurar e controlar sua própria instância, sem compartilhar
credenciais, sessão ou estado com outras pessoas. A hipótese operacional é:

- conta/projeto cloud do próprio estudante, ou uma conta explicitamente
  delegada a ele;
- token Canvas do próprio estudante, usado somente para o escopo autorizado do
  perfil dele;
- número pessoal do estudante para a configuração, confirmação e suporte do
  acesso;
- número/chip separado para a conta WhatsApp do bot, pareado durante a
  configuração inicial;
- seleção dos cursos e dos grupos em que o estudante tem autorização para
  colocar o bot;
- estado, secrets, sessão WhatsApp, custos e revogação pertencentes àquela
  instância, com isolamento verificável.

“Colocar o bot no grupo que quiser” significa apenas grupos que o estudante
administra ou para os quais tem autorização. Não significa enviar para terceiros
sem consentimento, contornar controles do WhatsApp ou tratar o formato de um JID
como prova de autorização. Esta decisão orienta a documentação e o próximo
desenho, mas **não está implementada**.

## 2. Personas

### 2.1 Estudante titular

Pessoa que escolhe aderir, confirma a identidade do próprio destino privado,
seleciona cursos e pode consultar, pausar, alterar ou revogar o serviço. É a
titular das escolhas de escopo do produto, mas continua responsável por
confirmar o aviso na fonte oficial.

### 2.2 Operador de suporte

Pessoa autorizada a atender dúvidas operacionais, explicar limites, verificar
estado sanitizado e encaminhar incidentes. Não deve visualizar conteúdo
individual desnecessário, token, sessão WhatsApp, QR, senha ou dados acadêmicos
privados.

### 2.3 Operador técnico

Pessoa responsável pela infraestrutura, disponibilidade, segurança, retenção e
custos. Acesso técnico não implica autorização para ler conteúdo acadêmico ou
alterar a seleção de cursos de uma estudante.

### 2.4 Responsável institucional (se houver)

Eventual pessoa ou área que possa avaliar o uso institucional. Sua existência,
autorização, API, parceria ou aprovação **não é presumida** nesta spec. Sem
confirmação verificável, o produto deve continuar descrito como independente e
não oficial.

## 3. Proposta de valor e jornada

### 3.1 Jornada principal

1. A estudante encontra uma descrição clara do produto e dos limites.
2. Lê a finalidade, as fontes previstas, os dados não coletados, os riscos,
   custos e a natureza não oficial.
3. Cria ou vincula uma conta do produto por um fluxo de autenticação ainda a
   definir; o produto não deve pedir credenciais neste documento nem inventar
   um método institucional.
4. Confirma o destino privado e prova que possui controle sobre ele por um
   mecanismo de confirmação ainda a definir.
5. Visualiza os cursos que a integração autorizada consegue listar, ou informa
   uma seleção por um fluxo alternativo explicitamente documentado.
6. Escolhe cursos, tipos de aviso e janelas permitidas; o padrão inicial é
   mínimo e reversível.
7. Dá consentimento específico, informado e registrável.
8. Recebe uma confirmação da configuração e uma mensagem de teste sem conteúdo
   acadêmico sensível.
9. O sistema executa rodadas de leitura, planejamento e entrega apenas para o
   escopo vigente.
10. A estudante pode consultar a origem do aviso, a data de atualização e o
    estado da coleta.
11. A estudante pausa, altera ou revoga quando quiser, com confirmação do
    efeito e prazo para cessar novas entregas.

### 3.2 Estados de uma adesão

A adesão deve ter estados observáveis e auditáveis, no mínimo:

`rascunho → aguardando_consentimento → ativa → pausada → revogada`.

Falhas de confirmação, fonte, destino ou configuração não podem promover a
adesão para `ativa`. `revogada` deve ser terminal para aquela autorização; uma
nova adesão deve começar com consentimento novo, sem reativação silenciosa.

## 4. Consentimento e controle da pessoa

O consentimento deve ser:

- **livre:** sem marcar cursos ou autorizar acesso amplo como condição para
  outra função não relacionada;
- **informado:** finalidade, fontes, categorias de dados, destino, retenção,
  custos, suporte, riscos e natureza não oficial aparecem antes da ativação;
- **específico:** cursos, tipos de fonte e destino ficam vinculados à adesão;
- **inequívoco:** uma ação afirmativa, sem checkbox pré-marcado;
- **revogável:** com caminho acessível e sem exigir justificativa;
- **comprovável:** registrar versão do texto aceito, momento, escopo e estado,
  sem guardar mais conteúdo acadêmico do que o necessário.

A tela ou fluxo de consentimento deve separar, pelo menos:

1. leitura de fontes acadêmicas;
2. preparação de avisos;
3. entrega no destino privado;
4. armazenamento operacional e retenção;
5. comunicações de suporte, se forem opcionais.

Não é suficiente dizer “aceito os termos” para autorizar acesso a qualquer
curso ou dado individual. O texto deve informar que o produto não garante que
um aviso será entregue, correto, completo ou atualizado em tempo real.

## 5. Seleção de cursos e escopo

A seleção deve ser explícita, revisável e limitada ao período de adesão:

- mostrar identificador e nome do curso apenas quando a fonte fornecer esses
  dados de modo autorizado;
- evitar selecionar todos os cursos por padrão;
- permitir ativar, pausar e remover cursos individualmente;
- registrar quando a seleção mudou e qual escopo passou a valer;
- impedir que um curso removido continue gerando avisos novos;
- tratar curso arquivado, duplicado, sem permissão ou não encontrado como
  estado de erro visível, nunca como autorização implícita;
- não inferir matrícula a partir de mensagens, grupos, nomes ou links;
- aplicar o princípio do menor privilégio à coleta e ao armazenamento.

A lista de cursos e seu significado dependem da capacidade real da integração.
A interface deve dizer quando uma seleção é apenas uma preferência local e
quando foi confirmada pela fonte.

## 6. Fontes Canvas e proveniência

O Canvas continua sendo a fonte de referência para prazos, atividades e
anúncios quando esses dados estiverem autorizadamente disponíveis. O desenho
futuro deve preservar os contratos atuais:

- leitura somente, sem ações de estudante;
- uso de dados coletivos/publicáveis no contexto autorizado;
- coleta parcial não equivale a ausência;
- origem, momento da coleta e estado da fonte acompanham cada aviso;
- agenda manual, se mantida, é complementar e identificada como anotação do
  operador, nunca como comunicado oficial;
- dados individuais não devem ser usados apenas para personalizar um texto se
  não forem necessários à finalidade declarada.

Esta spec **não inventa API institucional**, endpoint, escopo OAuth, método de
SSO, integração oficial, identificador de matrícula ou autorização de acesso.
Antes de implementação, cada fonte precisa de documentação e autorização
verificáveis, além de um caminho de falha fechado quando a capacidade não
existir.

Um aviso individual deve permitir conferir, quando disponível:

- curso e tipo de atividade;
- título mínimo necessário;
- data/hora conforme a fonte e o fuso adotado;
- link para a fonte, sem expor segredo;
- origem (Canvas ou agenda manual);
- momento da última coleta e indicação de coleta incompleta.

## 7. Destinos privados

O destino deve ser privado, confirmado e pertencente à estudante ou estar sob
seu controle demonstrável. O produto deve:

- separar identidade da pessoa, seleção de cursos e identificador técnico do
destino;
- confirmar o destino antes de qualquer mensagem acadêmica;
- não aceitar JID, telefone, e-mail ou endereço colado como prova suficiente de
  identidade;
- manter sessão, QR, token, auth e identificadores reais fora do Git, logs
  públicos, fixtures e mensagens de suporte;
- não enviar para grupo, lista ou contato compartilhado sem consentimento
  separado;
- mostrar o destino mascarado nas telas e nos relatórios;
- tratar mudança de destino como nova confirmação e possível revogação do
  destino anterior;
- usar a máquina de entrega existente: outbox, `message_id` determinístico,
  ACK válido, retry idempotente, CAS e fail-closed.

O canal de destino ainda depende de decisão de produto e de viabilidade
operacional. “Bot individual no WhatsApp” é uma hipótese; esta spec não afirma
que a plataforma, os termos de uso ou uma instituição autorizam esse desenho.

## 8. Revogação, pausa e exclusão

A estudante deve conseguir:

- pausar avisos sem apagar necessariamente a conta;
- retirar um curso sem revogar os demais;
- remover ou substituir um destino;
- revogar toda a adesão;
- solicitar exclusão dos dados associados, respeitando apenas retenções
  mínimas justificadas e informadas;
- receber confirmação do que parou, do que foi apagado e do que permanece,
  com motivo e prazo quando algo não puder ser removido imediatamente.

A revogação deve bloquear novas coletas vinculadas ao escopo revogado e novas
entregas. Itens já enviados não podem ser apagados do dispositivo ou histórico
de terceiros pelo produto; essa limitação deve ser declarada. Mensagens já em
`pending` ou `in_flight` exigem uma regra explícita para cancelamento seguro,
sem alegar exclusão de uma entrega que já saiu.

O sistema deve manter somente o registro mínimo necessário para provar a
revogação, prevenir reativação silenciosa e atender suporte. Logs devem ser
sanitizados, com retenção definida e sem payload acadêmico, token, QR, sessão,
JID real ou texto completo do aviso quando um identificador técnico bastar.

## 9. Suporte e incidentes

O suporte deve oferecer um caminho público e uma alternativa para quem não
consegue acessar o destino. A mensagem de suporte deve orientar a não enviar
senha, token, QR, sessão, captura com dados de colegas ou conteúdo privado.

Categorias mínimas:

- não recebi um aviso;
- recebi aviso de curso incorreto;
- origem ou data parece divergente;
- quero pausar, alterar ou revogar;
- destino foi trocado, perdido ou comprometido;
- suspeita de acesso indevido ou exposição de dados;
- cobrança ou custo inesperado;
- Canvas/WhatsApp indisponível.

O suporte pode consultar apenas metadados sanitizados: adesão, estado,
escopo, última coleta, erro curto e `message_id` técnico. Não deve conceder
acesso manual a curso nem reativar uma adesão sem novo consentimento. Incidente
com suspeita de exposição deve suspender entregas afetadas, preservar evidência
mínima e comunicar a pessoa por canal seguro, sem publicar dados no issue
tracker.

## 10. Custos e sustentabilidade

Antes de ativar o produto, deve existir uma estimativa por estudante e por
rodada, separando:

- execução do job e agendamento;
- armazenamento e operações de estado/outbox;
- chamadas ou limites do Canvas;
- sessão e transporte de mensagens;
- suporte, monitoramento e retenção;
- custos variáveis, franquias, impostos e contingência.

Os valores não são conhecidos nesta spec e não devem ser inventados. A
interface deve mostrar se há cobrança, quem paga, como o limite é aplicado e o
que acontece quando o orçamento acaba. O comportamento seguro diante de
estouro de custo é pausar novas rodadas/entregas e avisar a pessoa, não cobrar
silenciosamente nem degradar para um destino coletivo.

A operação deve medir, sem conteúdo desnecessário, estudantes ativos, cursos
selecionados, rodadas, falhas, mensagens planejadas e entregues, custo
estimado e solicitações de suporte. Qualquer métrica publicada deve ser
agregada e não reidentificar estudantes.

## 11. Dependências e decisões em aberto

A implementação não pode começar como se estes pontos já estivessem
resolvidos:

- base legal, responsabilidades e revisão de privacidade;
- autorização para a integração e limites reais do Canvas;
- método de autenticação e seleção de cursos;
- canal de destino privado, termos e limites da plataforma;
- política de retenção e exclusão;
- modelo de suporte e resposta a incidentes;
- orçamento e responsável pelo pagamento;
- operação, monitoramento, backup e recuperação;
- eventual participação institucional, que só pode ser afirmada com evidência
  verificável.

Cada decisão precisa de fonte, responsável, data, escopo e teste ou read-back.
Na ausência de fonte, registrar **não verificado** em vez de preencher a lacuna
com uma API ou aprovação plausível.

## 12. Critérios de aceite do produto futuro

A evolução só pode sair de DRAFT quando todos os critérios abaixo forem
comprovados em ambiente de teste e, separadamente, em uma operação autorizada:

- [ ] A documentação e a interface deixam explícito “independente e não
      oficial”; nenhuma tela sugere endosso institucional.
- [ ] Uma estudante consegue criar uma adesão sem compartilhar senha, token,
      QR ou sessão no chat ou no repositório.
- [ ] O consentimento registra finalidade, versão, momento, cursos, fontes,
      destino e retenção; não há consentimento implícito ou checkbox pré-marcado.
- [ ] O escopo inicial não seleciona todos os cursos por padrão e toda mudança
      é visível, reversível e auditável.
- [ ] A coleta acessa somente fontes e dados autorizados; testes provam que
      notas, frequência, submissões, tentativas, respostas e mensagens privadas
      não entram no aviso.
- [ ] Cada aviso mostra origem, atualização e incerteza de coleta; coleta
      parcial nunca produz “não há atividade”.
- [ ] O destino é confirmado antes do primeiro conteúdo acadêmico e fica
      isolado de grupos e de outras adesões.
- [ ] A entrega preserva `pending → in_flight → sent`, ACK, idempotência,
      CAS, lease, corte horário e fail-closed dos contratos atuais.
- [ ] Pausa, remoção de curso, troca de destino, revogação e exclusão têm
      efeitos observáveis e testes para itens pendentes/in-flight.
- [ ] Depois da revogação, nenhuma rodada cria nova coleta ou entrega do
      escopo revogado; reativação exige consentimento novo.
- [ ] O suporte funciona sem receber segredos e sem conceder acesso manual
      fora do escopo consentido.
- [ ] Logs, métricas e estado são minimizados, sanitizados, retidos por prazo
      definido e não expõem identificadores reais em documentação pública.
- [ ] Custos e limites são apresentados antes da ativação, têm orçamento
      verificável e possuem comportamento seguro quando excedidos.
- [ ] Há testes offline com fixtures sintéticas, teste adversarial de isolamento
      entre estudantes e read-back separado para autenticação, fonte, destino,
      configuração e operação real.
- [ ] Não existe afirmação de API institucional, parceria, autorização ou
      disponibilidade sem fonte verificável e aprovação correspondente.

## 13. Relação com os contratos atuais

Este rascunho complementa, mas não substitui, `README.md`,
`docs/privacidade.md`, `docs/arquitetura.md`, `docs/configuracao.md` e
`docs/interno/CONTRACTS.md`. Até uma implementação futura aprovada, os modos
`shadow`, `demo` e `rodada`, o destino coletivo atual, a configuração por
`SURICATA_*`, a ponte Python→Node, o outbox, o ACK, o CAS e o armazenamento
externo continuam sendo os únicos contratos descritos como existentes.
