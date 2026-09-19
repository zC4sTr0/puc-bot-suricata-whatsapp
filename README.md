<div align="center">

<img src="docs/img/banner.svg" width="640" alt="Suricata" />

**Avisos acadêmicos coletivos no WhatsApp** — o bot que acompanha o Canvas da turma e avisa o grupo na hora certa, sem nunca expor nada pessoal.

[![CI](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml/badge.svg)](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff&logoColor=white)](ruff.toml)
[![Dependencies: 0](https://img.shields.io/badge/dependencies-0-brightgreen?logo=python&logoColor=white)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-285%20passing-brightgreen)](suricata/tests)

[Começar](#-quickstart) · [Como funciona](#-como-funciona) · [WhatsApp](#-sincronizando-com-o-whatsapp) · [Configuração](#%EF%B8%8F-configuração) · [Deploy](#-deploy-no-google-cloud) · [Trilha do estudante](#-trilha-do-estudante)

</div>

---

## ✨ O que é

A Suricata consulta **atividades públicas** do Canvas (provas, listas, quizzes), identifica o que é novidade para a turma e envia **avisos coletivos** no grupo autorizado do WhatsApp. Mensagens só são marcadas como enviadas **depois** do ACK do servidor — reenvio nunca duplica. Nunca publica notas, frequência ou qualquer situação individual.

## 🚀 Quickstart

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp && cd suricata-whatsapp
```

**1. Sem instalar nada** (Python 3.11+ puro, zero `pip install`):

```bash
python -m suricata --mode demo
```

Saída: as mensagens que *seriam* enviadas, com relatório completo — tudo offline, relógio congelado, entrega desligada. É o bot inteiro funcionando na sua máquina em segundos.

**2. Suíte completa** (o outro comando é só a ponte Node):

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
python -m pytest -q
```

**3. Um comando que valida tudo** (ambiente + matriz inteira):

```bash
python scripts/bootstrap.py
```

## 🧠 Como funciona

```mermaid
flowchart LR
    A["☁️ Cloud Scheduler<br/>a cada 10 min"] --> B["⚙️ rodada<br/><code>python -m suricata --mode rodada</code>"]
    B -->|"GET apenas leitura"| C["📚 Canvas<br/>dados públicos"]
    C --> D["🧠 planejamento<br/>novidades · janelas BRT · corte 21h"]
    D --> E[("🗄️ estado<br/>memória · lease · outbox")]
    E --> F["🌉 ponte Node<br/>Baileys"]
    F --> G["💬 WhatsApp<br/>grupo da turma"]
    G -->|"✅ ACK"| E
```

**O ciclo acima é a "rodada"**: a rodada é uma volta completa do bot — acorda, consulta o Canvas, decide o que é novidade, grava no estado e (só se tudo estiver liberado) envia. Ela roda a cada 10 minutos em produção e também localmente com `--mode rodada`. É o único caminho que envia mensagens.

Três invariantes de segurança que o código inteiro respeita:

| Invariante | Como |
|---|---|
| **fail-closed** | Sem config, estado, lease ou ACK → nada é enviado. `SURICATA_ENTREGA` só envia com o valor exato `ligada` |
| **ACK antes de `sent`** | Sem ACK do servidor a mensagem volta para `pending` e é reenviada com o **mesmo** `message_id` (idempotência) |
| **só dados coletivos** | A fronteira Canvas admite apenas campos públicos; notas e dados individuais nunca atravessam |

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> in_flight : claim (antes do envio)
    in_flight --> sent : ACK válido
    in_flight --> pending : falha/timeout/logout
    pending --> expirado : corte 21h
    sent --> [*]
    expirado --> [*]
```

## 💬 Sincronizando com o WhatsApp

A sessão do WhatsApp vive **fora do repo** (nunca versionada, nunca na imagem):

1. **Parear** (operação humana, terminal local): `node suricata/whatsapp/parear.mjs --auth-dir <diretório-fora-do-repo>` — leia [`suricata/whatsapp/README.md`](suricata/whatsapp/README.md) para o fluxo completo.
2. A ponte Node usa `SURICATA_WA_AUTH_DIR` para encontrar a sessão em produção (materializada do GCS via CAS, nunca copiada).
3. Confirme o JID do grupo antes de qualquer entrega real.

O detalhamento de cada etapa está no [guia](docs/guia.md).

## ⚙️ Configuração

Tudo por variáveis de ambiente — veja [`.env.example`](.env.example) comentado. O essencial do modo `rodada`:

| Variável | Obrigatória | O que faz |
|---|---|---|
| `SURICATA_CANVAS_TOKEN` | ✅ | token de acesso à API do Canvas (nunca no repo) |
| `SURICATA_ESTADO_URI` | ✅ | estado da rodada: **diretório local** ou `gs://…` |
| `SURICATA_ENTREGA` | — | `ligada` habilita envio; **default: desligada** |
| `SURICATA_GRUPO_JID` | — | JID do grupo destino (`…@g.us`) |
| `SURICATA_DESTINOS_JSON` | — | múltiplos destinos com janela própria |

<details>
<summary><b>Todas as variáveis</b> (lease, auth, destinos)</summary>

Ver [`.env.example`](.env.example) — cada linha documenta obrigatória/opcional, valor de exemplo seguro e quando importa. A referência completa de semânticas está em [`docs/interno/CONFIGURATION.md`](docs/interno/CONFIGURATION.md).
</details>

## ☁️ Deploy no Google Cloud

Produção = **um** Cloud Run Job (`suricata-rodada`) acionado por **um** Scheduler (`suricata-rodada-10min`), imagem por digest no Artifact Registry, estado em GCS — região `southamerica-east1`. Nada de segundo Scheduler, jamais.

```mermaid
flowchart TB
    R["🐙 GitHub<br/>main (merge squash)"] --> CB["🏗️ Cloud Build"]
    CB --> AR["📦 Artifact Registry<br/>imagem por digest"]
    AR --> JOB["⚙️ Cloud Run Job<br/>suricata-rodada"]
    SCH["⏰ Scheduler<br/>*/10 min"] --> JOB
    JOB --> GCS[("🗄️ estado<br/>bucket Suricata")]
    JOB --> WA["💬 WhatsApp"]
```

O passo a passo completo (build, canário sem entrega, corte controlado, rollback por digest) está em [`docs/deploy-gcp.md`](docs/deploy-gcp.md).

## 📣 Quero avisar algo que não está no Canvas

Prova marcada em aula, material postado fora do sistema, prazo que só você sabe: publique na **agenda manual** e o bot anuncia no grupo na janela certa, igual aos avisos do Canvas.

```bash
# 1. escreva um arquivo com o item (id único por item; data AAAA-MM-DD ou null)
# 2. veja o que seria publicado, sem publicar nada:
python deploy/publicar_agenda.py --arquivo minha-agenda.json --dry-run
# 3. publique (vai para o estado que a rodada lê):
python deploy/publicar_agenda.py --arquivo minha-agenda.json
```

Formato completo, exemplo pronto e regras (id único, tipos aceitos) em [`docs/guia.md`](docs/guia.md) — seção "Publicando itens manuais na agenda". Publicar duas vezes o mesmo `id` não duplica aviso.

## 🎓 Trilha do estudante

Progressiva, do zero ao domínio — cada nível diz o que você vê, o que isso prova e o próximo passo:

| Nível | Comando | Prova |
|---|---|---|
| 1 · testes verdes | `python -m pytest -q` | contratos congelados |
| 2 · probe | `python -m suricata --mode shadow` | pacote e entrypoint íntegros |
| 3 · rodada offline | `python -m suricata --mode demo` | o pipeline inteiro, sem efeitos |
| 4 · produção local | `SURICATA_ESTADO_URI=./tmp … --mode rodada` | estado real, entrega desligada |

Guia completo em [`docs/guia.md`](docs/guia.md).

## 🧰 Desenvolvimento

```text
suricata/
├── rodada/      orquestração (execucao, runtime, coleta, agenda_manual, config)
├── dominio/     regras puras (planejamento, publico, corte, memoria, lotes, relatorio)
├── integracao/  adaptadores (canvas, bridge)
├── storage/     persistência e concorrência (outbox, lease, CAS, GCS/local)
├── whatsapp/    ponte Node (Baileys)
└── tests/       suíte de contratos (pytest + unittest + node --test)
```

- **Matriz de validação** antes de qualquer PR: `python -m compileall -q suricata && python -m pytest -q && python -m unittest discover -s suricata/tests && node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs`
- **Lint**: `ruff check .` (config em [`ruff.toml`](ruff.toml))
- Como contribuir: [`CONTRIBUTING.md`](CONTRIBUTING.md) — fatias pequenas, teste de contrato antes do código, PR com provas.

## 📄 Licença

[MIT](LICENSE) — livre para estudar, usar e modificar.
