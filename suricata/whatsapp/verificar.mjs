#!/usr/bin/env node
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  abrirSessao,
  fecharSessao,
  validarAuthDir as validarAuthDirSessao,
} from './sessao.mjs';

const DEFAULT_TIMEOUT_MS = 30_000;

function erroSeguro(mensagem, code = 'INVALID_INPUT') {
  return Object.assign(new Error(mensagem), { code, safeMessage: true });
}

function parseArgs(argv) {
  const args = {
    authDir: process.env.SURICATA_WA_AUTH_DIR ?? null,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    help: false,
  };
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
      if (typeof value !== 'string' || value.startsWith('--')) {
        throw erroSeguro('valor ausente para --auth-dir');
      }
      if (seen.has(option)) throw erroSeguro('opção repetida: --auth-dir');
      seen.add(option);
      args.authDir = value;
      i += 1;
    } else if (option === '--timeout-ms') {
      const value = argv[i + 1];
      if (typeof value !== 'string' || value.startsWith('--')) {
        throw erroSeguro('valor ausente para --timeout-ms');
      }
      if (seen.has(option)) throw erroSeguro('opção repetida: --timeout-ms');
      seen.add(option);
      args.timeoutMs = Number(value);
      i += 1;
    } else {
      throw erroSeguro('argumento desconhecido');
    }
  }
  if (!Number.isInteger(args.timeoutMs) || args.timeoutMs < 100) {
    throw erroSeguro('timeout inválido');
  }
  return args;
}

async function validarAuthDir(authDir) {
  return validarAuthDirSessao(authDir);
}

function contarGrupos(grupos) {
  if (Array.isArray(grupos)) return grupos.length;
  if (grupos && typeof grupos === 'object') return Object.keys(grupos).length;
  throw erroSeguro('resposta de grupos inválida', 'INVALID_RESPONSE');
}

function mensagemErroSegura(error) {
  if (error?.motivo === 'logged_out') return 'sessão desconectada';
  if (error?.motivo === 'timeout' || error?.code === 'TIMEOUT') return 'tempo excedido';
  if (error?.code === 'INVALID_INPUT' || error?.code === 'INVALID_RESPONSE' || error?.motivo === 'invalid_input') return 'argumentos ou resposta inválidos';
  return 'falha no transporte WhatsApp';
}

function imprimirErro(error) {
  const sessao = error?.motivo === 'logged_out'
    ? 'logged_out'
    : error?.motivo === 'timeout' || error?.code === 'TIMEOUT'
      ? 'timeout'
      : 'erro';
  return { sessao, grupos: 0, erro: mensagemErroSegura(error) };
}

async function verificar(args, dependencies = {}) {
  const connect = dependencies.abrirSessao ?? abrirSessao;
  const close = dependencies.fecharSessao ?? fecharSessao;
  const authDir = await validarAuthDir(args.authDir);
  const sock = await connect(authDir, { timeoutMs: args.timeoutMs });
  try {
    const grupos = await sock.groupFetchAllParticipating();
    return { sessao: 'ok', grupos: contarGrupos(grupos) };
  } finally {
    await close(sock);
  }
}

async function main(argv = process.argv.slice(2), dependencies = {}) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log('Uso: node verificar.mjs --auth-dir <diretório-fora-do-repo> [--timeout-ms <ms>]');
    return 0;
  }
  if (!args.authDir) throw erroSeguro('auth-dir ausente');
  const resultado = await verificar(args, dependencies);
  console.log(JSON.stringify(resultado));
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((error) => {
    console.error(JSON.stringify(imprimirErro(error)));
    process.exitCode = error?.motivo === 'logged_out' ? 10 : error?.code === 'INVALID_INPUT' ? 2 : 1;
  });
}

export {
  contarGrupos,
  imprimirErro,
  main,
  mensagemErroSegura,
  parseArgs,
  validarAuthDir,
  verificar,
};
