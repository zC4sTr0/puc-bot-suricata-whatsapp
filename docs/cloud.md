# Camada cloud: explicação segura para iniciantes

Este documento explica **o que cada peça da nuvem faz** e **quem pode usá-la**. Ele não autoriza acesso a contas, grupos, projetos ou credenciais. A Suricata é um projeto independente e não oficial da PUC Minas; o Canvas e os canais oficiais continuam sendo a fonte de verdade.

> **Regra de segurança:** os nomes abaixo são papéis da arquitetura. Em uma operação real, substitua apenas os placeholders, depois de confirmar o recurso correto com o responsável. Nunca copie um identificador, token, QR code, sessão, JID, nome de bucket ou comando de um ambiente real para uma issue, tutorial ou script.

## A visão em uma frase

Uma execução finita do **Cloud Run Job** acorda, recebe a configuração autorizada, lê informações coletivas do **Canvas**, consulta e atualiza o estado protegido no **GCS**, prepara os avisos e, somente quando todos os limites estão abertos, chama o Node para conversar com o WhatsApp. O **Cloud Scheduler** apenas inicia essa execução; ele não autoriza envio por si só.

O caminho de publicação da imagem é separado: uma fonte aprovada é construída pelo **Cloud Build**, armazenada no **Artifact Registry** e referenciada por digest. O **IAM** define quais identidades podem fazer cada parte. O **Secret Manager** entrega segredos ao runtime sem colocá-los no Git, na imagem, nos argumentos ou nos logs.

## As peças, em linguagem simples

### Canvas

O Canvas é a fonte acadêmica oficial consultada pela Suricata. O projeto deve ler somente dados coletivos e permitidos, como disciplinas, atividades, prazos e anúncios autorizados.

A Suricata não deve consultar notas, faltas, submissões, tentativas, respostas ou outros dados individuais. Uma falha ou coleta parcial do Canvas não significa “não há atividade”: o comportamento seguro é registrar a limitação e orientar a conferência direta no Canvas.

No modo local de demonstração, o Canvas é substituído por uma fixture fictícia. Isso permite estudar o planejamento sem conta, rede ou token.

### Secret Manager

O Secret Manager é o cofre de valores sensíveis. Exemplos: token de leitura do Canvas e referências controladas a materiais de sessão. O runtime autorizado recebe somente o que precisa, no momento da execução.

Segredos não pertencem ao repositório, ao Dockerfile, à imagem, a argumentos, a capturas de tela ou a logs. O nome de um secret também pode revelar informação operacional; use `<secret-canvas-autorizado>` em documentação.

Guardar um valor no Secret Manager não concede permissão automaticamente. A identidade do Job ainda precisa de uma autorização IAM específica para ler aquele secret.

### GCS (Cloud Storage)

O GCS é o armazenamento de objetos usado, quando autorizado, para estado operacional: memória de itens já vistos, lease, outbox, relatórios sanitizados e, em uma operação aprovada, o objeto de sessão do WhatsApp.

O estado deve ficar em um bucket e prefixo exclusivos, representados aqui por `<bucket-estado-autorizado>` e `<prefixo-suricata>`. A separação evita misturar dados de bots, turmas ou ambientes. O mecanismo de geração/CAS impede que uma execução sobrescreva silenciosamente o estado de outra.

GCS não é um banco de dados mágico nem um backup universal. É preciso definir retenção, acesso, recuperação e descarte antes de guardar qualquer dado. Nunca use um bucket real em exemplos didáticos.

### Cloud Build

Cloud Build é o construtor remoto da imagem do container. Ele recebe uma revisão aprovada do código, executa as verificações previstas e produz uma imagem identificável.

A imagem deve ser tratada como um artefato imutável. A referência operacional segura é o digest `<digest-sha256-confirmado>`, não uma tag móvel como “latest”. Um build concluído prova que o construtor terminou; não prova que o Job certo recebeu a imagem, que o IAM está correto ou que o WhatsApp entregará uma mensagem.

### Artifact Registry

O Artifact Registry guarda as imagens produzidas pelo Cloud Build. Ele é o catálogo de artefatos que o Cloud Run Job pode executar.

A operação deve registrar qual digest foi aprovado, quem o aprovou e qual digest anterior pode servir de rollback. Limpeza de imagens deve respeitar retenção e investigação: apagar o único digest anterior pode retirar a principal rota de recuperação.

### Cloud Run Job

Cloud Run Job executa uma tarefa finita e termina. Ele é diferente de um servidor permanentemente ligado: para a Suricata, uma execução faz uma rodada e encerra.

A configuração deve ser explícita: uma task quando possível, timeout limitado, tentativas limitadas, argumentos conhecidos e uma identidade dedicada `<service-account-job-autorizada>`. O Job não deve ganhar permissões amplas para “facilitar” a operação.

Uma execução do Job pode terminar com sucesso sem enviar nada: pode não haver novidade elegível, pode ser horário de silêncio, a coleta pode estar parcial ou a entrega pode estar desligada. “Executou” não significa “entregou”.

### Cloud Scheduler

Cloud Scheduler é o despertador. Ele chama o Job na frequência aprovada, por exemplo uma agenda representada por `<frequencia-confirmada>`.

Ter uma agenda ativa não autoriza a mensagem. O próprio código precisa revalidar horário, destino, estado, lease, origem do evento, idempotência e entrega antes de chamar a ponte. Deve existir exatamente a quantidade de agendas aprovada; criar uma segunda para compensar uma falha pode duplicar rodadas e efeitos.

### IAM

IAM é o sistema de identidade e permissão. Ele responde “qual identidade pode fazer qual ação em qual recurso?”.

Prefira identidades separadas para construir, executar e administrar. Como exemplo conceitual:

- o construtor pode publicar no repositório de imagens;
- o Job pode ler o secret autorizado e acessar apenas seu prefixo GCS;
- o Scheduler pode iniciar o Job aprovado;
- uma pessoa administradora pode revisar, canarizar e fazer rollback;
- nenhuma dessas permissões deve ser presumida só porque o projeto é o mesmo.

Use o menor privilégio, revise concessões e remova acessos temporários. IAM não é substituto para autorização acadêmica, consentimento do grupo ou validação do destino.

### WhatsApp e Node

O Python é o dono da política: coleta, planejamento, estado, outbox e gates. O Node é um adaptador de transporte: abre a sessão autorizada, tenta enviar e devolve um resultado compatível com a confirmação esperada.

A sessão WhatsApp, o QR code e o destino são materiais sensíveis. Eles não devem ser gerados em aula, publicados em logs ou copiados para fixtures. A ponte não deve decidir sozinha que uma mensagem é permitida. Sem sessão válida, destino confirmado ou confirmação de entrega, o sistema deve parar ou registrar falha — não inventar sucesso.

## O que é necessário em cada cenário

| Cenário | Pode usar | Não precisa | O que não prova |
| --- | --- | --- | --- |
| **Demo local** | Python, fixtures sintéticas, relógio controlado e armazenamento temporário | Conta cloud, Canvas ao vivo, Secret Manager, GCS real, sessão e grupo WhatsApp | Acesso ao Canvas, IAM, build, Job ativo ou entrega |
| **Desenvolvimento local com integração controlada** | Credenciais temporárias autorizadas, ambiente isolado e destino de teste explicitamente aprovado | Scheduler e produção | Que a operação de produção está correta |
| **Operação autorizada** | Projeto `<projeto-autorizado>`, região `<regiao-confirmada>`, secrets, GCS, imagem por digest, Job, Scheduler, IAM, sessão e destino confirmados | — | Mesmo assim, cada execução deve ser observada e o Canvas deve continuar sendo conferido |

A demo deve ser o caminho padrão para estudantes. A operação autorizada exige um responsável identificável, autorização para consultar o Canvas, autorização para o destino do WhatsApp, política de retenção e um plano de parada. Não transforme uma fixture local em “prova” de integração real.

## Custos: como pensar sem inventar preços

A nuvem cobra conforme o produto, a região, o volume e a configuração vigentes. Sem consultar a conta e a tabela oficial da data, não é seguro prometer um valor.

Qualitativamente, os principais vetores são:

- **Cloud Build:** tempo de build, volume do contexto e retenção de logs/artefatos;
- **Artifact Registry:** armazenamento de imagens, operações e transferência aplicável;
- **Cloud Run Job:** CPU, memória, duração, quantidade de tasks, retries e frequência;
- **Cloud Scheduler:** quantidade de agendas e invocações, conforme cotas e regras vigentes;
- **GCS:** bytes armazenados, operações, retenção e transferência;
- **Secret Manager:** versões mantidas, operações e acessos;
- **IAM:** o controle de acesso normalmente não é o principal item de cobrança, mas auditoria e logs associados podem gerar consumo.

Para controlar custo, use uma única agenda aprovada, limites de timeout e retries, contexto de build pequeno, retenção definida, lifecycle do GCS revisado e alertas de orçamento. Um alerta não interrompe necessariamente o consumo; alguém precisa definir o que acontece ao atingir o limite.

## Canário sem entrega

Um canário é uma execução controlada para observar o candidato antes de expô-lo ao fluxo normal. Ele deve usar **estado separado**, digest candidato confirmado, identidade restrita e `SURICATA_ENTREGA=desligada` ou equivalente fail-closed.

O canário seguro deve verificar, sem enviar WhatsApp:

1. a imagem por `<digest-candidato-confirmado>` é a que o Job canário recebeu;
2. o Job inicia com os argumentos e configuração esperados;
3. o Canvas, se autorizado para esse teste, é lido somente dentro da allowlist;
4. o GCS canário usa `<bucket-canario>` e `<prefixo-canario>`, nunca o estado produtivo;
5. o relatório sanitizado termina sem chamada à ponte de entrega;
6. logs não contêm token, QR, sessão, JID, payload sensível ou dados identificáveis;
7. retries, timeout e identidade estão dentro do limite aprovado.

A palavra “canário” não significa envio para um grupo menor. Neste projeto, a etapa inicial é deliberadamente **sem entrega**. Uma passagem do canário não autoriza sozinha ligar o destino real.

## Rollback sem apagar evidências

Rollback significa voltar a executar um digest anterior conhecido e aprovado, por exemplo `<digest-anterior-confirmado>`. Antes de qualquer mudança, registre o digest candidato, o digest anterior, a configuração não secreta, a identidade, o estado usado e o critério de parada.

Se o candidato falhar:

1. pare a promoção e preserve logs sanitizados e relatórios;
2. impeça novas execuções ou mantenha a entrega desligada, conforme o plano autorizado;
3. restaure o digest anterior no recurso correto, sem criar um segundo Scheduler;
4. preserve GCS, outbox, lease e histórico para investigação e idempotência;
5. faça read-back do Job, digest, argumentos, identidade e agenda;
6. confirme que não houve envio duplicado antes de reabrir qualquer entrega;
7. registre a causa, o impacto e o próximo gate.

Não apague o estado para “limpar” uma falha e não faça rollback trocando apenas uma tag móvel. Se o digest anterior não estiver disponível ou o recurso não puder ser identificado com segurança, permaneça parado e escale para o responsável.

## Limites que continuam valendo

- O Canvas é a fonte oficial; mensagem do bot não corrige o Canvas.
- Coleta parcial, timeout ou erro não significam ausência de atividade.
- Testes verdes, build concluído e canário sem entrega não provam entrega real.
- O Scheduler acordar o Job não significa que uma mensagem será enviada.
- O Python decide a política; o Node não ganha autoridade para publicar por conta própria.
- Segredos, sessões, QR codes, destinos, tokens e dados identificáveis ficam fora do Git e dos exemplos.
- Uma operação real depende de autorização do responsável, destino confirmado, IAM revisado, estado recuperável e observação contínua.
- Documentação não substitui read-back do projeto `<projeto-autorizado>`, região `<regiao-confirmada>`, Job, Scheduler, bucket, digest e identidade no ambiente real.

Para aprender, comece pelo [`guia.md`](guia.md) e pela demo. Para entender a estrutura, leia [`arquitetura.md`](arquitetura.md). Para uma operação autorizada, use também [`deploy-gcp.md`](deploy-gcp.md) e [`configuracao.md`](configuracao.md), lembrando que esses documentos descrevem controles e não concedem autorização.
