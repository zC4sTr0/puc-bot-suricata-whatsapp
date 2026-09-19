# Glossário para estudantes

O **PUC Bot da Suricata** é independente e não oficial da PUC Minas. Os termos abaixo aparecem nas mensagens e na documentação; quando houver dúvida sobre um prazo, confirme no Canvas e nos canais oficiais da disciplina.

## Termos acadêmicos

**Canvas** — plataforma de aprendizagem usada para disponibilizar disciplinas, atividades, anúncios e prazos. Neste projeto, “Canvas” significa a fonte externa consultada em modo real. O bot deve fazer apenas a leitura autorizada do que é coletivo; o demo usa dados fictícios e não acessa a plataforma.

**Prova / avaliação** — atividade usada para avaliar conhecimento. O aviso pode informar que ela foi publicada ou que há uma data no Canvas. O bot não aplica a prova, não corrige e não mostra nota.

**Quiz** — questionário ou avaliação curta no Canvas. O bot pode avisar que existe ou que está disponível, mas não inicia tentativa, não acessa resposta e não revela senha.

**Tarefa / entrega** — atividade que pede um trabalho, arquivo ou resposta e pode ter um prazo. O bot pode comunicar o título, a data e o link quando esses dados forem coletivos e estiverem disponíveis. Ele não vê a sua submissão nem confirma que você entregou.

**Anúncio** — comunicado publicado na área da disciplina. Um anúncio pode ser uma origem de informação para a turma, mas o aviso do bot não substitui a leitura do texto original.

**Agenda manual** — registro coletivo inserido por um operador autorizado para complementar o Canvas, por exemplo uma prova anunciada em aula. É uma fonte informada por uma pessoa, não uma publicação oficial automática da universidade.

## Termos do bot

**Aviso** — mensagem informativa preparada para o destino autorizado. Deve permitir identificar a origem, a disciplina, o tipo de atividade e a data quando esses dados existirem.

**Origem do aviso** — indicação de onde o fato veio: Canvas ou agenda manual. Se a fonte estiver indisponível ou incompleta, o bot não deve inventar uma ausência de atividade.

**Rodada** — uma execução completa do ciclo: consultar a fonte, organizar novidades, verificar regras, registrar o estado e, somente se permitido, preparar a entrega.

**Modelo coletivo** — funcionamento atual em que uma instância atende um grupo ou destino autorizado de turma. O conteúdo é pensado para a turma, não para o perfil individual de cada estudante.

**Evolução individual** — possível produto futuro com consentimento, escopo de cursos, destino privado, revogação e controles de dados por pessoa. Não é uma capacidade disponível só porque o bot envia mensagens no WhatsApp.

**Demo** — modo local, offline e determinístico que usa dados sintéticos. Ele mostra mensagens planejadas sem consultar Canvas, gravar estado de produção ou enviar WhatsApp.

**Janela de entrega** — período em que um tipo de aviso pode ser enviado segundo as regras do runtime. Uma rodada fora da janela pode apenas registrar ou aguardar; “rodou” não significa “enviou”.

**Corte / silêncio** — bloqueio de entrega em determinados horários ou quando uma condição de segurança não foi satisfeita. O silêncio do bot não prova que não existe atividade; consulte a fonte.

**Confirmação de entrega** — retorno da ponte do WhatsApp usado para saber se uma mensagem foi aceita como entregue. Ele não confirma que cada estudante leu o conteúdo nem que o prazo acadêmico foi alterado.

**Estado** — memória operacional que registra o que já foi observado, planejado ou entregue. Token, sessão e dados reais não devem ser colocados em documentação ou fixtures públicas.

**Ponte do WhatsApp** — componente técnico que conecta o runtime Python a uma sessão autorizada do WhatsApp. A ponte não é a fonte acadêmica e não transforma o projeto em serviço oficial da PUC Minas.

## Termos que não são promessa

**“Aviso coletivo”** não significa que o conteúdo está correto ou que o grupo inteiro recebeu a informação. Confirme origem, data e destinatário.

**“Público”** não significa “sem privacidade”. Um dado visível para uma turma ainda pode conter informação pessoal e não deve ser republicado sem necessidade.

**“Teste verde”** significa que uma verificação local passou. Não significa Canvas ao vivo, deploy funcionando, sessão WhatsApp conectada ou entrega real.
