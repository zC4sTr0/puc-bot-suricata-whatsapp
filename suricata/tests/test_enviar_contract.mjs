import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseBatch, parseArgs, imprimirErro, validarAuthDir } from '../whatsapp/enviar.mjs';
import { REPO_ROOT } from '../whatsapp/auth-dir.mjs';

const repoAuthDir = path.join(REPO_ROOT, 'auth');
const validAuthDir = path.join(os.tmpdir(), 'suricata-auth');
const duplicateAuthDir = path.join(os.tmpdir(), 'suricata-duplicate-auth');

const valid = {
  auth_dir: validAuthDir,
  grupo_jid: '5511999999999-123456@g.us',
  mensagens: [{
    event_id: 'evento-1',
    message_id: '3EB0A1B2C3D4E5F6071829',
    texto: 'aviso público'
  }]
};

test('aceita lote mínimo do contrato WhatsApp', () => {
  assert.deepEqual(parseBatch(JSON.stringify(valid)), {
    authDir: path.resolve(validAuthDir),
    grupoJid: valid.grupo_jid,
    mensagens: [{ eventId: 'evento-1', messageId: '3EB0A1B2C3D4E5F6071829', texto: 'aviso público' }]
  });
});

test('rejeita lote com event_id ou message_id duplicado antes do envio', () => {
  for (const campo of [
    { mensagens: [valid.mensagens[0], { ...valid.mensagens[0], event_id: valid.mensagens[0].event_id + '-novo' }] },
    { mensagens: [{ ...valid.mensagens[0], event_id: 'evento-2' }, { ...valid.mensagens[0], message_id: '3EB0A1B2C3D4E5F6071829' }] },
  ]) {
    assert.throws(() => parseBatch(JSON.stringify({ ...valid, ...campo })), (error) => {
      assert.equal(error.safeMessage, true);
      assert.equal(error.code, 'INVALID_INPUT');
      assert.match(error.message, /duplicado/);
      assert.doesNotMatch(error.message, /evento-1|3EB0A1B2C3D4E5F6071829/);
      return true;
    });
  }
});

test('recusa identificador, JID ou texto fora do contrato', () => {
  for (const campo of [
    { mensagens: [{ ...valid.mensagens[0], message_id: 'abc' }] },
    { grupo_jid: 'grupo' },
    { mensagens: [{ ...valid.mensagens[0], texto: '' }] },
    { auth_dir: repoAuthDir },
  ]) {
    assert.throws(() => parseBatch(JSON.stringify({ ...valid, ...campo })), /inválid|repo/);
  }
});

test('rejeita auth-dir com symlink que aponta para o repositório', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'suricata-enviar-symlink-'));
  const link = path.join(temp, 'auth-link');
  try {
    await fs.symlink(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), link, 'junction');
    assert.throws(() => validarAuthDir(link), /inválido|repo/);
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
});

test('rejeita raiz e qualquer subdiretório do repositório', () => {
  for (const authDir of [REPO_ROOT, path.join(REPO_ROOT, 'docs')]) {
    assert.throws(() => validarAuthDir(authDir), /repo/);
  }
});

test('resolve diretório de autenticação por variável de ambiente', () => {
  const args = parseArgs(['--auth-dir', validAuthDir]);
  assert.equal(args.authDir, path.resolve(validAuthDir));
});

test('rejeita --auth-dir sem valor ou com próximo argumento', () => {
  for (const argv of [['--auth-dir'], ['--auth-dir', '--timeout-ms']]) {
    assert.throws(() => parseArgs(argv), (error) => {
      assert.equal(error.safeMessage, true);
      assert.match(error.message, /valor.*--auth-dir/);
      assert.doesNotMatch(error.message, /timeout-ms/);
      return true;
    });
  }
});

test('rejeita --timeout-ms sem valor ou com próximo argumento', () => {
  for (const argv of [['--timeout-ms'], ['--timeout-ms', '--auth-dir']]) {
    assert.throws(() => parseArgs(argv), (error) => {
      assert.equal(error.safeMessage, true);
      assert.match(error.message, /valor.*--timeout-ms/);
      assert.doesNotMatch(error.message, /auth-dir/);
      return true;
    });
  }
});

test('rejeita opções singleton duplicadas sem expor valores', () => {
  for (const argv of [
    ['--timeout-ms', '1000', '--timeout-ms', '2000'],
    ['--auth-dir', validAuthDir, '--auth-dir', duplicateAuthDir],
  ]) {
    assert.throws(() => parseArgs(argv), (error) => {
      assert.equal(error.safeMessage, true);
      assert.equal(error.code, 'INVALID_INPUT');
      assert.match(error.message, /opção repetida/);
      assert.doesNotMatch(error.message, /1000|2000|suricata-auth/);
      return true;
    });
  }
});

test('classifica erros de sessão sem expor transporte ou identificadores', () => {
  const loggedOut = Object.assign(new Error('sessão desconectada'), { motivo: 'logged_out', safeMessage: true });
  const timeout = Object.assign(new Error('tempo excedido'), { motivo: 'timeout', safeMessage: true });
  assert.equal(imprimirErro(loggedOut).sessao, 'logged_out');
  assert.equal(imprimirErro(timeout).sessao, 'timeout');
  assert.deepEqual(imprimirErro(new Error('jid=5511999999999@g.us https://secret.invalid')), {
    sessao: 'erro', resultados: [], erro: 'falha no transporte WhatsApp', detalhe: 'Error: <omitido>'
  });
  // Mensagem simples do Baileys passa, com o código Boom: é o que permite diagnosticar na nuvem.
  const fechada = Object.assign(new Error('Connection Closed'), { output: { statusCode: 428 } });
  assert.equal(imprimirErro(fechada).detalhe, 'Error: Connection Closed (428)');
});

test('aceita JID de grupo moderno sem hífen e recusa JID de pessoa', () => {
  const base = { auth_dir: path.join(os.tmpdir(), 'suricata-wa-contrato'), mensagens: [{ event_id: 'e', message_id: '3EB0' + 'A'.repeat(18), texto: 'x' }] };
  assert.equal(parseBatch(JSON.stringify({ ...base, grupo_jid: '120363000000000000@g.us' })).grupoJid, '120363000000000000@g.us');
  assert.throws(() => parseBatch(JSON.stringify({ ...base, grupo_jid: '5511999999999@s.whatsapp.net' })));
});

test('ACK do servidor chega pelo stanza ack do WebSocket (Baileys 6.7.24 não emite evento)', async () => {
  const { EventEmitter } = await import('node:events');
  const { esperarAck } = await import('../whatsapp/enviar.mjs');
  const id = '3EB0' + 'B'.repeat(18);
  const sock = { ev: new EventEmitter(), ws: new EventEmitter() };
  const ok = esperarAck(sock, id, 200);
  sock.ws.emit('CB:ack,class:message', { attrs: { id: '3EB0' + 'C'.repeat(18) } });
  sock.ws.emit('CB:ack,class:message', { attrs: { id } });
  assert.deepEqual(await ok, { ack: true, status: 2, timeout: false });
  assert.equal(sock.ws.listenerCount('CB:ack,class:message'), 0);
  const erro = esperarAck(sock, id, 200);
  sock.ws.emit('CB:ack,class:message', { attrs: { id, error: '479' } });
  assert.deepEqual(await erro, { ack: false, status: null, timeout: false, erro: 'ack_error_479' });
  const semWs = await esperarAck({ ev: new EventEmitter() }, id, 20);
  assert.equal(semWs.timeout, true);
});
