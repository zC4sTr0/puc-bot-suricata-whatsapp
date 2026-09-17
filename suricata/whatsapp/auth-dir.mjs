import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

function existe(caminho) {
  try {
    fs.lstatSync(caminho);
    return true;
  } catch (error) {
    if (error?.code === 'ENOENT' || error?.code === 'ENOTDIR') return false;
    throw error;
  }
}

function realpathAncestro(alvo) {
  let atual = alvo;
  while (true) {
    try { return fs.realpathSync.native(atual); } catch (error) {
      if (error?.code !== 'ENOENT' && error?.code !== 'ENOTDIR') throw error;
      const pai = path.dirname(atual);
      if (pai === atual) throw error;
      atual = pai;
    }
  }
}

function estaDentro(raiz, alvo) {
  const relativo = path.relative(raiz, alvo);
  return relativo === ''
    || (!relativo.startsWith('..' + path.sep) && relativo !== '..' && !path.isAbsolute(relativo));
}

function encontrarRepoRoot(moduleDir) {
  let atual = path.resolve(moduleDir);
  let arquivoCompleto = null;
  let pacoteIsolado = null;
  while (true) {
    // Em checkout e worktree, .git pode ser diretório ou arquivo.
    if (existe(path.join(atual, '.git'))) return atual;
    // Arquivo completo extraído sem .git: AGENTS.md + suricata/ identifica a raiz.
    if (existe(path.join(atual, 'AGENTS.md')) && existe(path.join(atual, 'suricata'))) arquivoCompleto ??= atual;
    // Pacote Suricata isolado: whatsapp/package.json identifica sua raiz.
    if (existe(path.join(atual, 'package.json')) && path.basename(atual) === 'whatsapp') {
      pacoteIsolado ??= path.dirname(atual);
    }
    if (existe(path.join(atual, 'whatsapp', 'package.json'))) pacoteIsolado ??= atual;
    const pai = path.dirname(atual);
    if (pai === atual) return arquivoCompleto ?? pacoteIsolado ?? path.resolve(moduleDir);
    atual = pai;
  }
}

export const REPO_ROOT = encontrarRepoRoot(path.dirname(fileURLToPath(import.meta.url)));
export { estaDentro, realpathAncestro };

export function validarAuthDir(authDir, { errorFactory = (mensagem) => Object.assign(new Error(mensagem), { code: 'DIRETORIO_INVALIDO' }) } = {}) {
  if (!authDir || typeof authDir !== 'string') throw errorFactory('diretório de autenticação ausente');
  const resolvido = path.resolve(authDir);
  const raizReal = realpathAncestro(REPO_ROOT);
  if (estaDentro(REPO_ROOT, resolvido) || estaDentro(raizReal, realpathAncestro(resolvido))) {
    throw errorFactory('diretório de autenticação inválido (dentro do repo)');
  }
  return resolvido;
}
