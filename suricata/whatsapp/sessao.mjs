import process from 'node:process';
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import pino from 'pino';
import { validarAuthDir as validarAuthDirBase } from './auth-dir.mjs';

export class SessionError extends Error {
  constructor(mensagem, motivo = 'connection') {
    super(mensagem);
    this.name = 'SessionError';
    this.motivo = motivo;
    this.safeMessage = true;
  }
}

export async function validarAuthDir(authDir) {
  return validarAuthDirBase(authDir, {
    errorFactory: (mensagem) => new SessionError(mensagem, 'invalid_input'),
  });
}

export async function abrirSessao(authDir, { timeoutMs = 30_000, onQr, dependencies = {}, closeDelayMs = 3_000 } = {}) {
  authDir = await validarAuthDir(authDir);
  const useAuth = dependencies.useMultiFileAuthState ?? useMultiFileAuthState;
  const fetchVersion = dependencies.fetchLatestBaileysVersion ?? fetchLatestBaileysVersion;
  const createSocket = dependencies.makeWASocket ?? makeWASocket;
  const { state, saveCreds } = await useAuth(authDir);
  // A versão do pacote é pinada no package-lock; a versão WA negociada é
  // deliberadamente obtida do Baileys e não pode ser pinada sem inventar um
  // valor. O teste verifica que o valor retornado chega intacto ao socket.
  const { version } = await fetchVersion();
  const sock = createSocket({
    version,
    auth: state,
    printQRInTerminal: false,
    syncFullHistory: false,
    markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false,
    browser: Browsers.ubuntu('Suricata'),
    logger: pino({ level: 'silent' }),
  });
  let connected = false;
  try {
    sock.ev.on('creds.update', saveCreds);
    if (onQr) sock.ev.on('connection.update', ({ qr }) => { if (qr) onQr(qr); });
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new SessionError('tempo excedido aguardando conexão', 'timeout')), timeoutMs);
      sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
        if (connection === 'open') { clearTimeout(timer); resolve(); return; }
        if (connection === 'close') {
          clearTimeout(timer);
          const code = lastDisconnect?.error?.output?.statusCode;
          reject(new SessionError(code === DisconnectReason.loggedOut ? 'sessão desconectada' : 'conexão encerrada', code === DisconnectReason.loggedOut ? 'logged_out' : 'connection'));
        }
      });
    });
    connected = true;
    return sock;
  } finally {
    if (!connected) await fecharSessao(sock, closeDelayMs);
  }
}

export async function fecharSessao(sock, delayMs = 3_000) {
  // Baileys pode emitir creds.update imediatamente antes do encerramento.
  await new Promise((resolve) => setTimeout(resolve, delayMs));
  try { sock?.end(undefined); } catch { /* encerramento controlado */ }
}

if (process.env.NODE_ENV === 'test') process.exitCode = 0;
