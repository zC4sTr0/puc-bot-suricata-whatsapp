# Contratos do runtime

Este documento descreve interfaces observáveis que uma refatoração deve preservar. Ele não é configuração de produção.

## Entrada

- `python -m suricata --mode shadow` é a probe local sem efeitos.
- `python -m suricata --mode rodada` é o caminho funcional; configuração vem do ambiente.
- `sentinela` exige `--config`; `grupos` é diagnóstico; `teste-envio` tem efeito externo.
- `demo` roda a rodada offline com fixtures congeladas e entrega desligada; não exige variáveis.
- `--help`/`-h` imprime os modos e termina em zero; tem precedência sobre o parse.
- Argumentos inválidos e configuração inválida terminam com código não-zero e erro sanitizado; as mensagens de erro são acionáveis (apontam `--help`, `config.example.json` ou diretório local como estado) e os valores exatos estão congelados em `suricata/tests/test_cli_contract.py` e `test_emit_schema.py`.

## Fronteira Python → Node

- Python envia um lote JSON por stdin ao processo Node.
- O Node não possui estado de negócio nem decide elegibilidade.
- A resposta de stdout é JSON sanitizado; stderr não deve carregar sessão, token, QR, JID ou payload pessoal.
- Uma mensagem só se torna `sent` após ACK compatível; timeout, logout ou resposta inválida não pode ser tratado como sucesso.

## Estado e tempo

- O caminho da rodada preserva `pending → in_flight → sent`; falha/timeout não confirma envio.
- O corte é em `America/Sao_Paulo`: mensagens comuns não atravessam 21:00–06:59.
- Lease, geração/CAS, memória e outbox são contratos de concorrência; adapters concretos não podem vazar para as regras puras.
- Existem DOIS leases com contratos distintos: `suricata/lease_rodada.py` (ativo na rodada; payload ilegível é abandonado, nunca um lease preso) e `suricata/legacy/lease.py` (legado; payload ilegível é fail-closed com `RuntimeError`). Não unificar sem snapshot de paridade; ambos congelados por `test_lease_rodada.py` e `test_lease.py`.
- `domain.EXCLUIDAS` e `coleta.EXCLUIDAS` têm o mesmo nome com conjuntos e propósitos diferentes (fronteira pública vs. filtro de coleta); não são duplicatas — mudar um não autoriza mudar o outro.
- Coleta parcial não é ausência confirmada.

## Configuração e segredo

- `SURICATA_*` vem do ambiente/Secret Manager; o Git contém apenas placeholders.
- Sessão, QR, auth, token, JID real, banco e estado operacional ficam fora do repositório e da imagem.
- `SURICATA_ENTREGA` precisa ser explicitamente `ligada` para permitir entrega.

## Regra para refatorar

Uma fatia estrutural só pode ser aceita se preservar stdout/stderr, exit code, JSON, texto, IDs, ordenação, estados, ACK, retries, chamadas externas e arquivos de empacotamento. Quando não houver baseline old/new executável, a paridade fica `não comparável`, nunca presumida.
