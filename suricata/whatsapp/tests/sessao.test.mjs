import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { DisconnectReason } from '@whiskeysockets/baileys';
import { abrirSessao } from '../sessao.mjs';

function fakeSocket() {
  const ev = new EventEmitter();
  const socket = { ev, ended: [], end(value) { this.ended.push(value); } };
  return socket;
}

function dependencies(socket, version = [2, 3000, 1015901307]) {
  const state = { creds: { me: null } };
  return {
    useMultiFileAuthState: async () => ({ state, saveCreds() {} }),
    fetchLatestBaileysVersion: async () => ({ version }),
    makeWASocket: (config) => {
      socket.config = config;
      return socket;
    },
  };
}

function authDir() {
  return path.join(os.tmpdir(), `suricata-session-test-${process.pid}`);
}

async function waitForSocket(socket) {
  while (!socket.config) await new Promise((resolve) => setImmediate(resolve));
}

test('configura o socket com Browsers.ubuntu e versão retornada pelo Baileys', async () => {
  const socket = fakeSocket();
  const version = [2, 2412, 1];
  const promise = abrirSessao(authDir(), { dependencies: dependencies(socket, version), closeDelayMs: 0 });
  await waitForSocket(socket);
  assert.deepEqual(socket.config.version, version);
  assert.deepEqual(socket.config.browser, ['Ubuntu', 'Suricata', '22.04.4']);
  assert.equal(socket.config.printQRInTerminal, false);
  assert.equal(socket.config.syncFullHistory, false);
  assert.equal(socket.config.markOnlineOnConnect, false);
  assert.equal(socket.config.shouldSyncHistoryMessage(), false);
  assert.equal(socket.config.logger.level, 'silent');
  socket.ev.emit('connection.update', { connection: 'open' });
  assert.equal(await promise, socket);
});

test('rejeita com motivo timeout e encerra o socket', async () => {
  const socket = fakeSocket();
  await assert.rejects(
    abrirSessao(authDir(), { timeoutMs: 5, dependencies: dependencies(socket), closeDelayMs: 0 }),
    (error) => error.motivo === 'timeout',
  );
  assert.deepEqual(socket.ended, [undefined]);
});

test('rejeita com motivo logged_out e encerra o socket', async () => {
  const socket = fakeSocket();
  const promise = abrirSessao(authDir(), { dependencies: dependencies(socket), closeDelayMs: 0 });
  await waitForSocket(socket);
  socket.ev.emit('connection.update', {
    connection: 'close',
    lastDisconnect: { error: { output: { statusCode: DisconnectReason.loggedOut } } },
  });
  await assert.rejects(promise, (error) => error.motivo === 'logged_out');
  assert.deepEqual(socket.ended, [undefined]);
});
