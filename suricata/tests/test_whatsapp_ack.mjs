import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { MESSAGE_ID, enviarComAck, esperarAck } from '../whatsapp/teste_idempotencia.mjs';

function socketMock(sendMessage) {
  return { ev: new EventEmitter(), sendMessage };
}

test('captura ACK emitido sincronamente pelo envio e preserva o messageId', async () => {
  const ev = new EventEmitter();
  const envios = [];
  const sock = {
    ev,
    async sendMessage(jid, content, options) {
      assert.equal(ev.listenerCount('messages.update'), 1, 'listener deve existir antes do envio');
      envios.push({ jid, content, options });
      ev.emit('messages.update', [{ key: { id: options.messageId }, update: { status: 2 } }]);
      return { key: { id: options.messageId } };
    },
  };

  const primeira = await enviarComAck(sock, 'grupo@g.us', 100);
  const segunda = await enviarComAck(sock, 'grupo@g.us', 100);

  assert.deepEqual(primeira, { ack: true, status: 2, timeout: false });
  assert.deepEqual(segunda, { ack: true, status: 2, timeout: false });
  assert.equal(envios.length, 2);
  assert.deepEqual(envios.map(({ options }) => options.messageId), [MESSAGE_ID, MESSAGE_ID]);
});

test('diferencia timeout de ACK real e ignora status abaixo de 2', async () => {
  const sock = socketMock(async () => undefined);
  const ack = esperarAck(sock, MESSAGE_ID, 10);
  sock.ev.emit('messages.update', [{ key: { id: MESSAGE_ID }, update: { status: 1 } }]);

  assert.deepEqual(await ack, { ack: false, status: null, timeout: true });
});
