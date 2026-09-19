# Plano de continuidade perfeita — Suricata WhatsApp

> **Documento executável para um agente sem histórico desta conversa.**
> Leia este arquivo junto com `README.md`, `docs/PLANO-EXTRACAO-SURICATA.md` e
> `docs/STATUS.md`. O objetivo é permitir que outro agente faça alterações,
> valide-as e conduza um deploy rastreável sem depender de memória da sessão.
>
> **Regra de honestidade:** testes locais verdes não provam build, deploy,
> entrega WhatsApp, IAM ou produção. Cada afirmação deve ter evidência atual.
>
---

## 1. Objetivo final

Entregar um repositório GitHub privado e autossuficiente para a Suricata, o bot
público de avisos coletivos no WhatsApp, separado do repositório acadêmico e do
Bot pessoal do Telegram.

O agente que trabalhar aqui deve conseguir:

1. entender o produto e seus limites sem abrir o repositório acadêmico;
2. alterar o runtime preservando os contratos existentes;
3. rodar a suíte completa em clone limpo;
4. construir uma imagem identificada por commit e digest;
5. validar um canário sem entrega;
6. atualizar o Job Suricata com read-back;
7. manter exatamente um Scheduler Suricata;
8. fazer rollback para o digest anterior conhecido;
9. parar de forma segura quando faltar credencial, autorização, ferramenta,
   evidência ou configuração.

O “pronto” só existe quando todos esses pontos estiverem comprovados, não quando
os arquivos apenas parecem organizados.

---

## 2. Contexto que não pode ser perdido

### 2.1 Os dois produtos originais

- **Bot acadêmico pessoal:** Telegram, estado privado, materiais e automações
  do titular no repositório `puc-ciencia-dados-ia`.
- **Suricata:** WhatsApp, mensagens públicas para grupos da turma, dados mínimos
  e somente as informações coletivas necessárias para alertas.

A Suricata não deve importar, montar, copiar ou compartilhar:

- `academico/`, `academico/estado/`;
- `periodos/`, `.canvas/`, capturas e materiais;
- `scripts/academico/`;
- bucket, Job, Scheduler, secret, service account ou estado do Bot Telegram;
- sessões WhatsApp, QR, `auth.json`, `.wa-auth/`, cookies, tokens, URLs
  assinadas, bancos ou logs sensíveis.

Strings que mencionam esses nomes podem existir em testes de isolamento ou
histórico documental; não removê-las sem verificar o contrato que o teste está
protegendo.

### 2.2 Contrato funcional

O fluxo principal é:

```text
Canvas público
  -> suricata/canvas.py + coleta.py
  -> candidatos e planejamento
  -> estado / lease / outbox
  -> bridge.py
  -> whatsapp/enviar.mjs + Baileys
  -> ACK do servidor
  -> marcação idempotente como enviada
```

O bot só anuncia informação coletiva útil ao grupo autorizado. Não envia notas,
faltas, atrasos, entregas individuais ou comandos acadêmicos. Não recebe
comandos do WhatsApp.

Modos existentes (após a simplificação de 2026-09-18):

- `shadow`: probe sem Canvas, estado ou entrega;
- `demo`: rodada offline com fixtures congeladas, entrega desligada;
- `rodada`: caminho canônico de produção.

Os modos `sentinela`, `grupos` e `teste-envio` foram removidos nessa
simplificação; o histórico vive no git.

### 2.3 Decisões de segurança

- `SURICATA_ENTREGA=desligada` em teste e canário.
- `SURICATA_ENTREGA=ligada` somente em corte explicitamente autorizado.
- O bloqueio de 21:00 BRT ocorre antes de reivindicar pendências e antes da
  ponte WhatsApp.
- Nenhum evento é considerado enviado sem ACK válido associado ao
  `message_id`.
- Lease, fencing, CAS e outbox devem continuar fail-closed.
- A sessão WhatsApp fica fora do clone e da imagem.
- O destino real nunca deve ser inventado a partir de documentação antiga;
  confirmar por read-back e, para mudança, por autorização própria.

---

## 3. Estado verificado na criação deste plano

Data da evidência: **2026-09-17**.

### 3.1 Repositório independente

- Caminho local: `C:\GIT\suricata-whatsapp`.
- Branch atual: `migration/suricata-extraction`.
- Commit inicial: `dfb5220 feat: extract Suricata WhatsApp runtime`.
- Árvore do novo repo: limpa após o commit.
- O GitHub ainda não foi configurado para este repo.
- `AGENTS.md` é obrigatório, mas a criação foi bloqueada pelo mecanismo de
  proteção de arquivos de instrução mesmo após aprovação explícita; não tentar
  contornar por `terminal`, script, symlink ou outro nome.

### 3.2 Conteúdo extraído

- Allowlist original: 103 arquivos Suricata versionados.
- Estrutura adicional criada: `src/`, `tests/`, `whatsapp/` e `deploy/`, com
  READMEs de fronteira.
- Documentação criada: produto, arquitetura, configuração, operação,
  segurança, deploy, troubleshooting, migração e status.
- Publicador: `deploy/publicar_agenda.py`, com destino único vindo de
  `SURICATA_ESTADO_URI`.
- Plano integral de extração: `docs/PLANO-EXTRACAO-SURICATA.md`.
- Inventário: o documento detalhado `INVENTARIO-EXTRACAO-SURICATA.md` ficou no repo acadêmico; este clone usa o índice e a árvore versionada atuais como fonte de inventário.

### 3.3 Gates já executados

No novo repo, com `npm ci` em `suricata/whatsapp`:

```text
pytest: 279 passed, 80 subtests passed
node --test: 39 passed
compileall: passou
python -m suricata --mode shadow: {"mode":"shadow","status":"ok","adapter":"none"}
varredura de caminhos proibidos: 0
varredura de sessão/segredo: 0
```

O mesmo baseline no repo acadêmico também confirmou `279 passed, 80 subtests
passed`. A árvore acadêmica estava suja antes da migração e deve permanecer
intocada até uma etapa de limpeza explicitamente autorizada.

### 3.4 Infraestrutura observada, sem afirmar que veio deste repo

Read-back somente leitura confirmou:

- projeto GCP Suricata ativo: `suricata-college-20260913`;
- região: `southamerica-east1`;
- Cloud Run Job: `suricata-rodada`, uma task, `maxRetries=1`;
- Scheduler: `suricata-rodada-10min`, `ENABLED`, `*/10 * * * *`, timezone
  `America/Sao_Paulo`;
- bucket de estado Suricata existente;
- service account Suricata existente;
- imagem atualmente observada por digest
  `sha256:9622db22436d366a2b1b6224479eb5b3b6c5a66da4f5a8fe5da468216de763c3`;
- últimas execuções observadas concluídas com sucesso;
- última rodada observada coletou 10 ofertas e 36 atividades;
- nessa última rodada, `eventos=[]` e contadores de entrega zerados: isso não
  prova entrega WhatsApp.

IAM least-privilege, origem independente da imagem e entrega real no grupo
continuam **não verificados**.

---

## 4. Protocolo obrigatório de retomada

Executar da raiz do novo repo:

```bash
cd /c/GIT/suricata-whatsapp
git status --short --branch
git log --oneline -10
```

Depois:

1. ler este documento, `README.md`, `docs/PLANO-EXTRACAO-SURICATA.md`,
   `docs/STATUS.md`, `docs/CONFIGURATION.md` e `docs/OPERATIONS.md`;
2. conferir o primeiro item ainda pendente na seção 10;
3. verificar os arquivos e a evidência daquele item;
4. não repetir uma etapa comprovadamente concluída;
5. se a árvore, GitHub ou GCP divergirem do texto, atualizar primeiro o status;
6. nunca interpretar texto histórico como read-back atual;
7. em dúvida, registrar `BLOQUEIO`, `EVIDÊNCIA` e `AÇÃO SEGURA POSSÍVEL`.

### Formato de registro

```text
DATA:
ETAPA:
AÇÃO:
EVIDÊNCIA:
RESULTADO: passou | falhou | bloqueado | não verificado
PRÓXIMO PASSO:
```

---

## 5. Ordem de execução para chegar ao “sim”

### Fase A — Tornar o repo autoexplicativo

1. Criar o `AGENTS.md` através do mecanismo autorizado de proteção de arquivos.
   O conteúdo deve reforçar escopo Suricata-only, leitura inicial, gates,
   segredos externos, deploy controlado e rollback.
2. Conferir que o README aponta para `AGENTS.md`, plano mestre, status e
   quickstart.
3. Transformar `docs/PLANO-SURICATA-WHATSAPP.md` em referência histórica segura
   ou substituir referências ao Bot pessoal por links válidos deste repo. Não
   deixar §R mandando executar `scripts/academico` nem consultar um arquivo
   ausente como se fosse requisito deste repo.
4. Remover do plano independente JIDs, nomes de destino, IDs e snapshots que
   não sejam necessários para o contrato; manter valores reais somente no
   ambiente autorizado.
5. Atualizar `docs/STATUS.md` com o estado real e commit que o produziu.
6. Rodar a varredura:

```bash
rg -n 'academico|periodos|\.canvas|scripts\.academico|telegram-|puc-bot-|auth\.json|\.wa-auth|Bearer|eyJ' .
```

Classificar cada achado antes de corrigir. Ocorrência em teste de isolamento ou
histórico pode ser legítima; ocorrência no runtime ou configuração executável é
bloqueadora.

**Aceite A:** um agente sem esta conversa consegue saber o que ler, o que não
pode tocar e qual é o próximo passo sem inventar contexto.

### Fase B — Revalidar o clone independente

1. Criar clone local limpo a partir do commit/branch de migração.
2. Instalar Node com `npm ci --prefix suricata/whatsapp --ignore-scripts`.
3. Executar:

```bash
python -m compileall -q suricata
python -m pytest -q
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
python -m suricata --mode shadow
python deploy/publicar_agenda.py --arquivo <fixture-temporaria> --validar
```

4. Confirmar que a fixture de agenda é temporária, sintética e não contém
   destino real, token, JID real ou dado pessoal.
5. Verificar que `git diff --check` e a varredura de segredos passam.

**Aceite B:** clone limpo reproduz `279` testes Python e `39` testes Node, sem
acesso a dados fora do repo.

### Fase C — GitHub privado e revisão

1. Confirmar `gh auth status`; não pedir nem imprimir token.
2. Criar o repositório privado com nome decidido pelo titular, sem reutilizar o
   repo `whatsapp-bot` público e sem alterar o repo acadêmico.
3. Adicionar remote e publicar a branch de migração.
4. Abrir PR para `main` com:
   - escopo da allowlist;
   - prova dos testes;
   - lista de exclusões;
   - limitações Docker/GCP;
   - plano de rollback.
5. Rodar CI e revisar se os paths disparadores cobrem a raiz, `suricata/`,
   `deploy/`, docs e workflow.
6. Usar revisão automatizada; corrigir achados; somente depois fazer merge
   squash.
7. Clonar a `main` resultante e repetir a Fase B.

**Aceite C:** URL do repo privado, PR, revisão, CI verde e clone de `main`
reproduzível. Não confundir um commit local com publicação.

### Fase D — Build rastreável

O Docker local não estava instalado nesta sessão. Usar uma destas rotas,
registrando qual foi usada:

- Docker/BuildKit disponível no runner ou máquina autorizada; ou
- Cloud Build no projeto Suricata, após autorização explícita.

Antes do build:

```bash
git rev-parse HEAD
git status --short
```

Build:

```bash
gcloud builds submit . \
  --project=<projeto-suricata-confirmado> \
  --tag=<artifact-registry-suricata-confirmado>/suricata:<commit-curto>
```

Não preencher projeto, registry ou digest por memória: obter por read-back.
Depois do build, confirmar:

- status `SUCCESS`;
- imagem contém somente artefatos esperados;
- nenhum `auth.json`, `.wa-auth`, QR, token ou banco;
- digest completo registrado em `docs/STATUS.md`;
- tamanho dentro do limite aceito;
- commit e digest são associados.

**Aceite D:** imagem por digest, origem rastreável e inspeção sem segredo.

### Fase E — Canário sem entrega

1. Fazer read-back de projeto, região, Jobs, Scheduler, bucket e service
   account.
2. Confirmar que o canário tem estado separado e não aponta para destino real.
3. Configurar `SURICATA_ENTREGA=desligada` e `maxRetries=0` no canário.
4. Executar somente o Job canário autorizado, nunca o envio real.
5. Ler execução, logs sanitizados e relatório de estado.
6. Exigir zero eventos enviados, zero ACK de entrega e ausência de secrets ou
   destinos pessoais.
7. Se qualquer valor divergir do plano, parar e corrigir o registro.

**Aceite E:** canário `Succeeded`, relatório sanitizado, zero entrega e
read-back da imagem/digest/configuração.

### Fase F — Corte controlado

Esta fase exige autorização explícita separada. Antes dela:

- CI verde;
- clone limpo verde;
- imagem por digest;
- canário aprovado;
- rollback preparado;
- IAM revisado ou marcado como bloqueio;
- destino confirmado pelo procedimento autorizado;
- sessão WhatsApp externa existente e não copiada;
- exatamente um Scheduler Suricata;
- ausência de recursos Telegram/acadêmicos no alvo.

Procedimento:

1. registrar digest anterior;
2. atualizar somente o Job Suricata para o digest novo;
3. manter o Scheduler único, sem criar outro;
4. fazer read-back de imagem, args, env, timeout, retries e service account;
5. observar uma execução sem assumir que `Succeeded` significa mensagem;
6. só ligar entrega quando o gate humano estiver satisfeito;
7. observar logs e relatório sem expor payload, token, JID ou sessão;
8. registrar resultado e janela de observação.

**Aceite F:** Job aponta para o digest novo, Scheduler único permanece correto,
configuração confere e a observação pós-corte não encontrou regressão.

### Fase G — Limpeza do repo acadêmico

Somente depois de C, D, E e F concluídas:

1. criar branch própria no repo acadêmico;
2. remover apenas o código/documentação Suricata explicitamente inventariado;
3. preservar todo `academico/`, `periodos/`, `.canvas/`, scripts acadêmicos,
   estado pessoal e alterações de outros agentes;
4. rodar a suíte acadêmica afetada;
5. abrir PR separado e revisar diff por allowlist;
6. nunca usar `git clean`, `git reset --hard`, `git restore` ou `git add .`.

**Aceite G:** repo acadêmico continua funcional e a Suricata só existe no repo
independente, com histórico e rollback documentados.

---

## 6. Procedimento de alteração futura

Quando o titular pedir “altere X e dê deploy”:

1. localizar o contrato e os usos com `search_files` antes de editar;
2. explicar, no PR, quais invariantes podem ser afetadas;
3. escrever/ajustar teste antes do código quando houver mudança comportamental;
4. fazer a menor alteração possível;
5. rodar a matriz da Fase B;
6. executar revisão de segurança e acoplamento;
7. publicar branch e abrir PR;
8. aguardar CI/revisão automatizada;
9. construir nova imagem por digest;
10. executar canário desligado;
11. pedir autorização somente para o efeito externo específico;
12. fazer deploy e read-back;
13. observar e registrar rollback possível.

Se o pedido envolver envio real, pareamento, troca de sessão, alteração de IAM,
Scheduler, Job, Secret Manager ou custo de nuvem, isso é um gate separado. Não
considerar “dar deploy” autorização implícita para todas essas ações.

---

## 7. Matriz de decisão rápida

| Situação | Ação |
|---|---|
| Testes verdes, Docker indisponível | Pode revisar código; não declarar imagem pronta |
| CI verde, sem digest | Não fazer corte |
| Digest novo, sem canário | Não ligar entrega |
| Job `Succeeded`, sem `sent`/ACK | Declarar execução, não entrega |
| Sessão caída | Handoff humano; não pedir segredo no chat |
| JID/destino divergente | Parar; confirmar por procedimento autorizado |
| IAM desconhecido | Marcar não verificado; não ampliar permissões |
| Segundo Scheduler encontrado | Parar e reconciliar antes de qualquer deploy |
| Arquivo acadêmico apareceu no clone | Parar, remover da origem da extração e repetir varredura |
| `AGENTS.md` bloqueado | Não contornar; registrar bloqueio e continuar somente tarefas não dependentes |

---

## 8. Critérios de conclusão definitiva

Só marcar este plano como concluído quando houver evidência anexada para todos:

- [ ] `AGENTS.md` presente e legível no GitHub;
- [ ] README e documentação não dependem da conversa original;
- [ ] plano histórico não induz comandos do Bot pessoal;
- [ ] repo privado publicado e clone de `main` validado;
- [ ] CI verde em PR;
- [ ] suíte Python/Node e shadow verdes no clone limpo;
- [ ] imagem construída por commit e digest;
- [ ] canário sem entrega aprovado;
- [ ] IAM least-privilege verificado ou bloqueio formal aceito;
- [ ] Job de produção atualizado por read-back;
- [ ] exatamente um Scheduler ativo;
- [ ] observação pós-corte concluída;
- [ ] rollback reproduzível/documentado;
- [ ] Suricata removida do repo acadêmico somente após todos os gates;
- [ ] nenhum segredo, sessão, QR, dado acadêmico ou estado pessoal no Git;
- [ ] status final contém URLs/SHAs/digests não sensíveis e limitações honestas.

Até todos os itens estarem marcados, a resposta correta para “vai funcionar
exatamente igual?” é: **ainda não comprovado**.
