# Plano de extração da Suricata para um repositório próprio

> **Objetivo:** retirar a Suricata deste repositório acadêmico e criar um
> repositório independente para o bot de WhatsApp.
>
> **Modo de execução:** um passo por vez. Depois de cada passo, atualizar o
> registro de progresso deste arquivo. Se o agente perder contexto, ele deve
> executar a seção **Retomada** e continuar no primeiro passo sem `concluído`.
>
> **Regra principal:** não alterar o comportamento do bot durante a extração.
> Primeiro separar e documentar. Melhorias de lógica ficam para depois da
> migração.

---

## 0. O que este plano está tentando fazer

Existem dois produtos no mesmo repositório:

1. **Bot Acadêmico Pessoal:** Telegram, dados privados do titular e materiais
   da PUC Minas.
2. **Suricata:** WhatsApp, mensagens públicas para grupos da turma e dados
   mínimos necessários para alertas coletivos.

O resultado final será:

- este repositório continuará sendo acadêmico;
- um novo repositório conterá todo o código e a operação da Suricata;
- o novo repositório poderá ser clonado, testado, empacotado e implantado sem
  `academico/`, `periodos/`, `.canvas/` ou `scripts/academico/`;
- a Suricata continuará usando somente dados públicos úteis ao grupo;
- nenhum segredo, sessão WhatsApp, QR code ou estado real será colocado no Git.

---

## 1. Regras que nunca podem ser quebradas

### 1.1 Segurança

- Nunca imprimir ou gravar tokens, cookies, QR codes, JIDs reais, sessão
  WhatsApp ou URLs assinadas.
- Nunca copiar `academico/estado/`, `.canvas/`, capturas ou materiais para o
  novo repositório.
- Nunca copiar segredos do Bot Telegram para a Suricata.
- Nunca usar o Chrome pessoal do titular.
- Nunca fazer deploy, enviar mensagem, parear WhatsApp ou alterar GCP sem
  autorização explícita para aquela ação.

### 1.2 Segurança da árvore atual

A árvore atual está suja. Existem mudanças acadêmicas e mudanças da Suricata.

- Não usar `git reset --hard`.
- Não usar `git restore`, `git checkout` ou `git clean` para limpar a árvore.
- Não usar `git add .`.
- Não apagar mudanças de outra pessoa/agente.
- O novo repositório deve ser criado a partir de uma lista controlada de
  arquivos, não da árvore inteira.

### 1.3 Fonte de verdade

Quando dois documentos discordarem:

1. o estado real verificado vence;
2. se o estado real não puder ser verificado, escrever `não verificado`;
3. nunca escolher a versão mais conveniente;
4. registrar qual documento estava errado e por quê.

---

## 2. Estado persistente do plano

O agente deve manter esta tabela atualizada. Não marcar uma etapa como
`concluída` sem o critério de aceite correspondente.

| Etapa | Nome | Estado | Último passo concluído | Evidência | Próximo passo |
|---|---|---|---|---|---|
| 0 | Preparação e leitura | pendente | — | — | 0.1 |
| 1 | Congelar a realidade atual | pendente | — | — | 1.1 |
| 2 | Criar o novo repositório | pendente | — | — | 2.1 |
| 3 | Extrair somente a Suricata | pendente | — | — | 3.1 |
| 4 | Remover acoplamentos | pendente | — | — | 4.1 |
| 5 | Documentar para iniciantes | pendente | — | — | 5.1 |
| 6 | Validar clone limpo e imagem | pendente | — | — | 6.1 |
| 7 | Validar infraestrutura em canário | pendente | — | — | 7.1 |
| 8 | Fazer o corte para produção | pendente | — | — | 8.1 |
| 9 | Limpar o repositório acadêmico | pendente | — | — | 9.1 |
| 10 | Encerrar a migração | pendente | — | — | 10.1 |

Estados permitidos:

- `pendente`: ainda não começou;
- `em andamento`: começou, mas ainda não passou no aceite;
- `concluída`: aceite comprovado;
- `bloqueada`: existe um bloqueio concreto registrado;
- `não fazer`: etapa deliberadamente fora do escopo.

Após cada subpasso, atualizar `Último passo concluído`, `Evidência` e
`Próximo passo` nesta tabela.

---

> Este plano começou no repositório acadêmico e foi preservado como histórico
> da extração. Para executar a continuidade no repositório independente, use
> primeiro `docs/PLANO-CONTINUIDADE-INDEPENDENTE.md` e `docs/STATUS.md`.

## 3. Retomada obrigatória após perda de contexto

Execute sempre a partir da raiz:

```powershell
Set-Location C:\GIT\suricata-whatsapp
Get-Content docs\PLANO-EXTRACAO-SURICATA.md
git status --short
git log --oneline -10
```

Depois:

1. leia a tabela da seção 2;
2. encontre a primeira etapa sem `concluída`;
3. leia novamente a seção dessa etapa;
4. confira se os arquivos esperados já existem;
5. não repita uma etapa já concluída;
6. se a árvore ou a nuvem divergirem do registro, corrija o registro antes de
   continuar;
7. execute somente o próximo subpasso indicado.

Se houver dúvida sobre o estado, pare e registre:

```text
BLOQUEIO: <descrição curta>
EVIDÊNCIA: <arquivo, comando ou resultado>
AÇÃO SEGURA POSSÍVEL: <alternativa, se existir>
```

---

## 4. Etapa 0 — Preparação e leitura

### 0.1 Ler os documentos necessários

Leia:

- `AGENTS.md`;
- `README.md`;
- `BOTS.md`;
- `suricata/README.md`;
- `suricata/DOCUMENTATION.md`;
- `suricata/ARCHITECTURE.md`;
- `suricata/RUNBOOK.md`;
- `suricata/tests/README.md`;
- `suricata/whatsapp/README.md`;
- `docs/PLANO-SURICATA-WHATSAPP.md`;
- `docs/PLANTAO-SURICATA-STATUS.md` e `docs/SURICATA-PRODUCAO.md` eram documentos do plano de origem e não fazem parte deste clone; o estado atual está em `docs/STATUS.md` e a operação em `suricata/RUNBOOK.md`.

Não leia o repositório inteiro. Abra outros arquivos somente quando um passo
pedir.

### 0.2 Registrar a linha de base

Execute:

```powershell
git status --short
git diff --check
python -m compileall -q suricata
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Registre os resultados. Se algum teste já estiver vermelho, marque-o como
falha existente. Não conserte código nesta etapa.

### Aceite da etapa 0

- documentos lidos;
- estado da árvore registrado;
- testes de linha de base registrados;
- nenhuma alteração feita no código.

---

## 5. Etapa 1 — Congelar a realidade atual

### 1.1 Criar um inventário de arquivos

Liste os arquivos versionados da Suricata:

```powershell
git ls-files suricata
```

Separe a lista em:

- código Python;
- código Node;
- testes;
- documentação;
- Docker/packaging;
- infraestrutura;
- arquivos que não devem ser extraídos.

### 1.2 Procurar acoplamentos

Execute:

```powershell
rg -n "scripts\.academico|academico/|periodos/|\.canvas|ACADEMICO_|puc-bot-|telegram-" suricata
rg -n "suricata|SURICATA_" --glob '!suricata/**' .
```

Classifique cada resultado como:

- runtime real;
- teste de isolamento;
- documentação;
- integração necessária;
- referência histórica.

Não remova strings de testes de isolamento sem entender o teste.

### 1.3 Resolver a contradição de produção

Os documentos atuais têm snapshots conflitantes. Antes de dizer que o bot está
em produção, verificar somente leitura:

- projeto GCP;
- região;
- Cloud Run Job;
- Scheduler;
- digest da imagem;
- bucket de estado;
- service account;
- secrets por nome, sem ler valores;
- últimas execuções;
- estado de entrega.

Se não houver acesso ou se houver divergência, registrar `não verificado`.

### Aceite da etapa 1

Existe um arquivo de inventário contendo:

- commit de referência;
- lista de arquivos a extrair;
- lista de arquivos proibidos;
- lista de acoplamentos;
- produção atual como `verificada`, `não verificada` ou `bloqueada`;
- instrução de rollback.

---

## 6. Etapa 2 — Criar o novo repositório

### 2.1 Criar um diretório/repositório vazio

O novo repositório deve ter uma raiz própria, por exemplo:

```text
suricata-whatsapp/
```

Não copie a raiz acadêmica inteira.

### 2.2 Criar regras próprias do novo repositório

Criar:

- `README.md`;
- `AGENTS.md`;
- `pyproject.toml` ou configuração equivalente;
- `.gitignore`;
- `.dockerignore`;
- `.gcloudignore`;
- `Dockerfile`;
- diretórios `src/`, `whatsapp/`, `tests/`, `docs/` e `deploy/`.

O novo `AGENTS.md` deve dizer claramente:

- Suricata é pública e usa WhatsApp;
- Canvas é somente leitura;
- nenhuma nota, atraso, frequência ou situação individual pode chegar ao
  grupo;
- nunca versionar segredo ou sessão;
- deploy/envio/pareamento exigem autorização;
- como retomar o plano;
- qual arquivo contém o estado do plano.

### Aceite da etapa 2

O novo repositório existe, tem suas próprias instruções e ainda não contém
dados acadêmicos ou segredos.

---

## 7. Etapa 3 — Extrair somente a Suricata

### 3.1 Copiar por allowlist

Copiar somente os arquivos confirmados no inventário da etapa 1.

Incluir, quando presentes:

- runtime sob `suricata/`;
- testes Suricata;
- `whatsapp/package.json` e `package-lock.json`;
- Dockerfiles e ignores Suricata;
- documentação Suricata;
- manifesto de infraestrutura sem segredos.

Não usar cópia recursiva da raiz acadêmica.

### 3.2 Escolher o layout inicial conservador

Na primeira extração, preservar os caminhos que o programa já usa. Não fazer
refatoração estrutural e extração no mesmo passo.

Primeiro fazer o novo repositório funcionar com o layout conhecido. Uma
refatoração posterior poderá criar `src/`, mas exigirá um plano separado.

### 3.3 Atualizar caminhos

Atualizar apenas referências que apontavam para o repositório antigo. Não
alterar:

- textos públicos;
- horários;
- timezone;
- códigos de saída;
- formato do relatório;
- estados do outbox;
- message IDs;
- ordem dos efeitos;
- contratos Python/Node.

### Aceite da etapa 3

O novo repositório contém o runtime Suricata completo e não contém arquivos de
curso, capturas Canvas, estado pessoal ou código do Bot Telegram.

---

## 8. Etapa 4 — Remover acoplamentos

### 4.1 Resolver o publicador de agenda manual

Atualmente existe integração fora de `suricata/` que importa código Suricata:

```text
scripts/publicar_agenda_manual.py → suricata.storage.gcs
```

Escolher uma única solução:

1. mover o publicador para o novo repositório; ou
2. definir uma interface externa de publicação sem importar módulos internos.

Preferência: criar comando Suricata próprio para publicar a agenda sanitizada.

### 4.2 Tornar a configuração externa

Não colocar no código como regra fixa:

- IDs de ofertas;
- JIDs;
- nomes privados de grupos;
- projeto GCP;
- nomes de secrets;
- tokens;
- sessão WhatsApp.

Esses valores devem ser fornecidos por ambiente, Secret Manager ou arquivo
privado fora do Git.

### 4.3 Separar testes de produto de testes locais da PUC

Manter fixtures PUC somente quando forem necessárias para regressão. Rotulá-las
como fixtures sanitizadas. Adicionar pelo menos um fixture genérico para provar
que o código não depende da PUC Minas.

### Aceite da etapa 4

O novo runtime não importa nada de `academico`, `periodos` ou `scripts.academico`.
O publicador de agenda tem dono claro. Configuração real não está no Git.

---

## 9. Etapa 5 — Documentar para um agente iniciante

### 5.1 O README deve responder em dez minutos

O `README.md` do novo repositório deve conter, nesta ordem:

1. o que Suricata faz;
2. o que Suricata nunca faz;
3. teste local sem efeitos;
4. modos disponíveis;
5. onde roda em produção;
6. onde as mensagens são escritas;
7. onde Canvas é consultado;
8. onde ficam outbox e estado;
9. onde está o WhatsApp Node;
10. como configurar sem expor segredo;
11. como testar;
12. como implantar;
13. como verificar;
14. como parar e fazer rollback.

### 5.2 Criar documentos curtos

Criar:

- `docs/PRODUCT.md`: escopo, público e proibições;
- `docs/ARCHITECTURE.md`: fluxo ponta a ponta;
- `docs/CONFIGURATION.md`: variáveis e fontes de segredo;
- `docs/OPERATIONS.md`: rotina diária e incidentes;
- `docs/SECURITY.md`: ameaças e controles;
- `docs/DEPLOYMENT.md`: build, Cloud Run, Scheduler e IAM;
- `docs/TROUBLESHOOTING.md`: falhas comuns;
- `docs/MIGRATION.md`: origem, data e limitações da extração.

### 5.3 Usar um único status operacional

Criar um arquivo como `docs/STATUS.md` com três campos obrigatórios:

```text
Código local: verificado/não verificado
Infraestrutura: verificada/não verificada
Produção e entrega: verificada/não verificada
Última verificação: data/hora e evidência
```

Não usar “produção ativa” quando somente o código local foi testado.

### Aceite da etapa 5

Um agente novo consegue explicar o fluxo e encontrar os arquivos principais
sem abrir o repositório acadêmico.

---

## 10. Etapa 6 — Validar clone limpo e imagem

### 6.1 Clonar do Git

Criar um clone temporário do novo repositório. Não usar a cópia de trabalho
como prova.

### 6.2 Executar os testes

No clone limpo, executar os comandos definidos pelo novo `README.md`, incluindo
Python, Node e compilação.

### 6.3 Construir a imagem

Construir a imagem com o Dockerfile do novo repositório. Conferir:

- entrypoint correto;
- modo padrão seguro;
- Node instalado;
- dependências instaladas pelo lockfile;
- ausência de `auth.json`, `.wa-auth`, QR, banco e secrets;
- ausência de `academico/`, `periodos/` e `.canvas/`.

### 6.4 Verificar reprodutibilidade

Registrar:

- commit;
- digest da imagem;
- comandos usados;
- resultados;
- arquivos excluídos pelo contexto de build.

### Aceite da etapa 6

Um clone limpo consegue testar e construir a imagem sem depender deste
repositório acadêmico.

---

## 11. Etapa 7 — Validar infraestrutura em canário

Esta etapa exige autorização para ações de nuvem. Antes disso, somente leitura.

### 7.1 Criar ou confirmar namespace Suricata

Usar somente recursos com nomes Suricata:

- projeto GCP Suricata;
- bucket Suricata;
- Artifact Registry Suricata;
- service account Suricata;
- secrets Suricata;
- Job e Scheduler `suricata-*`.

Nunca reutilizar recursos `academico-*`, `puc-bot-*`, `telegram-*` ou estado do
Bot pessoal.

### 7.2 Executar canário sem entrega

Usar:

- estado separado;
- `SURICATA_ENTREGA=desligada`;
- nenhum JID de produção;
- imagem identificada por digest;
- logs sanitizados.

### 7.3 Verificar o canário

Confirmar:

- coleta Canvas somente por GET;
- planejamento correto;
- persistência;
- lease/fencing;
- outbox;
- tratamento de falhas;
- corte das 21:00 BRT;
- alertas operacionais.

### Aceite da etapa 7

O canário executa no Cloud Run sem enviar mensagens e sem acessar recursos do
Bot acadêmico.

---

## 12. Etapa 8 — Fazer o corte para produção

Não executar esta etapa sem autorização explícita.

### 8.1 Pré-corte

- build concluído;
- digest registrado;
- clone limpo aprovado;
- IAM revisado;
- canário aprovado;
- rollback documentado;
- destino confirmado por humano;
- sessão WhatsApp disponível pelo mecanismo aprovado.

### 8.2 Corte controlado

1. publicar o novo Job com entrega desligada;
2. fazer read-back do Job e Scheduler;
3. executar uma rodada shadow;
4. conferir estado e destino;
5. ligar entrega somente após autorização;
6. testar apenas o grupo autorizado;
7. observar várias rodadas;
8. desligar o caminho antigo;
9. manter a imagem anterior para rollback.

Nunca deixar os schedulers antigo e novo ativos ao mesmo tempo.

### Aceite da etapa 8

O novo repositório é a origem do digest em produção, a entrega foi observada,
o estado é o correto e existe rollback testado ou documentado.

---

## 13. Etapa 9 — Limpar o repositório acadêmico

Só fazer depois de a etapa 8 estar concluída.

### 9.1 Remover a implementação

Remover somente a implementação Suricata. Preservar o conteúdo acadêmico e o
Bot Telegram.

### 9.2 Deixar um ponteiro

Atualizar `BOTS.md` e criar uma nota curta apontando para o novo repositório.

A nota deve explicar:

- que Suricata foi extraída;
- qual commit/data fez a extração;
- onde está a documentação nova;
- que este repositório não é mais necessário para executar Suricata.

### 9.3 Remover referências operacionais antigas

Remover ou marcar como histórico:

- planos de deploy da Suricata dentro do repositório acadêmico;
- snapshots conflitantes;
- instruções que parecem comandar a produção Suricata;
- imports ou scripts que dependam do runtime extraído.

Não apagar evidências acadêmicas nem históricos necessários para proveniência.

### Aceite da etapa 9

O repositório acadêmico continua funcionando para seu próprio escopo e não
precisa da árvore Suricata para testar ou operar o Bot Telegram.

---

## 14. Etapa 10 — Encerrar

### 10.1 Executar a matriz final

| Verificação | Resultado esperado |
|---|---|
| Novo clone limpo | funciona sozinho |
| Testes Python | verdes |
| Testes Node | verdes |
| Docker build | concluído |
| Imagem | sem dados acadêmicos ou segredos |
| Cloud Run | recursos Suricata próprios |
| Scheduler | somente um caminho ativo |
| WhatsApp | destino correto |
| Estado | bucket/prefixo Suricata |
| Rollback | documentado |
| Repo acadêmico | sem runtime Suricata |

### 10.2 Atualizar o registro

Preencher a tabela da seção 2 com:

- `concluída` em cada etapa aceita;
- data/hora;
- commit;
- evidência curta;
- limitações remanescentes.

### 10.3 Mensagem final obrigatória

O relatório final deve conter:

```text
EXTRAÇÃO: concluída ou bloqueada
NOVO REPOSITÓRIO: <local/URL>
COMMIT DE ORIGEM: <SHA>
PRODUÇÃO: verificada/não verificada
ROLLBACK: <procedimento>
PENDÊNCIAS: <lista>
SEGREDOS EXPOSTOS: não
```

---

## 15. Quando parar imediatamente

Pare e atualize o registro se:

- a produção documentada contradizer a nuvem;
- um arquivo acadêmico aparecer no novo pacote;
- um teste falhar depois de uma mudança;
- o Dockerfile depender de caminho antigo;
- a imagem incluir sessão, QR ou segredo;
- aparecer recurso GCP do Bot Telegram no namespace Suricata;
- o destino WhatsApp não estiver confirmado;
- houver duas versões do Scheduler ativas;
- a ação exigir envio, pareamento, deploy ou alteração de infraestrutura sem
  autorização;
- não for possível provar de onde veio o digest implantado.

Não tente contornar o bloqueio apagando arquivos ou repetindo comandos em loop.

---

## 16. Definição de sucesso

A migração só está concluída quando todas estas frases forem verdadeiras:

1. Um agente novo entende a Suricata sem ler o repositório acadêmico.
2. O novo repositório testa e constrói a Suricata a partir de um clone limpo.
3. O novo repositório não contém capturas, materiais ou estado pessoal.
4. O runtime não importa código do Bot Telegram.
5. A infraestrutura usa recursos próprios da Suricata.
6. A produção atual foi verificada ou explicitamente marcada como não
   verificada.
7. Existe rollback.
8. O repositório acadêmico continua dedicado ao curso e ao Bot pessoal.