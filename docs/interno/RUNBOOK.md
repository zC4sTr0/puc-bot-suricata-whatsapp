# Runbook humano conservador — Suricata

> Este runbook privilegia leitura, reversibilidade e parada. Os comandos de nuvem abaixo são read-only, salvo os blocos explicitamente marcados como **ação com efeito**. Não executar uma ação com efeito sem autorização específica e sem os gates H1–H3 aplicáveis.

## 1. Pré-voo obrigatório

Execute na raiz do repositório:

```bash
git status --short
git diff --check
python -m compileall -q suricata
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

Pare se houver teste vermelho, segredo exposto, diff inesperado, arquivo de sessão/QR no repositório ou qualquer mudança que não pertença ao escopo. Não use `git reset --hard`, `git restore .`, `git checkout -- .` ou `git clean` para “limpar” a árvore.

Confirme também:

- hora e decisões em `America/Sao_Paulo`;
- que o alvo é o projeto Suricata, não o projeto do Bot Telegram;
- que a ação planejada é somente leitura ou está autorizada separadamente;
- que `SURICATA_ENTREGA` não está sendo ligada por acidente;
- que não existe `SURICATA_CANVAS_TOKEN`, sessão, QR ou JID real em arquivo de configuração versionado.

## 2. Contrato dos modos

### Probe sem efeito

```bash
python -m suricata --mode shadow
```

Esperado: uma linha JSON com `mode=shadow`, `status=ok`, `adapter=none`, código 0. Isso prova apenas que o roteador local respondeu. Não consulta Canvas, GCS ou WhatsApp.

### Rodada funcional

```bash
SURICATA_ENTREGA=desligada python -m suricata --mode rodada
```

Use somente com estado e token de teste controlados. `desligada` é um bloqueio de entrega, não prova de que toda integração externa esteja ausente. Para simulação determinística, prefira `--mode demo` ou os testes/fixtures de [`tests/README.md`](../../suricata/tests/README.md), com Canvas, relógio, memória e ponte falsos.

Os modos `sentinela`, `grupos` e `teste-envio` foram removidos na simplificação de modos de 2026-09-18; procedimentos que os usavam estão no histórico do git.

## 3. Comandos read-only de nuvem

Defina o binário e o alvo sem alterar recursos:

```bash
G="/c/Users/C4sTr/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin/gcloud"
PROJECT="suricata-college-20260913"
REGION="southamerica-east1"
"$G" projects describe "$PROJECT" --format='yaml(projectId,lifecycleState)' \
  --quiet
"$G" run jobs list --region "$REGION" --project "$PROJECT" \
  --format='table(name,latestCreatedExecution,startTime,completionTime)' --quiet
"$G" scheduler jobs list --location "$REGION" --project "$PROJECT" \
  --format='table(name,state,schedule,timeZone)' --quiet
"$G" artifacts repositories list --location "$REGION" --project "$PROJECT" \
  --format='table(name,format)' --quiet
"$G" storage ls "gs://${PROJECT}-estado/" --project "$PROJECT"
```

Para um Job encontrado no read-back, consulte sem executar:

```bash
"$G" run jobs describe NOME_CONFIRMADO --region "$REGION" --project "$PROJECT" \
  --format='yaml(name,template.template.containers,template.template.timeout,template.template.maxRetries)' --quiet
```

Não copie tokens, headers, conteúdo de `auth.json`, URLs assinadas ou logs brutos para a conversa ou para o Git. `storage ls` é preferível a `storage cat`; leia conteúdo somente quando o procedimento exigir um campo sanitizado e aprovado.

### Nomes divergentes

O plano histórico usa `suricata-sentinela` e `suricata-sentinela-10min`. O inventário [`infra/isolamento.json`](../../suricata/infra/isolamento.json) registra, em 2026-09-16, `suricata-rodada` e `suricata-rodada-10min`, além de uma execução datada. Esses nomes são fatos históricos **não verificados novamente**. Nunca execute, atualize ou delete pelo nome sem primeiro listar e confirmar o recurso, projeto, região, imagem, argumentos e agenda.

## 4. Critérios de parada

Pare imediatamente e registre o fato quando ocorrer qualquer um destes casos:

- projeto, região, Job, Scheduler, bucket ou service account não correspondem ao namespace Suricata;
- aparecer recurso `academico-*`, `diario-0700`, `sentinela-10min`, bucket `puc-bot-*` ou secret `telegram-*` no alvo;
- imagem/digest não puder ser ligado ao código local por evidência;
- IAM, estado, sessão ou geração CAS estiverem inválidos ou desconhecidos;
- coleta parcial for apresentada como ausência;
- horário for 21:00–06:59 BRT, ou o corte não puder ser revalidado antes de `claim`/ponte;
- houver ACK ausente, divergente ou sessão `logged_out`;
- surgir pedido de senha, QR, token, cookie, JID não confirmado ou dado pessoal em log;
- qualquer comando read-only pedir confirmação de alteração ou produzir efeito não esperado.

Não “tente mais uma vez” em loop. Preserve a saída sanitizada, o comando, horário, projeto/região e motivo da parada.

## 5. Gates humanos H1–H3

Gates humanos são explícitos e únicos; nenhum deles deve ser inferido de um teste verde.

### H1 — pareamento QR

**Efeito:** vincula o chip dedicado à sessão WhatsApp. Só executar quando o titular autorizar o pareamento.

- abrir o procedimento de pareamento em janela controlada;
- o titular escaneia o QR no celular do chip;
- não copiar QR, sessão ou arquivos de auth para Git/log/conversa;
- confirmar apenas sucesso sanitizado e remover a cópia temporária do PC;
- se aparecer logout, timeout ou dúvida, parar; não repetir em loop.

### H2 — grupo correto

**Efeito:** colocar/selecionar a audiência. O JID só pode ser configurado após confirmação humana do nome exato do grupo.

- listar grupos sem publicar mensagens e sem mostrar números de telefone;
- se houver zero grupos, o titular adiciona o chip ao grupo da turma;
- se houver mais de um candidato, o titular escolhe; não adivinhar;
- registrar nome e JID confirmado somente no ambiente autorizado, nunca no JSON de exemplo.

### H3 — inspeção da mensagem de teste

**Efeito:** valida envio externo e pode publicar no grupo de teste.

- usar apenas um grupo de teste autorizado, nunca o grupo da turma por conveniência;
- enviar a mensagem de teste somente com autorização explícita;
- o titular verifica visualmente quantidade e texto;
- interromper se houver duplicata inesperada, texto pessoal, destinatário errado, ACK inconsistente ou sessão alterada;
- remover/expirar o teste conforme o procedimento autorizado e registrar resultado sanitizado.

Sem H1, H2 e H3, não parear, não configurar destino e não enviar teste. A leitura de configuração ou a execução de `shadow` não substitui esses gates.

## 6. Limites de deploy e alteração externa

Deploy, atualização de imagem, alteração de Job/Scheduler, mudança de env vars/secrets, upload de sessão, publicação de mensagem, pareamento e criação de alertas são ações separadas. Este runbook não os autoriza por estar sendo executado.

Antes de qualquer uma dessas ações, exigir: diff revisado, build Docker real, imagem por digest, read-back do recurso, projeto/região confirmados, IAM verificado, plano/registro atualizado e gate humano aplicável. Se qualquer evidência faltar, permaneça em sombra ou pare.

Nunca use `gcloud run jobs update`, `gcloud scheduler jobs update`, `gcloud run jobs execute`, `gcloud builds submit` ou upload de `auth.json` como “teste” sem autorização própria. Após uma ação autorizada, leia de volta o recurso exato; sucesso do comando não prova que o estado desejado foi aplicado.

## 7. Recuperação conservadora

- **Canvas indisponível:** não anuncie ausência; preserve relatório parcial/erro e aguarde próxima rodada.
- **Sessão WhatsApp caída:** não envie; notifique apenas o canal operacional autorizado e retome por H1 quando houver autorização.
- **Outbox pendente:** não force `sent`; mantenha `pending` ou `expirado` conforme contrato e ACK.
- **Estado/CAS em conflito:** não sobrescreva; faça read-back da geração e pare se a concorrência não puder ser explicada.
- **Job parado ou nome divergente:** liste recursos e compare datas; não crie um segundo Job/Scheduler por suposição.

## 8. Relato mínimo

Registre: data/hora BRT, comando, projeto/região, modo, efeito esperado, resultado sanitizado, código de saída, gate H1/H2/H3 (quando aplicável), evidência local e motivo de parada. Nunca registre segredo, sessão, token, QR, cookie, URL assinada ou conteúdo de estado sensível.
