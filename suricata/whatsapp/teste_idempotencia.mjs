#!/usr/bin/env node
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import crypto from 'node:crypto';
import { pathToFileURL } from 'node:url';
import makeWASocket, { fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import pino from 'pino';
import { validarAuthDir as validarAuthDirBase } from './auth-dir.mjs';

const MESSAGE_ID = '3EB0A1B2C3D4E5F6071829';
const TEXT = 'teste 1';

const SAFE_ERROR_CLASSES = new Set([
  'AbortError', 'AggregateError', 'Error', 'EvalError', 'RangeError',
  'ReferenceError', 'SyntaxError', 'TimeoutError', 'TypeError', 'URIError',
]);
const TRANSPORT_CODES = new Set(['EAI_AGAIN', 'ECONNABORTED', 'ECONNRESET', 'ETIMEDOUT', 'ENETUNREACH', 'ENOTFOUND']);

function erroLocal(message) {
  const error = new Error(message);
  error.safeMessage = true;
  return error;
}

function sanitizarErro(error, fallback = 'falha externa') {
  const classe = SAFE_ERROR_CLASSES.has(error?.constructor?.name) ? error.constructor.name : 'Error';
  if (error?.safeMessage && typeof error.message === 'string') {
    return `${classe}: ${error.message.slice(0, 120)}`;
  }
  if (TRANSPORT_CODES.has(error?.code) || ['AbortError', 'TimeoutError'].includes(error?.name)) {
    return `${classe}: falha de transporte`;
  }
  return `${classe}: ${fallback}`;
}

function parseArgs(argv) {
  const args = { authDir: null, grupoJid: null, timeoutMs: 30_000, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    switch (argv[i]) {
      case '--help': case '-h': args.help = true; break;
      case '--auth-dir': args.authDir = argv[++i]; break;
      case '--grupo-jid': args.grupoJid = argv[++i]; break;
      case '--timeout-ms': args.timeoutMs = Number(argv[++i]); break;
      default: throw erroLocal('argumento desconhecido');
    }
  }
  return args;
}

function validar(args) {
  if (!args.authDir) throw erroLocal('--auth-dir é obrigatório; use um diretório temporário/local.');
  const authDir = validarAuthDirBase(args.authDir, { errorFactory: () => erroLocal('--auth-dir deve ficar fora do repositório.') });
  if (!Number.isInteger(args.timeoutMs) || args.timeoutMs < 100) throw erroLocal('--timeout-ms inválido.');
  return { ...args, authDir };
}

async function hashDir(dir) {
  const entries = [];
  async function visit(current) {
    for (const name of (await fs.readdir(current)).sort()) {
      const full = path.join(current, name);
      const stat = await fs.stat(full);
      if (stat.isDirectory()) await visit(full);
      else entries.push(`${path.relative(dir, full)}\0${await fs.readFile(full, 'base64')}`);
    }
  }
  await visit(dir);
  return crypto.createHash('sha256').update(entries.join('\n')).digest('hex');
}

async function copiarDevolverComCas(origem, temporario, hashInicial) {
  if (await hashDir(origem) !== hashInicial) throw new Error('sessão local alterada durante o teste; CAS recusado');
  // O backup fica no tmp do sistema, nunca ao lado da sessão ou no repo.
  const backup = path.join(os.tmpdir(), `.suricata-wa-backup-${process.pid}-${crypto.randomUUID()}`);
  let movido = false;
  try {
    await fs.rename(origem, backup);
    movido = true;
    await fs.cp(temporario, origem, { recursive: true });
  } catch (error) {
    if (movido) {
      await fs.rm(origem, { recursive: true, force: true });
      await fs.rename(backup, origem);
      movido = false;
    }
    throw error;
  } finally {
    if (movido) await fs.rm(backup, { recursive: true, force: true });
  }
}

function esperarAck(sock, messageId, timeoutMs) {
  return new Promise((resolve) => {
    const onUpdate = (updates) => {
      for (const update of updates) {
        const status = Number(update.update?.status ?? 0);
        if (update.key?.id === messageId && status >= 2) {
          clearTimeout(timer);
          sock.ev.off('messages.update', onUpdate);
          resolve({ ack: true, status, timeout: false });
          return;
        }
      }
    };
    const timer = setTimeout(() => {
      sock.ev.off('messages.update', onUpdate);
      resolve({ ack: false, status: null, timeout: true });
    }, timeoutMs);
    // A chamada ocorre antes de sendMessage para não perder um update síncrono.
    sock.ev.on('messages.update', onUpdate);
  });
}

async function enviarComAck(sock, jid, timeoutMs) {
  // Registra o listener antes de qualquer envio para capturar updates imediatos.
  const ack = esperarAck(sock, MESSAGE_ID, timeoutMs);
  await sock.sendMessage(jid, { text: TEXT }, { messageId: MESSAGE_ID });
  return ack;
}

async function executarMock(args) {
  await fs.mkdir(args.authDir, { recursive: true });
  const arquivo = path.join(args.authDir, 'mock-session.json');
  await fs.writeFile(arquivo, '{"mock":true}\n', { flag: 'a', mode: 0o600 });
  return { evento: 'medicao_local', modo: 'mock', grupo_jid: args.grupoJid ?? 'mock-group@g.us', message_id: MESSAGE_ID, primeira: { ack: true, status: 2, timeout: false }, segunda: { ack: true, status: 2, timeout: false }, mensagens_observadas: 1 };
}

async function executarReal(args) {
  let temporario;
  let hashInicial;
  let sock;
  try {
    temporario = await fs.mkdtemp(path.join(os.tmpdir(), '.suricata-wa-'));
    hashInicial = await hashDir(args.authDir);
    await fs.cp(args.authDir, temporario, { recursive: true });
    const { state, saveCreds } = await useMultiFileAuthState(temporario);
    const { version } = await fetchLatestBaileysVersion();
    sock = makeWASocket({ version, auth: state, printQRInTerminal: false, logger: pino({ level: 'silent' }) });
    sock.ev.on('creds.update', saveCreds);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('tempo excedido aguardando conexão')), args.timeoutMs);
      sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
        if (connection === 'open') { clearTimeout(timer); resolve(); }
        if (connection === 'close') { clearTimeout(timer); reject(lastDisconnect?.error ?? new Error('conexão encerrada')); }
      });
    });
    let jid = args.grupoJid;
    let created = false;
    if (!jid) {
      try { jid = (await sock.groupCreate('Suricata teste', [])).id; created = true; }
      catch { throw erroLocal('criação do grupo de teste recusada'); }
    }
    const started = Date.now();
    const primeira = await enviarComAck(sock, jid, args.timeoutMs);
    const segunda = await enviarComAck(sock, jid, args.timeoutMs);
    if (created) await sock.groupLeave(jid);
    return { evento: 'medicao', grupo_jid: jid, message_id: MESSAGE_ID, primeira, segunda, duracao_ms: Date.now() - started, mensagens_observadas: null, observacao: 'conte as mensagens no celular do chip; o script não infere a duplicação visual' };
  } finally {
    try { sock?.end(undefined); } catch { /* encerramento controlado */ }
    if (temporario && hashInicial) await copiarDevolverComCas(args.authDir, temporario, hashInicial);
    if (temporario) await fs.rm(temporario, { recursive: true, force: true });
  }
}

async function main(argv = process.argv.slice(2)) {
  const parsed = parseArgs(argv);
  if (parsed.help) { console.log('Uso: node teste_idempotencia.mjs --auth-dir <diretório-fora-do-repo> [--grupo-jid <jid>] [--timeout-ms <ms>]'); return 0; }
  const args = validar(parsed);
  const resultado = process.env.SURICATA_WHATSAPP_LOCAL === '1' ? await executarMock(args) : await executarReal(args);
  console.log(JSON.stringify(resultado));
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch((error) => { console.error(`Falha na medição: ${sanitizarErro(error)}`); process.exitCode = 2; });
export { MESSAGE_ID, parseArgs, validar, hashDir, esperarAck, enviarComAck, executarMock, copiarDevolverComCas, sanitizarErro, main };
