// Stub permanente da ponte WhatsApp (Node) para o E2E offline do Suricata.
//
// Contrato espelhado de suricata/bridge.py (_executar/_sucesso_valido):
//   stdin  (uma linha JSON): {"auth_dir": "...", "grupo_jid": "...",
//                            "mensagens": [{"event_id", "message_id", "texto"}]}
//   stdout (ÚLTIMA linha JSON): {"sessao": "ok"|"timeout"|"erro",
//                                "resultados": [{"event_id", "message_id",
//                                                "ack", "status", ...}]}
//
// A ponte só aceita "ok" quando cada mensagem volta com o MESMO par
// (event_id, message_id), ack === true e status inteiro >= 2; e só persiste a
// sessão quando "ok". Bibliotecas podem imprimir antes, mas o contrato é a
// última linha — este stub só imprime o contrato.
//
// Cenário escolhido (em ordem de precedência):
//   1. env var SURICATA_STUB_SCENARIO (uso manual/standalone; a ponte real
//      não repassa env, então por ela este campo é sempre vazio);
//   2. marcador "[stub:<cenario>]" no campo texto de alguma mensagem do lote;
//   3. campo "stub_scenario" do creds.json da sessão materializada.
// Padrão: "sucesso".
//
// NUNCA importa Baileys, NUNCA abre rede: só lê/escreve dentro do auth_dir
// recebido no próprio lote. Cenários: sucesso, timeout, ack-divergente, crash.

import fs from "node:fs";

const CENARIOS = new Set(["sucesso", "timeout", "ack-divergente", "crash"]);

function cenarioDoLote(payload) {
  const doEnv = process.env.SURICATA_STUB_SCENARIO;
  if (doEnv) return doEnv;
  const textos = (payload.mensagens || []).map((m) => m.texto || "");
  const marcador = textos.join("\n").match(/\[stub:([a-z-]+)\]/);
  if (marcador) return marcador[1];
  try {
    const creds = JSON.parse(fs.readFileSync(`${payload.auth_dir}/creds.json`, "utf8"));
    if (typeof creds.stub_scenario === "string") return creds.stub_scenario;
  } catch {
    // sessão sem creds.json legível: cai no cenário padrão
  }
  return "sucesso";
}

function lerCreds(authDir) {
  try {
    return JSON.parse(fs.readFileSync(`${authDir}/creds.json`, "utf8"));
  } catch {
    return {};
  }
}

function emitir(resposta) {
  process.stdout.write(JSON.stringify(resposta) + "\n");
}

let entrada = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { entrada += chunk; });
process.stdin.on("end", () => {
  const payload = JSON.parse(entrada);
  const cenario = cenarioDoLote(payload);
  const mensagens = payload.mensagens || [];

  if (!CENARIOS.has(cenario)) {
    emitir({ sessao: "erro", resultados: [], erro: `cenário desconhecido no stub: ${cenario}` });
    return;
  }

  if (cenario === "crash") {
    // Processo morre ANTES de emitir o contrato válido: a ponte tem que recusar.
    process.stdout.write("stub: crash simulado antes do contrato\n");
    process.stderr.write("stub: erro simulado de processo\n");
    process.exitCode = 70;
    return;
  }

  if (cenario === "timeout") {
    // Estado "timeout" do enviar.mjs: nenhum envio confirmado, nada persistido.
    emitir({
      sessao: "timeout",
      resultados: mensagens.map((m) => ({
        event_id: m.event_id,
        message_id: m.message_id,
        ack: false,
        status: 0,
        timeout: true,
      })),
    });
    return;
  }

  if (cenario === "ack-divergente") {
    // Sessão "ok" com ACK casado com message_id estranho: a ponte tem que
    // recusar (resposta de sucesso inconsistente) e não persistir a sessão.
    emitir({
      sessao: "ok",
      resultados: mensagens.map((m, i) => ({
        event_id: m.event_id,
        message_id: i === 0 ? `${m.message_id}-divergente` : m.message_id,
        ack: true,
        status: 2,
      })),
    });
    return;
  }

  // sucesso: confirma cada envio (mesmo event_id/message_id, ack true, status>=2)
  // e devolve a sessão atualizada dentro do auth_dir, como o enviar.mjs faria.
  const creds = lerCreds(payload.auth_dir);
  fs.writeFileSync(`${payload.auth_dir}/creds.json`, JSON.stringify({ ...creds, stub_used: true }));
  emitir({
    sessao: "ok",
    resultados: mensagens.map((m) => ({
      event_id: m.event_id,
      message_id: m.message_id,
      ack: true,
      status: 2,
    })),
  });
});
