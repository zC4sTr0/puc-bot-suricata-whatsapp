#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState
} from '@whiskeysockets/baileys';
import pino from 'pino';
import { estaDentro, validarAuthDir as validarAuthDirBase, realpathAncestro } from './auth-dir.mjs';

const WAIT_AFTER_OPEN_MS = 5_000;

function argumentos(argv) {
  const result = { png: null, codigo: null, authDir: null, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') result.help = true;
    else if (arg === '--auth-dir') result.authDir = argv[++i];
    else if (arg === '--png') result.png = argv[++i];
    else if (arg === '--codigo') result.codigo = argv[++i];
    else throw Object.assign(new Error('argumento desconhecido'), { code: 'ARGUMENTO_INVALIDO' });
  }
  return result;
}

function uso() {
  return 'Uso: node parear.mjs --auth-dir <diretorio-fora-do-repo> [--png <arquivo>] [--codigo <DDI+DDD+número>]';
}

function validar(args) {
  if (!args.authDir) throw Object.assign(new Error('auth-dir ausente'), { code: 'ARGUMENTO_INVALIDO' });
  const authDir = validarAuthDirBase(args.authDir);
  if (args.png) validarDestinoControlado(args.png, path.dirname(authDir));
  if (args.codigo && !/^\d{10,15}$/.test(args.codigo)) {
    throw Object.assign(new Error('codigo inválido'), { code: 'ARGUMENTO_INVALIDO' });
  }
  return { ...args, authDir };
}

function validarDestinoControlado(destino, raiz) {
  const raizReal = realpathAncestro(path.resolve(raiz));
  const destinoAbsoluto = path.resolve(destino);
  if (!estaDentro(raizReal, destinoAbsoluto) || !estaDentro(raizReal, realpathAncestro(destinoAbsoluto))) {
    throw Object.assign(new Error('destino fora da área controlada'), { code: 'DIRETORIO_INVALIDO' });
  }
  return destinoAbsoluto;
}

function terminalLocalInterativo(runtime = process) {
  return runtime.stdin?.isTTY === true
    && runtime.stdout?.isTTY === true
    && runtime.stderr?.isTTY === true;
}

function modoLocalPermitido(env = process.env, runtime = process) {
  return env.SURICATA_WHATSAPP_LOCAL === '1' && terminalLocalInterativo(runtime);
}

function ambienteCloudOuCi(env = process.env) {
  const marcado = (nome) => typeof env[nome] === 'string' && env[nome].trim() !== '';
  return ['CI', 'GITHUB_ACTIONS', 'K_SERVICE', 'CLOUD_RUN_JOB', 'CLOUD_RUN_SERVICE',
    'BUILD_ID', 'BUILD_NUMBER'].some(marcado);
}

function mensagemErroSegura(error) {
  if (error?.code === 'DIRETORIO_INVALIDO' || error?.code === 'EEXIST' || error?.code === 'ENOTDIR') {
    return 'Diretório de autenticação inválido.';
  }
  if (error?.code === 'SURICATA_LOCAL_ONLY') return 'Pareamento permitido somente em modo local explícito.';
  if (error?.code === 'ARGUMENTO_INVALIDO') return `Argumentos inválidos. ${uso()}`;
  if (error?.code === 'ERR_MODULE_NOT_FOUND') return 'Dependência opcional ausente.';
  if (error?.code === 'EACCES' || error?.code === 'EPERM') return 'Acesso ao diretório de autenticação recusado.';
  return 'Falha no pareamento (erro de biblioteca).';
}

function emitirErroSeguro(error) {
  console.error(JSON.stringify({ erro: mensagemErroSegura(error).slice(0, 200) }));
}

async function salvarPng(qr, destino) {
  try {
    const { default: qrcodeFile } = await import('qrcode');
    await qrcodeFile.toFile(destino, qr, { margin: 1, width: 512 });
    await fs.chmod(destino, 0o600);
  } catch (error) {
    if (error?.code === 'ERR_MODULE_NOT_FOUND') {
      throw Object.assign(new Error('dependência PNG ausente'), { code: 'ERR_MODULE_NOT_FOUND' });
    }
    throw error;
  }
}

async function listarGrupos(sock, authDir) {
  const grupos = Object.values(await sock.groupFetchAllParticipating())
    .map((grupo) => ({
      nome: String(grupo.subject ?? ''),
      jid: String(grupo.id ?? ''),
      participantes: Array.isArray(grupo.participants) ? grupo.participants.length : 0
    }))
    .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  const destino = caminhoGrupos(authDir);
  const temporario = `${destino}.tmp-${process.pid}-${Date.now()}`;
  try {
    await fs.writeFile(temporario, `${JSON.stringify(grupos, null, 2)}\n`, {
      encoding: 'utf8', mode: 0o600, flag: 'wx'
    });
    await fs.chmod(temporario, 0o600);
    await fs.rename(temporario, destino);
  } finally {
    // Uma falha não pode deixar lixo nem destruir o inventário anterior.
    await fs.rm(temporario, { force: true });
  }
  console.log(JSON.stringify({ evento: 'grupos_salvos', quantidade: grupos.length }));
}

function caminhoGrupos(authDir) {
  return path.join(path.dirname(authDir), 'grupos.json');
}

async function limparGruposAposConfirmacao(authDir, confirmacao = {}) {
  if (confirmacao?.confirmado !== true) return false;
  const args = validar({ authDir, png: null, codigo: null });
  await fs.rm(caminhoGrupos(args.authDir), { force: true });
  return true;
}

async function main(argv = process.argv.slice(2), dependencies = {}) {
  const runtime = dependencies.runtime ?? process;
  const env = dependencies.env ?? runtime.env ?? process.env;
  if (!modoLocalPermitido(env, runtime) || ambienteCloudOuCi(env)) {
    throw Object.assign(new Error('pareamento fora do modo local'), { code: 'SURICATA_LOCAL_ONLY' });
  }
  const parsed = argumentos(argv);
  if (parsed.help) { console.log(uso()); return 0; }
  const args = validar(parsed);
  await fs.mkdir(args.authDir, { recursive: true });
  const authReal = await fs.realpath(args.authDir);
  const useAuth = dependencies.useMultiFileAuthState ?? useMultiFileAuthState;
  const fetchVersion = dependencies.fetchLatestBaileysVersion ?? fetchLatestBaileysVersion;
  const createSocket = dependencies.makeWASocket ?? makeWASocket;
  const { state, saveCreds } = await useAuth(args.authDir);
  const { version } = await fetchVersion();
  const sock = createSocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ['Suricata Pairing', 'Chrome', '1.0.0'],
    logger: pino({ level: 'silent' })
  });
  sock.ev.on('creds.update', saveCreds);
  let pairingRequested = false;
  let closing = false;
  let resolveDone;
  const done = new Promise((resolve) => { resolveDone = resolve; });

  const close = (code) => {
    if (closing) return;
    closing = true;
    try { sock.end(undefined); } catch { /* já encerrado */ }
    process.exitCode = code;
    resolveDone(code);
  };

  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    try {
      if (qr && !args.codigo) {
        if (args.png) await salvarPng(qr, validarDestinoControlado(args.png, path.dirname(authReal)));
        console.log(JSON.stringify({ evento: 'qr_disponivel', png: args.png ? 'salvo' : 'nao_salvo' }));
      }
      if (args.codigo && !pairingRequested && connection === 'connecting') {
        pairingRequested = true;
        const code = await sock.requestPairingCode(args.codigo);
        void code;
        console.log(JSON.stringify({ evento: 'codigo_pareamento_disponivel' }));
      }
      if (connection === 'open') {
        await new Promise((resolve) => setTimeout(resolve, WAIT_AFTER_OPEN_MS));
        await listarGrupos(sock, authReal);
        close(0);
      }
      if (connection === 'close' && !closing) {
        const code = lastDisconnect?.error?.output?.statusCode;
        close(code === DisconnectReason.loggedOut ? 2 : 1);
      }
    } catch (error) {
      emitirErroSeguro(error);
      close(1);
    }
  });
  process.once('SIGINT', () => close(130));
  process.once('SIGTERM', () => close(143));
  return done;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((error) => { emitirErroSeguro(error); process.exitCode = 2; });
}

export {
  argumentos,
  validar,
  salvarPng,
  listarGrupos,
  caminhoGrupos,
  limparGruposAposConfirmacao,
  main,
  modoLocalPermitido,
  terminalLocalInterativo,
  ambienteCloudOuCi,
  mensagemErroSegura
};
