# Auditoria de seams de isolamento multi-instância — bot individual

> **DRAFT / NÃO IMPLEMENTADO.** Este documento é somente uma auditoria do
> comportamento atual. Não implementa isolamento individual, não altera o
> contrato do produto e não autoriza ativação de múltiplas instâncias.
>
> **Data:** 2026-09-19
> **Escopo lido:** `rodada/config.py`, `rodada/execucao.py`,
> `storage/cas.py`, `storage/outbox.py`, `storage/lease_rodada.py`,
> `storage/sessao.py`, `integracao/bridge.py`, `whatsapp/enviar.mjs`,
> `whatsapp/parear.mjs`, `whatsapp/auth-dir.mjs`, composição do runtime,
> persistência e testes Python/Node relacionados.

## Veredito

Há seams reais para separar destinos e estado por prefixo, mas a unidade de
isolamento atual é a configuração/estado da **instância operacional**, não um
estudante/tenant. O isolamento depende de cada processo receber um
`SURICATA_ESTADO_URI` e uma configuração coerente; não há identidade, política
de autorização ou vínculo verificável entre tenant, sessão WhatsApp, JID,
token Canvas e prefixo. O maior bloqueio é o lease global relativo
`locks/rodada.lock`: ele serializa instâncias que compartilham o mesmo estado e
não contém um identificador de instância.

## Matriz de seams

| Seam | Símbolo/arquivo | Comportamento atual | Risco para multi-instância | Teste que falta | Recomendação |
|---|---|---|---|---|---|
| Entrada de estado | `run_from_environment()` / `rodada/runtime.py:31-43` | Uma URI `SURICATA_ESTADO_URI` cria um único backend; a sessão/ponte só é construída quando `SURICATA_ENTREGA=ligada`. | Um processo pode apontar para o estado de outra instância por configuração; não há `instance_id` resolvido e verificado contra a URI. | Subir A e B com URIs/prefixos distintos e provar que nenhuma chamada de factory, objeto ou relatório cruza o namespace; rejeitar URI incompatível com identidade declarada. | Introduzir um contexto de instância/tenant resolvido por política, não por env livre; validar URI, prefixo e credenciais como um conjunto atômico. |
| Destinos e prefixos | `Destino`, `destinos_do_ambiente()` / `rodada/config.py:43-55,109-169` | IDs são validados e viram prefixos `grupo` ou `destinos/<id>`; env pode sobrepor o arquivo inteiro (`env > arquivo`). | O operador/processo pode trocar JID e prefixo independentemente; formato válido não prova autorização nem titularidade. Uma lista com ID reaproveitado em outra instância pode apontar ao mesmo estado. | Fixture A/B com mesmo ID, JIDs trocados e `SURICATA_CONFIG`/env concorrentes; exigir falha antes de storage quando identidade não corresponde ao prefixo. | Resolver destinos a partir de manifesto/política assinada e derivar prefixo opaco; não aceitar JID como autoridade de tenant. |
| Lease de rodada | `LEASE`, `Lease.adquirir()` / `storage/lease_rodada.py:17,41-77` | Sempre usa `locks/rodada.lock`; criação, expiração e remoção usam CAS. | É global dentro do backend: A e B que compartilham URI bloqueiam uma à outra; se o compartilhamento for acidental, o lease também não distingue dono/tenant. `dono` é UUID sem vínculo verificável à instância. | Dois processos com mesma URI e dois prefixes: verificar se a política desejada é serialização global ou lease por instância; dois tenants devem provar não bloqueio indevido. | Tornar o escopo do lease explícito: por instância/tenant quando houver paralelismo, ou declarar e testar serialização global; incluir identidade e fencing verificáveis no documento. |
| Execução multi-destino | `executar_destinos()` / `rodada/execucao.py:338-371` | Faz uma coleta, adquire um lease global e executa cada destino com `destino.prefixo`; memória, outbox e relatório usam prefixos separados. | Um erro de configuração pode compartilhar prefixo; o mesmo `ponte`/sessão é reutilizado para todos os destinos. A coleta é comum mesmo quando a futura instância individual exigiria escopo próprio. | Rodar A/B em paralelo, com falha em um destino e troca de JID, e verificar que memória/outbox/relatório e sessão não têm efeitos cruzados. | Separar composição por instância e declarar se uma sessão WA pode servir múltiplos tenants; preferir uma ponte/contexto por unidade autorizada. |
| Outbox temporário → CAS | `OutboxSincronizado` / `storage/persistencia_rodada.py:15-51`; chamada em `execucao.py:232-250` | Copia `prefixo/outbox.json` para arquivo temporário, usa lock local e publica de volta com `generation`. | O CAS protege o objeto, mas o isolamento semântico vem apenas de `outbox_nome`; uma instância mal configurada pode ler/republicar outbox alheio. `podar()` altera o snapshot local antes de publicar. | Teste com duas instâncias e mesmo objeto em GCS/fake CAS, incluindo `podar`, publicação intercalada e conflito; provar que o conflito não envia lote. | Exigir namespace/tenant no contrato do backend e verificar owner/versão antes de cada publish; tratar conflito como abortar sem efeito externo. |
| Outbox local e lock | `Outbox.__init__`, `_lock_arquivo()` / `storage/outbox.py:60-87,240-298` | Lock é irmão do JSON, recarrega snapshot a cada mutação e usa `os.replace`; testes cobrem processos concorrentes e fencing por `attempt_id`. | Funciona para processos que apontam exatamente ao mesmo caminho; não impede que dois namespaces lógicos sejam configurados para o mesmo arquivo. O namespace do lock é constante (`SuricataOutbox`). | Teste de colisão deliberada: A/B com IDs distintos mas mesmo caminho, e A/B com caminhos distintos mas mesmo `event_id`; provar invariantes esperados. | Tornar a chave de namespace parte explícita do caminho/objeto e validar que ela é derivada do contexto autorizado, não de input arbitrário. |
| Memória/relatório por prefixo | `executar()` / `rodada/execucao.py:263-335` | Usa `destino_prefixo/memoria.json`, `outbox.json` e `ultima-rodada.json`; memória é gravada por CAS após o outbox. | O prefixo separa arquivos, mas não separa autorização, origem Canvas ou sessão. `destino_prefixo` é argumento interno e não carrega identidade de tenant. | Fixture A/B com mesma atividade e eventos diferentes; adulterar prefixo e verificar que o runtime recusa, em vez de ler/gravar o estado do outro. | Encapsular caminhos em um `InstanceContext` validado; não passar strings de prefixo soltas entre composição, execução e storage. |
| Objeto CAS de sessão | `SuricataSessionStorage`, `_resolve_session_object()` / `storage/cas.py:39-57,184-208` | Exige `session_object` explícito ou `SURICATA_WA_SESSION_OBJECT`; valida `gs://bucket/prefixo/...`, usa CAS e revalida geração após `cat`. | A classe aceita qualquer objeto GCS estruturalmente válido e não verifica que ele pertence ao `SURICATA_ESTADO_URI` ou a uma identidade. O mesmo processo pode ser apontado à sessão de outra instância. | Instanciar com estado A e sessão B; exigir rejeição. Testar também divergência entre argumento, env, bucket e prefixo. | Derivar o objeto de sessão do backend/tenant autorizado e rejeitar qualquer URI fora do namespace; manter a revalidação de geração. |
| Fachada `SessaoWhatsApp` | `SessaoWhatsApp`, `_nome_sessao()` / `storage/sessao.py:20-64` | Usa `whatsapp/auth.json` por padrão; quando recebe `gs://`, exige backend GCS, mesmo bucket e caminho exatamente igual a `prefixo/whatsapp/auth.json`. | Este é um seam forte de namespace, mas só funciona quando toda composição passa por essa fachada. O fallback local `whatsapp/auth.json` não carrega identidade e pode ser compartilhado por erro de raiz. | Testar duas instâncias no mesmo bucket com prefixes A/B, ausência de prefixo, backend local e env `SURICATA_WA_SESSION_OBJECT` trocado; testar que a classe direta e o bridge usam o mesmo contrato. | Remover fallback ambíguo no modo individual; carregar `InstanceContext` obrigatório e verificar que `prefixo`, bucket e sessão foram resolvidos pela mesma fonte. |
| Sessão durante envio | `WhatsAppBridge.enviar_lote()` / `integracao/bridge.py:25-62` | Lê snapshot, materializa auth em `TemporaryDirectory`, executa Node, lê credenciais alteradas e grava com geração esperada. | Não há lock de sessão entre read → uso do socket → write. Dois processos da mesma instância podem abrir a mesma sessão; um conflito CAS ocorre apenas depois de possível envio. Dois tenants que compartilhem objeto podem operar a mesma conta. | Concorrência real com dois bridges e runner controlado: ambos leem geração N, enviam, alteram auth e escrevem; verificar conflito, ausência de mistura e política de retry. | Lease/lock por sessão e identidade antes de abrir Baileys; conflito de credencial deve impedir retry cego e exigir reconciliação. |
| Contrato Python → Node | `_validar_entrada()` / `bridge.py:64-94`; `parseBatch()` / `whatsapp/enviar.mjs:19-40` | Python valida `message_id == message_id(grupo_jid,event_id)`; Node valida forma, unicidade e lote, mas não reconstrói a relação JID/evento. | Chamada direta ao Node pode aceitar um `message_id` válido para outro grupo; o isolamento depende de a ponte Python ser sempre a única entrada. | Teste Node direto com JID A e message ID gerado para B; teste Python e Node com dois lotes A/B intercalados. | Duplicar a validação semântica no contrato Node, ou tornar o Node não invocável fora de um envelope assinado/contextualizado. |
| Diretório de auth temporário | `_materializar()` / `bridge.py:190-211`; `validarAuthDir()` / `whatsapp/auth-dir.mjs:56-64` | Auth materializado fora do repo, com permissões restritas; `auth-dir` dentro do repo e symlink que resolve para o repo são rejeitados. | “Fora do repo” não significa tenant correto, dono correto ou isolamento entre processos; o caminho pode ser qualquer diretório externo autorizado pelo chamador. | A/B com diretórios externos trocados, symlinks/junctions e mesmo pai; provar que nenhum processo pode ler ou gravar auth de outro. | Usar diretório de runtime derivado de identidade autorizada, ACL mínima e lock por sessão; não aceitar caminho livre como autoridade. |
| Pareamento e inventário | `parear.mjs:130-195`, `listarGrupos()`, `caminhoGrupos()` / `parear.mjs:96-126` | Pareamento exige modo local + TTY, bloqueia Cloud/CI, grava `grupos.json` ao lado do auth dir e só remove após confirmação. | A guarda reduz exposição operacional, mas não associa o pareamento a uma instância/tenant; `grupos.json` pode ser confundido ou selecionado por operador errado. | Parear A/B em diretórios irmãos, trocar `--auth-dir` e confirmar que inventários, sessões e destinos não se cruzam; testar reuso após logout. | Emitir e consumir um identificador de instância/tenant no artefato de pareamento e registrar associação autorizada; impedir seleção manual fora dessa associação. |

## Cobertura existente e lacunas principais

Há cobertura útil para validação de configuração (`test_config_arquivo.py`,
`test_multidestino.py`), concorrência e fencing do outbox
(`test_outbox_concurrency.py`), revalidação CAS
(`test_storage_cas_revalidation.py`), composição do runtime
(`test_runtime.py`) e guardas do pareamento (`test_parear_security.mjs`).

Não encontrei, no escopo lido, um teste end-to-end de **duas instâncias
independentes** com identidade, estado, sessão, outbox, lease, JID e runner
simultâneos. Também não há teste que prove isolamento contra adulteração de
`SURICATA_ESTADO_URI`/`SURICATA_WA_SESSION_OBJECT`, nem corrida de dois bridges
sobre a mesma sessão. Os testes atuais provam concorrência e separação por
prefixo em vários pontos; não provam isolamento de tenant individual.

## Ordem recomendada para uma implementação futura

1. Fixar um `InstanceContext`/tenant opaco e a política que o resolve; negar
   contexto ausente ou ambíguo.
2. Derivar e validar juntos estado, prefixo, sessão, JID, token e limites; não
   aceitar qualquer um deles como autoridade isolada de env/argv.
3. Decidir lease global versus lease por instância e implementar o teste de
   concorrência correspondente.
4. Adicionar testes A/B de não-vazamento para leitura, escrita, retry, erro,
   dead-letter, logs e pareamento; depois testar GCS/Cloud Run com canário sem
   envio.
5. Só então tratar consentimento, revogação, retenção e operação individual;
   formato válido de JID ou sucesso de ACK não substitui esses controles.

**Estado:** DRAFT / NÃO IMPLEMENTADO. Nenhum código foi alterado como parte
desta auditoria.
