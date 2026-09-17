#!/usr/bin/env node
import readline from 'node:readline';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { fecharSessao, abrirSessao, SessionError } from './sessao.mjs';
import { validarAuthDir as validarAuthDirBase } from './auth-dir.mjs';

const DEFAULT_TIMEOUT_MS = 30_000;

function erroSeguro(mensagem, code = 'INVALID_INPUT') {
  return Object.assign(new Error(mensagem), { code, safeMessage: true });
}

function validarAuthDir(authDir) {
  return validarAuthDirBase(authDir, { errorFactory: (mensagem) => erroSeguro(mensagem) });
}

function parseBatch(text) {
  let value;
  try { value = JSON.parse(text); } catch { throw erroSeguro('stdin não contém JSON válido'); }
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw erroSeguro('lote deve ser um objeto JSON');
  const authDir = validarAuthDir(value.auth_dir);
  // Grupos atuais: 120363…@g.us; grupos antigos: número-timestamp@g.us.
  if (!/^\d+(-\d+)?@g\.us$/.test(value.grupo_jid ?? '')) throw erroSeguro('grupo_jid inválido');
  if (!Array.isArray(value.mensagens) || value.mensagens.length === 0) throw erroSeguro('mensagens deve ser uma lista não vazia');
  const eventIds = new Set();
  const messageIds = new Set();
  return { authDir, grupoJid: value.grupo_jid, mensagens: value.mensagens.map((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw erroSeguro(`item ${index} inválido`);
    const { event_id: eventId, message_id: messageId, texto } = item;
    if (typeof eventId !== 'string' || eventId.length === 0 || eventId.length > 200) throw erroSeguro(`event_id inválido no item ${index}`);
    if (!/^3EB0[0-9A-F]{18}$/.test(messageId ?? '')) throw erroSeguro(`message_id inválido no item ${index}`);
    if (typeof texto !== 'string' || texto.length === 0 || texto.length > 4096) throw erroSeguro(`texto inválido no item ${index}`);
    if (eventIds.has(eventId)) throw erroSeguro(`event_id duplicado no item ${index}`);
    if (messageIds.has(messageId)) throw erroSeguro(`message_id duplicado no item ${index}`);
    eventIds.add(eventId);
    messageIds.add(messageId);
    return { eventId, messageId, texto };
  }) };
}

function parseArgs(argv) {
  const args = { authDir: process.env.SURICATA_WA_AUTH_DIR ?? null, timeoutMs: DEFAULT_TIMEOUT_MS, help: false };
  const seen = new Set();
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const option = arg === '-h' ? '--help' : arg;
    if (option === '--help') {
      if (seen.has(option)) throw erroSeguro('opção repetida: --help');
      seen.add(option);
      args.help = true;
    } else if (option === '--auth-dir') {
      const value = argv[i + 1];
      if (typeof value !== 'string' || value.startsWith('--')) throw erroSeguro('valor ausente para --auth-dir');
      if (seen.has(option)) throw erroSeguro('opção repetida: --auth-dir');
      seen.add(option);
      args.authDir = value;
      i += 1;
    } else if (option === '--timeout-ms') {
      const value = argv[i + 1];
      if (typeof value !== 'string' || value.startsWith('--')) throw erroSeguro('valor ausente para --timeout-ms');
      if (seen.has(option)) throw erroSeguro('opção repetida: --timeout-ms');
      seen.add(option);
      args.timeoutMs = Number(value);
      i += 1;
    } else throw erroSeguro('argumento desconhecido');
  }
  if (!Number.isInteger(args.timeoutMs) || args.timeoutMs < 100) throw erroSeguro('timeout inválido');
  if (args.authDir) {
    args.authDir = validarAuthDir(args.authDir);
  }
  return args;
}

// Confirmação do servidor = stanza <ack class="message" id=...> sem "error".
// Medido 2026-09-14 no Baileys 6.7.24 (Socket/messages-recv.js): esse ACK de sucesso
// NÃO vira evento; só erros viram messages.update. Status >= 2 em messages.update
// só chega por recibo de outro aparelho (celular do chip ou participantes online),
// que pode nunca vir. Por isso escutamos o WebSocket e aceitamos os dois sinais.
function esperarAck(sock, messageId, timeoutMs) {
  return new Promise((resolve) => {
    const ws = sock.ws && typeof sock.ws.on === 'function' ? sock.ws : null;
    const encerrar = (resultado) => {
      clearTimeout(timer);
      sock.ev.off('messages.update', onUpdate);
      ws?.off('CB:ack,class:message', onAck);
      resolve(resultado);
    };
    const timer = setTimeout(() => encerrar({ ack: false, status: null, timeout: true }), timeoutMs);
    function onAck(node) {
      if (node?.attrs?.id !== messageId) return;
      if (node.attrs.error) encerrar({ ack: false, status: null, timeout: false, erro: `ack_error_${String(node.attrs.error).slice(0, 20)}` });
      else encerrar({ ack: true, status: 2, timeout: false });
    }
    function onUpdate(updates) {
      for (const update of updates) {
        const status = Number(update.update?.status ?? 0);
        if (update.key?.id === messageId && status >= 2) {
          encerrar({ ack: true, status, timeout: false });
          return;
        }
      }
    }
    sock.ev.on('messages.update', onUpdate);
    ws?.on('CB:ack,class:message', onAck);
  });
}

function comTimeout(promise, timeoutMs) {
  let timer;
  const limite = new Promise((_, reject) => {
    timer = setTimeout(() => reject(erroSeguro('tempo excedido no envio WhatsApp', 'TIMEOUT')), timeoutMs);
  });
  return Promise.race([promise, limite]).finally(() => clearTimeout(timer));
}

async function enviarLote(batch, args, dependencies = {}) {
  const connect = dependencies.abrirSessao ?? abrirSessao;
  const close = dependencies.fecharSessao ?? fecharSessao;
  const sock = await connect(batch.authDir, { timeoutMs: args.timeoutMs });
  try {
    const resultados = [];
    for (const item of batch.mensagens) {
      // O listener vem antes do envio para capturar ACK síncrono.
      const ack = esperarAck(sock, item.messageId, args.timeoutMs);
      await comTimeout(sock.sendMessage(batch.grupoJid, { text: item.texto }, { messageId: item.messageId }), args.timeoutMs);
      resultados.push({ event_id: item.eventId, message_id: item.messageId, erro: null, ...await ack });
    }
    return { sessao: 'ok', resultados };
  } finally {
    await close(sock);
  }
}

function imprimirErro(error) {
  const mensagem = error?.safeMessage ? String(error.message).slice(0, 160) : 'falha no transporte WhatsApp';
  const sessao = error?.motivo === 'logged_out' ? 'logged_out' : error?.motivo === 'timeout' ? 'timeout' : 'erro';
  // Diagnóstico por lista branca: mensagens do Baileys como "Connection Closed" ou "Timed Out"
  // passam; qualquer coisa com '=', '@', '/', dígitos longos etc. vira <omitido>.
  const texto = String(error?.message ?? '');
  const simples = /^[A-Za-zÀ-ú][A-Za-zÀ-ú \-_.,:]{0,60}$/.test(texto) ? texto : '<omitido>';
  const codigo = Number.isInteger(error?.output?.statusCode) ? ` (${error.output.statusCode})` : '';
  const nome = /^[A-Za-z]{1,30}$/.test(String(error?.name ?? '')) ? error.name : 'Error';
  return { sessao, resultados: [], erro: mensagem, detalhe: `${nome}: ${simples}${codigo}` };
}

async function main(argv = process.argv.slice(2), input = process.stdin) {
  const args = parseArgs(argv);
  if (args.help) { console.log('Uso: node enviar.mjs --auth-dir <diretório-fora-do-repo> [--timeout-ms <ms>]'); return 0; }
  const chunks = [];
  for await (const linha of readline.createInterface({ input, crlfDelay: Infinity })) if (linha.trim()) chunks.push(linha);
  const batch = parseBatch(chunks.join('\n'));
  return enviarLote(batch, { ...args, authDir: args.authDir ?? batch.authDir });
}

function sair(resultado, codigo) {
  // stdout em pipe é assíncrono no Node: só encerra depois do flush da linha do contrato.
  process.stdout.write(`${JSON.stringify(resultado)}` + String.fromCharCode(10), () => process.exit(codigo));
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  // Medido 2026-09-14 no Cloud Run: depois de sock.end() o Baileys rejeita promessas pendentes
  // sem handler, e o Node saía com exit 1 DEPOIS de obter ACKs válidos. O contrato é a linha JSON.
  process.on('unhandledRejection', (erro) => { process.stderr.write(`rejeicao_ignorada: ${erro?.name ?? 'Error'}` + String.fromCharCode(10)); });
  process.on('uncaughtException', (erro) => { process.stderr.write(`excecao_ignorada: ${erro?.name ?? 'Error'}` + String.fromCharCode(10)); });
  main().then(
    (resultado) => (resultado === 0 ? process.exit(0) : sair(resultado, 0)),
    (error) => sair(imprimirErro(error), error?.motivo === 'logged_out' ? 10 : 1),
  );
}

export { parseBatch, parseArgs, validarAuthDir, esperarAck, comTimeout, enviarLote, imprimirErro, main, SessionError };
