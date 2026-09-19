# Auditoria de horários e casos — domínio Suricata

**Escopo:** rastreamento somente-leitura de coleta → planejamento → memória/outbox → bridge/ACK. Não foram executados Job, Canvas real, cloud ou WhatsApp real. Os testes executados usam fixtures, armazenamento temporário e, no E2E, stub Node local.

**Baseline auditado:** branch `docs/readme-rodada-agenda`, HEAD `e20049f` (`ci: trigger on root markdown changes`).

## Veredito resumido

O caminho vertical está implementado e coberto para o corte das 21:00, novidades do mesmo dia/dia seguinte, pendências overnight autorizadas, deduplicação por `event_id`, ACK inválido/ausente, falhas de coleta e múltiplos destinos. A regra temporal é BRT via `America/Sao_Paulo`.

As lacunas abaixo são de **matriz de teste/documentação**, não comportamento inferido como defeito: não há teste dedicado para o limite exato `12:00:00`, para `18:00:00` como fronteira de entrada da véspera, para `07:00:01` como saída da janela de autorização matinal, nem para a composição de todos os horários com dois destinos simultaneamente. O comportamento nesses pontos é derivado do código citado e não foi promovido a aceitação por teste dedicado.

## Rastro do fluxo

1. **Coleta:** `suricata/rodada/coleta.py:35-65` consulta cursos, assignments e announcements; falha de todas as ofertas levanta `ColetaIndisponivel` (`:51-52`); falhas parciais são acumuladas (`:43-47`, `:65`). `anuncios=None` significa rota de anúncios indisponível, não ausência (`:32`, `:53-64`).
2. **Entrada da rodada:** `suricata/rodada/execucao.py:263-330` registra a coleta e falhas (`:284-300`), carrega memória fail-closed (`:196-213`), planeja sobre cópia (`:216-229`) e só grava memória depois da durabilidade do outbox (`:313-324`).
3. **Planejamento:** `suricata/dominio/planejamento.py:59-140` cria eventos novos/mudanças/lembretes e atualiza memória planejada. A janela da novidade é calculada em BRT por `_inicio_janela_novidade` (`:152-180`) e `janela_novidade` (`:183-202`). Aviso de prova é `12:00–17:59` (`:204-222`); véspera é `18:00–22:59` (`:224-257`).
4. **Corte:** `suricata/dominio/corte_rodada.py:17-26` define corte inclusivo a partir de `21:00:00` e autorização matinal somente no minuto `07:00` (`:23-26`). A autorização overnight valida atividade, datas, tipo e fechamento (`:29-41`, delegando a `planejamento.py:262-282`).
5. **Outbox:** `suricata/rodada/execucao.py:113-193` registra, recupera `in_flight`, corta/expira pendentes, reivindica somente eventos disponíveis e persiste `in_flight` antes do efeito externo (`:164-182`). `suricata/storage/outbox.py:89-110` deduplica por `event_id`; `:134-167` aplica fencing e só aceita `sent` com ACK/status; `:186-216` faz o corte atômico; `:218-238` restringe transições.
6. **Memória:** `suricata/dominio/memoria_rodada.py:17-62` consome a marca somente para evento durável; ACK não é necessário para durabilidade, mas sessão de ponte em erro não consome (`:23-32`).
7. **Bridge/ACK:** `suricata/integracao/bridge.py:41-62` valida a entrada, materializa sessão temporária e só persiste sessão alterada em sessão `ok`; `_sucesso_valido` exige cardinalidade, pares `event_id/message_id`, `ack=true` e status inteiro `>=2` (`:156-188`). A reconciliação Python repete essa exigência e devolve `pending` em qualquer dúvida (`suricata/rodada/execucao.py:88-110`).
8. **Destinos:** `suricata/rodada/execucao.py:338-371` coleta uma vez e processa somente destinos elegíveis; `suricata/rodada/config.py:21-34` usa janela BRT; `suricata/rodada/config.py:124-147` valida IDs/JIDs e janelas. Cada destino possui prefixo/outbox/memória próprios.

## Matriz BRT de horários e casos

Legenda: **OK** = há teste direto do caso; **PARCIAL** = comportamento coberto por janela próxima, não pelo limite solicitado; **LACUNA** = não há teste dedicado encontrado.

| Horário BRT | Evento do mesmo dia | Evento do dia seguinte | Pendências / duplicatas | Estado da evidência |
|---|---|---|---|---|
| **07:00:00** | Novidade relevante do dia pode ser imediata; `em_silencio` termina às 07:00. | Novidade descoberta entre 07:00 e 11:59 é imediata (`planejamento.py:174-180`, `:192-202`). | É a janela que pode validar autorização overnight persistida; pendência comum anterior ao corte é expirada, enquanto evento atual da rodada pode ser preservado (`execucao.py:143-148`). | **OK**: `test_corte_21h.py:81-83,95-97`; `test_corte_21h_current_event.py:37-58`; **LACUNA**: não há teste de `07:00:00` com aviso de prova e múltiplos destinos juntos. |
| **12:00:00** | Evento que envolve hoje continua alertável/imediato (`publico.py:90-104`). | Prova/quiz de amanhã entra na janela do aviso extra; novidade geral de amanhã espera 18:00 (`planejamento.py:204-222`, `:174-180`). | `avisos_prova[data]` impede nova decisão para a mesma data; duplicata de evento é barrada por `event_id` no outbox (`outbox.py:98-103`). | **PARCIAL**: `test_discricao.py:80-82` usa 12:00 e `test_janelas_novidade.py:124-132` usa 13:00; **LACUNA** de fronteira explícita `12:00:00` com prova + novidade geral no mesmo ciclo. |
| **18:00:00** | Evento do mesmo dia segue imediato enquanto antes de 21:00 (`planejamento.py:163-180`; `publico.py:81-87`). | Véspera passa a ser elegível; novidade de amanhã descoberta a partir de 18:00 aguarda 07:00 (`planejamento.py:224-257`, `:174-180`). | Véspera usa `vesperas[data]` como decisão única e não repete itens já avisados ao meio-dia (`planejamento.py:233-253`). | **PARCIAL/OK funcional**: há testes em 18:00 (`test_janelas_novidade.py:79-84`, `:158-161`) e véspera (`test_discricao.py:72-82`); **LACUNA** como teste de fronteira `18:00:00` e composição prova+atividade. |
| **21:00:00** | Corte inclusivo: novidade do dia não é enviada; evento comum pendente é expirado. | Quiz/avaliação claramente do dia seguinte, descoberto nesta rodada, pode ser persistido para 07:00; não é enviado à noite (`planejamento.py:262-282`, `corte_rodada.py:29-41`). | Pendência comum não atravessa; flag persistida forjada não autoriza; `in_flight` é devolvido/expirado sem envio matinal (`outbox.py:203-216`). | **OK**: `test_corte_21h.py:70-83,109-117`; `test_janelas_novidade.py:134-151`; `test_corte_21h_adversarial.py:77-115`; limite inclusivo em `test_corte_compatibility.py:31-43`. |
| **21:00:01** | Continua sob corte; evento do mesmo dia é descartável, sem chamada à ponte. | Evento do dia seguinte autorizado continua `pending` para 07:00. | Revalidação do relógio entre claim e ponte impede envio após o corte; duplicata não cria novo registro. | **OK**: `test_corte_21h.py:58-68,85-97`; `test_corte_21h_adversarial.py:55-75`; **LACUNA**: não há teste dedicado de autorização válida especificamente em `21:00:01` (há caso equivalente em `21:01`). |

### Casos por data

| Caso | Comportamento confirmado | Referências / testes |
|---|---|---|
| Mesmo dia, atividade descoberta antes de 21h | Imediata se `decidir()` classifica como `alertar`; expirada se já fechada. | `suricata/dominio/publico.py:90-104`; `suricata/dominio/planejamento.py:83-125`; `test_janelas_novidade.py:114-132`. |
| Mesmo dia, descoberta após 21h | Não cria envio; corte expira evento não autorizado. | `suricata/dominio/planejamento.py:163-170`; `test_corte_21h.py:58-68`. |
| Dia seguinte, descoberta 07:00–11:59 | Imediata, sem duplicar a véspera das 18h. | `suricata/dominio/planejamento.py:174-180,192-202`; `test_janelas_novidade.py:69-84`. |
| Dia seguinte, descoberta 12:00–17:59 | Aguarda véspera das 18h; prova/quiz também pode gerar aviso extra ao meio-dia, uma decisão por data. | `suricata/dominio/planejamento.py:178-180,204-222`; `test_discricao.py:80-87`. |
| Dia seguinte, descoberta 18:00–20:59 | Fica pendente para 07h; a véspera não duplica o item já tratado no ciclo. | `suricata/dominio/planejamento.py:174-180,224-257`; `test_janelas_novidade.py:86-112`. |
| Dia seguinte, descoberta 21:00/21:00:01 | Não envia à noite; quiz/avaliação de janela do dia seguinte pode atravessar até 07h. | `suricata/dominio/planejamento.py:262-282`; `test_janelas_novidade.py:134-151`; `test_corte_21h.py:85-97`. |
| Pendência antiga antes do corte | Não é artificialmente carregada para a manhã; expira no corte. | `suricata/storage/outbox.py:186-216`; `test_corte_21h_adversarial.py:77-115`. |
| Pendência `in_flight` após crash | Recupera para `pending`, mas o fluxo do corte pode expirar; resultado tardio perde pelo `attempt_id`. | `suricata/storage/outbox.py:153-179`; `test_outbox.py:31-53`; `test_corte_21h_adversarial.py:103-115`. |
| Duplicata idêntica | Reutiliza o registro existente; não cria segundo evento. | `suricata/storage/outbox.py:96-110`; `test_outbox.py:18-29`; `test_e2e_rodada_offline.py:165-176`. |
| Mesmo `event_id` com conteúdo diferente | A API do outbox rejeita; a fachada de registro da rodada preserva o registro existente e não trava por mudança de texto (`execucao.py:69-78`). | `test_outbox.py:55-59`; `suricata/rodada/execucao.py:69-75`. **Lacuna documental:** não há teste específico da combinação “deploy muda texto + evento já existente” no caminho `executar`. |
| Falha de ACK/timeout | Estado volta a `pending`, não `sent`; dead-letter sanitizada é tentativa adicional e não derruba a rodada. | `suricata/rodada/execucao.py:88-110,183-192`; `test_e2e_rodada_offline.py:178-204`; `test_falhas.py:113-130`. |
| ACK válido | Exige sessão `ok`, mesmo `message_id`, `ack=true`, status inteiro `>=2`; então marca `sent`. | `suricata/integracao/bridge.py:156-188`; `test_e2e_rodada_offline.py:148-163`; `test_whatsapp_ack.mjs:10-38`. |
| Múltiplos destinos | Uma coleta; somente destinos elegíveis; estado e outbox separados por prefixo; `message_id` muda por JID. | `suricata/rodada/execucao.py:338-371`; `suricata/rodada/config.py:30-34`; `test_multidestino.py:27-80`. |
| Falha total de coleta | Não planeja nem entrega; retorna código 3 e estado `coleta_indisponivel`. | `suricata/rodada/coleta.py:35-38,51-52`; `suricata/rodada/execucao.py:283-288,350-353`; `test_rodada.py:183-190` / `test_operacao_fail_closed.py:75-89`. |
| Falha parcial de coleta | Continua com dados disponíveis, registra oferta/rota falha e estado parcial; não trata falha como ausência. | `suricata/rodada/coleta.py:43-47,53-65`; `suricata/rodada/execucao.py:289-300,323-324`; `test_falhas.py:139-155`. |
| Memória inválida | Interrompe antes de planejar/enviar; não altera memória. | `suricata/rodada/execucao.py:196-213,302-305`; `test_execucao_fases_compatibility.py:51-66`; `test_operacao_fail_closed.py:91-107`. |

## Lacunas verificáveis

1. **L1 — fronteira do meio-dia:** falta teste dedicado em `12:00:00` que diferencie `12:00–17:59` de `11:59:59`, cobrindo simultaneamente prova/quiz de amanhã e atividade geral de amanhã. A regra está em `suricata/dominio/planejamento.py:204-222` e `suricata/dominio/planejamento.py:174-180`.
2. **L2 — fronteira das 18h:** falta teste dedicado em `18:00:00` contra `17:59:59`, incluindo véspera vazia, prova já avisada às 12h e novidade descoberta no mesmo ciclo. A janela está em `suricata/dominio/planejamento.py:224-257`.
3. **L3 — minuto matinal:** `janela_manha()` aceita qualquer segundo de `07:00`, mas não `07:01` (`suricata/dominio/corte_rodada.py:23-26`). Há teste de `07:00`, não de `07:00:01`/`07:01:00` para autorização persistida e envio posterior.
4. **L4 — matriz horária × multidestino:** os testes de múltiplos destinos usam madrugada/10:00 e não combinam `07:00`, `12:00`, `18:00`, `21:00:00` e `21:00:01` com destinos elegíveis/não elegíveis. O processamento por destino está em `suricata/rodada/execucao.py:356-365`.
5. **L5 — erro de conteúdo em duplicata no caminho completo:** existe teste unitário da rejeição no `Outbox`, mas não do comportamento deliberado de `suricata/rodada/execucao.py:69-75`, que conserva o registro antigo quando o mesmo `event_id` chega com texto diferente.
6. **L6 — anúncio indisponível × horários:** há contrato de `anuncios=None` (`suricata/rodada/coleta.py:32,53-64`) e testes de falha parcial, mas não uma matriz dedicada mostrando que `12:00`/`18:00` não transformam rota de anúncios indisponível em “sem anúncios”.

## Testes executados nesta auditoria

Comando: `python -m pytest -q suricata/tests/test_corte_21h.py suricata/tests/test_corte_21h_adversarial.py suricata/tests/test_corte_21h_current_event.py suricata/tests/test_corte_compatibility.py suricata/tests/test_janelas_novidade.py suricata/tests/test_memoria_compatibility.py suricata/tests/test_outbox.py suricata/tests/test_multidestino.py suricata/tests/test_falhas.py suricata/tests/test_e2e_rodada_offline.py`

Resultado real: **60 passed in 6.01s**.

## Não verificado por escopo

- Nenhum Job foi executado.
- Nenhuma consulta Canvas/cloud foi feita.
- Nenhuma sessão WhatsApp real, credencial ou segredo foi lido.
- Não há prova de comportamento do Scheduler externo de 10 minutos além da validação de formato em `suricata/rodada/config.py:138-144`.
- O E2E executado prova o contrato contra stub Node local, não conectividade, timing ou ACK de servidor WhatsApp real.

**Conclusão:** para o caminho offline e o contrato atual, a cadeia está coberta e os testes passam; não é possível declarar validação de produção/cloud/WhatsApp real dentro do escopo imposto.
