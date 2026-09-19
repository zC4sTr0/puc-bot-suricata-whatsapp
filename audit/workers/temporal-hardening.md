# Temporal hardening — fronteiras BRT

## Escopo

- Teste novo: `suricata/tests/test_temporal_hardening.py`.
- Nenhum runtime compartilhado foi alterado; `suricata/storage/cas.py` já estava
  modificado no workspace e permaneceu intocado.
- Os testes usam `corte_21h`, `janela_manha`, `janela_novidade`,
  `executar`/`executar_destinos` e os fakes públicos já existentes.

## Cobertura adicionada

- `07:00:00`, `07:00:01` e `07:01:00`: a exceção matinal vale nos dois
  primeiros momentos e deixa de valer às 07:01.
- `11:59:59`/`12:00:00`: novidade de amanhã muda de `imediata` para `18h`.
- `17:59:59`/`18:00:00`: muda de `18h` para `07h`.
- `20:59:59`/`21:00:00`/`21:00:01`: novidade do mesmo dia é imediata antes
  do corte e silenciosa a partir do corte.
- Dois destinos recebem a mesma novidade, com memória/outbox isolados.
- Falha na coleta de anúncios deixa a rodada `parcial`, mas não bloqueia um
  quiz nem fabrica um evento de anúncio.
- Novidade pendente atravessa 21:00 e é entregue às 07:00:01 uma única vez;
  uma rodada adicional às 07:01 não duplica `event_id` nem texto.

## Resultados verificados

- `python -m pytest suricata/tests/test_temporal_hardening.py -q`:
  **6 passed, 10 subtests passed**.
- `python -m pytest suricata/tests/test_lint.py::LintTests::test_ruff_check_verde_na_raiz suricata/tests/test_temporal_hardening.py -q`:
  **7 passed, 10 subtests passed**.
- Suíte, excluindo somente `test_demo.py`:
  **342 passed, 90 subtests passed**.

A execução integral de `suricata/tests` não ficou verde: `test_demo.py` detectou
arquivos `build/bdist.win-amd64/wheel/...` gerados no repositório durante a
execução. Esse é um gate de higiene do demo, não uma falha dos testes temporais;
o artefato deve ser tratado pelo agente integrador sem misturar a correção aqui.

## Ambiguidades comportamentais remanescentes

1. `janela_manha` é deliberadamente granular a minuto: 07:00:01 ainda é
   matinal, mas 07:01:00 não é. Isso é compatível com o Scheduler de 10 minutos,
   porém a regra de negócio não explicita se segundos devem ser ignorados ou se
   a janela deveria terminar exatamente às 07:01:00.
2. `Destino.elegivel` compara `HH:MM` por igualdade. Um destino configurado para
   `07:00` não é elegível às 07:01, mesmo que uma execução atrasada pudesse ser
   operacionalmente desejável.
3. O teste de anúncio indisponível confirma apenas o contrato atual de estado
   `parcial` e continuidade do quiz; não há decisão de produto sobre reprocessar
   anúncios perdidos ou sobre a retenção/expiração dessa lacuna.
4. A deduplicação comprovada é por `event_id`/outbox e texto determinístico do
   mesmo evento. Eventos distintos com textos idênticos continuam permitidos;
   não foi adotada deduplicação global por texto, pois isso poderia suprimir
   avisos legítimos.
