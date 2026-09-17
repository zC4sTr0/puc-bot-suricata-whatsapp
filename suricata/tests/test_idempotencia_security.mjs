import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  copiarDevolverComCas,
  hashDir,
  sanitizarErro,
  validar,
} from '../whatsapp/teste_idempotencia.mjs';

const TMP_PREFIX = '.suricata-wa-backup-';
async function tempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), 'suricata-security-'));
}

test('aceita auth-dir externo no diretório temporário do sistema', async () => {
  const root = await tempDir();
  try {
    const resultado = validar({ authDir: path.join(root, 'auth'), grupoJid: null, timeoutMs: 100 });
    assert.equal(resultado.authDir, path.join(root, 'auth'));
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

test('rejeita auth-dir por junction que aponta para dentro do repositório', async () => {
  const root = await tempDir();
  const link = path.join(root, 'auth-link');
  try {
    await fs.symlink(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), link, 'junction');
    assert.throws(() => validar({ authDir: link, grupoJid: null, timeoutMs: 100 }), /fora do repositório/);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});

// S-03 — a mensagem externa nunca entra no erro exibido.
test('sanitiza erro de transporte sem JID nem URL', () => {
  const error = new Error('connect https://wa.example.test/abc para 5511999999999@s.whatsapp.net');
  error.code = 'ECONNRESET';
  const output = sanitizarErro(error);

  assert.equal(output, 'Error: falha de transporte');
  assert.doesNotMatch(output, /https?:\/\//i);
  assert.doesNotMatch(output, /@s\.whatsapp\.net|\d{10,}/i);
  assert.ok(output.length <= 120);
});

// S-03 — classes desconhecidas também não carregam texto do objeto externo.
test('sanitiza erro externo de classe desconhecida', () => {
  class BaileysTransportError extends Error {}
  const output = sanitizarErro(new BaileysTransportError('jid=5511999999999@s.whatsapp.net url=https://secret.invalid'));

  assert.equal(output, 'Error: falha externa');
  assert.doesNotMatch(output, /5511999999999|https?:\/\//i);
});

// S-05 — falha durante a troca restaura a sessão e não deixa backup ao lado dela.
test('rollback de backup temporário restaura a sessão após crash de cópia', async () => {
  const root = await tempDir();
  const authDir = path.join(root, 'auth');
  const missingTemp = path.join(root, 'temporario-inexistente');
  await fs.mkdir(authDir);
  await fs.writeFile(path.join(authDir, 'creds.json'), '{"original":true}\n', { mode: 0o600 });
  const before = await hashDir(authDir);

  await assert.rejects(
    copiarDevolverComCas(authDir, missingTemp, before),
    /ENOENT|não existe|no such file/i,
  );

  assert.equal(await hashDir(authDir), before);
  assert.deepEqual(await fs.readdir(root), ['auth']);
  assert.equal((await fs.readdir(os.tmpdir())).some((name) => name.startsWith(TMP_PREFIX)), false);
  await fs.rm(root, { recursive: true, force: true });
});

// S-05 — caminho de staging concluído também remove o backup.
test('troca CAS concluída remove o backup fora da sessão', async () => {
  const root = await tempDir();
  const authDir = path.join(root, 'auth');
  const staging = path.join(root, 'staging');
  await fs.mkdir(authDir);
  await fs.mkdir(staging);
  await fs.writeFile(path.join(authDir, 'creds.json'), 'old\n');
  await fs.writeFile(path.join(staging, 'creds.json'), 'new\n');

  await copiarDevolverComCas(authDir, staging, await hashDir(authDir));

  assert.equal(await fs.readFile(path.join(authDir, 'creds.json'), 'utf8'), 'new\n');
  assert.equal((await fs.readdir(os.tmpdir())).some((name) => name.startsWith(TMP_PREFIX)), false);
  await fs.rm(root, { recursive: true, force: true });
});
