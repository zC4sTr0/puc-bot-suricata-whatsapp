# Segurança e privacidade

O PUC Bot da Suricata é independente e não oficial da PUC Minas. Esta política
explica como reportar riscos no código e como proteger dados durante testes e
operação.

## Nunca publique

Não envie em issues, pull requests, logs ou anexos:

- tokens, senhas, cookies, QR codes ou `auth.json`;
- JIDs, nomes de grupos, números de telefone ou capturas identificáveis;
- notas, frequência, submissões, tentativas ou mensagens privadas do Canvas;
- URLs assinadas, dumps, bancos de dados ou configuração real de cloud.

Se um segredo apareceu no Git ou em um log, pare de reutilizá-lo e peça ao
operador responsável para revogá-lo/rotacioná-lo. Não copie o segredo para uma
issue para “provar” o problema.

## Reportar vulnerabilidade

Use um canal privado dos mantenedores (por exemplo, a função privada de
security report do GitHub, se habilitada) e informe:

1. componente e versão/commit afetado;
2. comportamento observado e impacto;
3. reprodução mínima usando valores fictícios;
4. se houve contato com Canvas, WhatsApp, GCP ou dados reais — sem anexar os
dados;
5. uma sugestão de contenção, se houver.

Não execute pareamento, envio, leitura de produção, alteração de IAM ou deploy
para confirmar um relato sem autorização específica do titular do ambiente.

## Limites do projeto

O código local e os testes offline não provam segurança de uma conta do
WhatsApp, IAM correto, sessão válida, conformidade institucional ou entrega
real. O operador é responsável por autorização, retenção, acesso e remoção de
credenciais. O Canvas continua sendo a fonte oficial dos prazos e o bot não
substitui professor, coordenação ou secretaria.

Para entender os dados e limites do produto, leia
[`docs/privacidade.md`](docs/privacidade.md). Para contribuir com código,
leia [`CONTRIBUTING.md`](CONTRIBUTING.md).
