# Pacote WhatsApp do Suricata

Este diretório é autocontido para instalação e testes Node:

```bash
npm ci --ignore-scripts --omit=dev
npm test
```

`npm test` é o contrato Node agregado: executa os cinco testes em
`../tests/*.mjs` e os testes do pacote em `./tests/*.mjs`. Para executar apenas
o pacote autocontido, use `npm run test:package`. Nenhum desses comandos usa
sessão, credencial ou arquivo gerado.

## Bloqueio conhecido: libsignal

O Baileys 6.7.24 declara `libsignal` como dependência Git. O lockfile preserva
o commit já resolvido (`bcea72df9ec34d9d9140ab30619cf479c7c144c7`) e registra a
origem GitHub. Não foi substituído por URL, hash ou versão inventados: não há
uma alternativa segura já disponível neste pacote para remover essa dependência.

Assim, uma instalação reproduzível ainda requer rede e acesso ao repositório
GitHub durante `npm ci`; `--ignore-scripts` não elimina essa resolução Git.
Se o ambiente não puder acessar o GitHub, a instalação fica bloqueada e deve
ser tratada como problema de fornecimento da dependência, não contornada com
um pacote ou hash não verificado.
