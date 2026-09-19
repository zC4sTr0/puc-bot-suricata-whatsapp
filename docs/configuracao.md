# Configuração pública

Esta é a referência canônica das variáveis do runtime. Ela usa somente valores
sintéticos. Segredos, sessão WhatsApp, JIDs, tokens, buckets e caminhos reais
ficam fora do Git e são fornecidos pelo ambiente autorizado.

## Antes de configurar

- **Python é o runtime do produto:** execute `python -m suricata` e configure a
  rodada com as variáveis `SURICATA_*` da tabela abaixo.
- **Node é um adaptador de WhatsApp e um runtime de testes:** instale as
  dependências em `suricata/whatsapp` com `npm ci` e execute `node --test` ali.
  Node não substitui o entrypoint Python.
- **Local** usa diretórios temporários e fixtures; não reutilize a sessão de
  produção.
- **Produção** usa Secret Manager para segredos, GCS para estado autorizado e
  Cloud Run Job para uma execução finita. Cloud Run não deve receber uma sessão
  copiada dentro da imagem.
- `SURICATA_ENTREGA` fica desligada por padrão. O valor exato `ligada` é um
  gate de efeito externo, não uma opção de diagnóstico.

## Tabela canônica de variáveis

“Público” significa que o **nome** da variável e a sua semântica podem aparecer
na documentação. Não significa que o valor seja público.

| Variável | Obrigatória | Segredo? | Escopo | Exemplo sintético | Efeito e validação |
|---|---:|---:|---|---|---|
| `SURICATA_CANVAS_TOKEN` | sim em `rodada` | sim | Python / local e produção | `<token-canvas-fora-do-repo>` | Token de leitura do Canvas; ausente faz a rodada falhar fechada. Em produção, vem do Secret Manager. Nunca logar, versionar ou passar por argv. |
| `SURICATA_ESTADO_URI` | sim em `rodada` | não, mas é sensível | Python / local e produção | `./estado-local` ou `gs://<bucket>/<prefixo>` | Seleciona diretório local ou namespace GCS para memória, lease e outbox. URI ausente ou namespace incorreto impede a rodada. |
| `SURICATA_ENTREGA` | não | não | Python / todos | `desligada` | Somente `ligada` habilita a ponte de WhatsApp. Qualquer outro valor mantém a entrega desligada; o gate humano continua necessário. |
| `SURICATA_GRUPO_JID` | não | não, mas é identificador operacional | Python / ambiente autorizado | `<grupo-sintetico>@g.us` | Destino legado único. Deve ter formato de JID válido; o formato não comprova que a identidade do grupo foi confirmada. Nunca publicar valor real. |
| `SURICATA_DESTINOS_JSON` | não | não, mas contém destinos | Python / ambiente autorizado | `[{"id":"exemplo","jid":"<jid>@g.us"}]` | Lista de destinos com `id`, `jid` e `janela_brt` opcional. Deve ser JSON válido, sem IDs duplicados ou caminhos inseguros. |
| `SURICATA_DESTINOS` | não | não, mas contém destinos | Python / compatibilidade | `<json-de-destinos>` | Nome legado aceito como alternativa de `SURICATA_DESTINOS_JSON`. Prefira o nome explícito novo em configurações novas. |
| `SURICATA_CONFIG` | não | pode conter destinos | Python / local e produção controlada | `./config-local.json` | Arquivo JSON externo com `destinos` e, opcionalmente, `lease_minutos`. O arquivo é a base; variáveis de destino do ambiente têm precedência. Não colocar no repo se tiver valores reais. |
| `SURICATA_LEASE_MINUTOS` | não | não | Python / rodada | `6` | Duração do lease; o padrão efetivo é `6`. O módulo converte o texto para `int` no import e rejeita valores não numéricos, zero e negativos. O campo homônimo de `SURICATA_CONFIG` só é validado e não é aplicado. |
| `SURICATA_CURSOS_EXCLUIDOS` | não | não | Python / coleta Canvas | `104959,292184` | IDs Canvas separados por vírgulas. Ausente usa o padrão legado `104959`; a validação rejeita lista vazia, itens vazios, IDs não numéricos e duplicatas. |
| `SURICATA_WA_SESSION_OBJECT` | não na rodada; exigida pelo adaptador CAS direto | contém/aponta para sessão | Python / estado WhatsApp | `gs://<bucket>/<prefixo>/whatsapp/auth.json` | Na rodada, ausente usa `whatsapp/auth.json` dentro do namespace de `SURICATA_ESTADO_URI`. Quando presente, `SessaoWhatsApp` exige backend GCS e correspondência exata de bucket/prefixo/objeto; outro namespace falha fechado. O `SuricataSessionStorage` direto exige uma URI explícita válida. |
| `SURICATA_WA_AUTH_DIR` | não na rodada; sim para `enviar.mjs`/`verificar.mjs` sem `auth_dir` no stdin | sim, contém sessão | Node / comandos diretos e operação local autorizada | `C:/caminho/fora-do-repo/.wa-auth` | `enviar.mjs` e `verificar.mjs` usam o diretório externo; o pareamento recebe `--auth-dir`. A ponte Python da rodada não lê a variável: materializa a sessão em diretório temporário e passa `auth_dir` pelo stdin. O adaptador rejeita diretórios dentro do clone. |
| `SURICATA_GCLOUD_BIN` | não | não | Python / testes de armazenamento | `gcloud` | Permite fixar o executável usado pelo adaptador de sessão. Normalmente não é necessário; em produção, mantenha o binário aprovado e não aceite caminho arbitrário. |
| `SURICATA_STUB_SCENARIO` | não | não | Node / testes | `success` | Seleciona cenário da ponte stub versionada. É ferramenta de teste, não configuração de produção e não envia WhatsApp. |
| `SURICATA_WHATSAPP_LOCAL` | não | não | Node / local interativo | `1` | Habilita explicitamente caminhos locais permitidos pelo adaptador. CI e Cloud Run devem permanecer fora desse modo; isso não fornece uma sessão real. |

### Precedência e falha fechada

1. `SURICATA_CONFIG`, quando presente, fornece a base de destinos.
2. `SURICATA_GRUPO_JID`, `SURICATA_DESTINOS_JSON` ou o nome legado de destinos
   sobrepõem a base do arquivo.
3. `SURICATA_LEASE_MINUTOS` sempre vem do ambiente; o campo homônimo do arquivo
   pode ser validado, mas não substitui a variável. Isso evita que uma duração
   pareça aplicada quando não foi.
4. Em conflito, JSON inválido, JID inválido, ID duplicado, caminho inseguro,
   lease não inteiro positivo ou namespace de sessão divergente, o runtime recusa a
   operação. Não substitua o erro por uma configuração vazia.

As regras de domínio e segurança não são variáveis: janela BRT, confirmação do
WhatsApp antes de marcar `sent`, CAS, limites de texto/JID, lease e idempotência
continuam contratos do código e dos testes.

## Configuração local segura

O caminho local deve ser reversível e sem efeitos externos. Exemplo de smoke
test da CLI, com estado descartável e token fictício:

```bash
SURICATA_ESTADO_URI=./tmp-estado \
SURICATA_CANVAS_TOKEN=falso \
SURICATA_ENTREGA=desligada \
python -m suricata --mode rodada
```

Para o caminho mínimo sem coleta externa:

```bash
python -m suricata --mode shadow
```

Para o adaptador Node:

```bash
cd suricata/whatsapp
npm ci
node --test
```

Use uma pasta temporária fora do repositório para qualquer sessão local. O
exemplo acima não prova acesso ao Canvas, GCS, WhatsApp ou entrega; ele só
exercita o caminho permitido pelo ambiente fornecido.

## Testes e CI

A separação esperada é:

| Camada | Comando | O que demonstra |
|---|---|---|
| Sintaxe Python | `python -m compileall -q suricata` | módulos Python compilam |
| Suite Python | `python -m pytest -q` | contratos Python e fixtures locais |
| Adaptador Node | `cd suricata/whatsapp && npm ci && node --test` | contratos do adaptador e segurança local |
| CLI segura | `python -m suricata --mode shadow` | entrypoint sem transporte externo |
| Imagem | fluxo de build documentado em [`deploy-gcp.md`](deploy-gcp.md) | empacotamento remoto e digest, após autorização |

Uma suite verde não prova sessão WhatsApp válida, destino correto, IAM, acesso a
um bucket real, coleta ao vivo ou entrega. Esses fatos exigem read-back e gates
operacionais separados.

## Configuração em produção

- Injete `SURICATA_CANVAS_TOKEN` por Secret Manager; não use `--set-env-vars`
  para o valor do segredo.
- Defina `SURICATA_ESTADO_URI` para um namespace GCS confirmado e exclusivo da
  aplicação. Separe canário e produção.
- `SURICATA_WA_SESSION_OBJECT` pode ser omitida: na rodada, a sessão usa
  `whatsapp/auth.json` dentro do namespace de `SURICATA_ESTADO_URI`. Se for
  definida, use exatamente o objeto correspondente desse namespace; não use
  fallback para outro bucket ou produto.
- Comece com `SURICATA_ENTREGA=desligada`, sem destinos reais, no canário.
- Só no corte autorizado configure destino confirmado e `ligada`, seguindo o
  [gate de deploy](deploy-gcp.md#gate-3--corte-controlado).
- Faça read-back de env não secreto, args, imagem por digest, identidade, IAM,
  timeout, retries e URI de estado. Segredos devem ser verificados apenas pela
  presença da referência correta, nunca imprimindo o valor.

## O que não entra nesta configuração pública

Não publique arquivos `.env` preenchidos, tokens, QR codes, `auth.json`, JIDs,
URLs com credenciais, nomes reais de projeto/bucket/Job/Scheduler, digests de
produção, IDs de Cloud Build, contas de serviço, dumps Canvas ou logs com
payload. A documentação pública descreve contratos; o operador autorizado
preenche valores reais no sistema de deploy e registra a evidência em local
privado.
