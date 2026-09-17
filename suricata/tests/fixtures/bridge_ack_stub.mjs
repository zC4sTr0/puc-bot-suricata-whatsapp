import fs from "node:fs";

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const payload = JSON.parse(input);
  const auth = JSON.parse(fs.readFileSync(`${payload.auth_dir}/creds.json`, "utf8"));
  fs.writeFileSync(`${payload.auth_dir}/creds.json`, JSON.stringify({ ...auth, stub_used: true }));
  process.stdout.write(JSON.stringify({
    sessao: "ok",
    resultados: payload.mensagens.map((mensagem) => ({
      event_id: mensagem.event_id,
      message_id: mensagem.message_id,
      ack: true,
      status: 2,
    })),
  }) + "\n");
});
