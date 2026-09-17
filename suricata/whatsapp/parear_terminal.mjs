#!/usr/bin/env node
// Pareamento da Suricata para o titular: QR no terminal, reconexão após o scan.
//
// Depois de ler o QR, o WhatsApp encerra a conexão com "restart required" (515)
// e o cliente precisa reconectar com as credenciais novas para chegar a "open".
// O parear.mjs antigo tratava esse fechamento como falha e saía antes de concluir.
//
// Uso (só local, terminal interativo; o diretório fica FORA do repositório):
//   node parear_terminal.mjs --auth-dir <dir> [--codigo 5531999999999]
// Ao concluir, grava <dir>/../grupos.json (nome, JID, participantes) e sai com 0.
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import pino from 'pino';
import qrcodeTerminal from 'qrcode-terminal';
import { validarAuthDir } from './auth-dir.mjs';

const args = process.argv.slice(2);
const valor = (nome) => { const i = args.indexOf(nome); return i >= 0 ? args[i + 1] : null; };
const authDir = validarAuthDir(valor('--auth-dir'));
const numero = valor('--codigo');
if (numero && !/^\d{10,15}$/.test(numero)) { console.error('número inválido (use DDI+DDD+número, só dígitos)'); process.exit(2); }
await fs.mkdir(authDir, { recursive: true });

const PRAZO_MS = 5 * 60_000;
setTimeout(() => { console.error('\nTempo esgotado (5 min) sem concluir o pareamento.'); process.exit(3); }, PRAZO_MS).unref();

let codigoPedido = false;

async function conectar() {
  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version, auth: state, printQRInTerminal: false, syncFullHistory: false, markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false, browser: Browsers.ubuntu('Suricata'), logger: pino({ level: 'silent' }),
  });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    if (qr && !numero) {
      console.clear();
      console.log('SURICATA — pareamento do WhatsApp do chip\n');
      console.log('No celular do chip: WhatsApp → Aparelhos conectados → Conectar aparelho → aponte para o QR.\n');
      qrcodeTerminal.generate(qr, { small: true });
      console.log('\n(O QR troca a cada ~20 s; esta janela atualiza sozinha.)');
    }
    if (numero && !codigoPedido && !state.creds.registered) {
      codigoPedido = true;
      await new Promise((r) => setTimeout(r, 2000));
      const codigo = await sock.requestPairingCode(numero);
      console.log(`\nCódigo de pareamento: ${codigo}`);
      console.log('No celular do chip: Aparelhos conectados → Conectar aparelho → "Conectar com número de telefone".');
    }
    if (connection === 'open') {
      console.log('\n✅ Pareado. Lendo grupos...');
      await new Promise((r) => setTimeout(r, 5000));
      const grupos = Object.values(await sock.groupFetchAllParticipating()).map((g) => ({
        nome: String(g.subject ?? ''), jid: g.id, participantes: Array.isArray(g.participants) ? g.participants.length : null,
      }));
      await fs.writeFile(path.join(path.dirname(authDir), 'grupos.json'), JSON.stringify(grupos, null, 2), { mode: 0o600 });
      console.log(`Grupos encontrados: ${grupos.length}. Pode fechar esta janela.`);
      await new Promise((r) => setTimeout(r, 3000));  // flush final de creds
      sock.end(undefined);
      process.exit(0);
    }
    if (connection === 'close') {
      const status = lastDisconnect?.error?.output?.statusCode;
      if (status === DisconnectReason.loggedOut) {
        console.error('\nO WhatsApp recusou/desconectou este aparelho (401). Rode de novo para um QR novo.');
        process.exit(2);
      }
      // 515 restartRequired após o scan, ou queda de rede: reconecta com as credenciais salvas.
      setTimeout(() => conectar().catch((e) => { console.error('falha ao reconectar:', e?.message); process.exit(1); }), 1000);
    }
  });
}

await conectar();
