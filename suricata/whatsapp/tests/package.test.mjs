import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import {
  MESSAGE_ID,
  enviarComAck,
  sanitizarErro,
} from '../teste_idempotencia.mjs';
import { ambienteCloudOuCi, modoLocalPermitido } from '../parear.mjs';
import { parseBatch, imprimirErro } from '../enviar.mjs';

const AUTH_DIR = path.join(os.tmpdir(), 'suricata-whatsapp-auth');
const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const INTERACTIVE_RUNTIME = {
  stdin: { isTTY: true }, stdout: { isTTY: true }, stderr: { isTTY: true }
};


test('o pacote valida lote e rejeita autenticação dentro do pacote', () => {
  const batch = parseBatch(JSON.stringify({
    auth_dir: AUTH_DIR,
    grupo_jid: '5511999999999-123@g.us',
    mensagens: [{
      event_id: 'evento-1',
      message_id: MESSAGE_ID,
      texto: 'aviso público',
    }],
  }));

  assert.equal(batch.grupoJid, '5511999999999-123@g.us');
  assert.equal(batch.mensagens[0].messageId, MESSAGE_ID);
  assert.throws(
    () => parseBatch(JSON.stringify({
      auth_dir: path.join(PACKAGE_ROOT, 'auth'),
      grupo_jid: '5511999999999-123@g.us',
      mensagens: [{ event_id: 'e', message_id: MESSAGE_ID, texto: 'x' }],
    })),
    /diretório de autenticação dentro do repo|repo/i,
  );
});

test('arquivo completo sem .git prioriza a raiz sobre o pacote Suricata', async () => {
  const arquivo = fs.mkdtempSync(path.join(os.tmpdir(), 'suricata-arquivo-completo-'));
  const externa = fs.mkdtempSync(path.join(os.tmpdir(), 'suricata-auth-externa-'));
  const modulePath = path.join(arquivo, 'suricata', 'whatsapp', 'auth-dir.mjs');
  try {
    fs.mkdirSync(path.dirname(modulePath), { recursive: true });
    fs.writeFileSync(path.join(arquivo, 'AGENTS.md'), '# fixture\n');
    fs.writeFileSync(path.join(arquivo, 'suricata', 'whatsapp', 'package.json'), '{}\n');
    fs.copyFileSync(path.join(PACKAGE_ROOT, 'auth-dir.mjs'), modulePath);

    const auth = await import(`${pathToFileURL(modulePath).href}?fixture=${Date.now()}`);
    assert.equal(auth.REPO_ROOT, arquivo);
    assert.throws(() => auth.validarAuthDir(path.join(arquivo, 'suricata')), /dentro do repo/i);
    assert.equal(auth.validarAuthDir(externa), externa);
  } finally {
    fs.rmSync(arquivo, { recursive: true, force: true });
    fs.rmSync(externa, { recursive: true, force: true });
  }
});

test('o ACK síncrono é capturado antes do envio', async () => {
  const ev = new EventEmitter();
  const sent = [];
  const sock = {
    ev,
    async sendMessage(jid, content, options) {
      sent.push({ jid, content, options });
      ev.emit('messages.update', [{ key: { id: options.messageId }, update: { status: 2 } }]);
    },
  };

  const result = await enviarComAck(sock, 'grupo@g.us', 100);
  assert.deepEqual(result, { ack: true, status: 2, timeout: false });
  assert.equal(sent[0].options.messageId, MESSAGE_ID);
});

test('políticas de execução e erros não expõem dados externos', () => {
  assert.equal(modoLocalPermitido({ SURICATA_WHATSAPP_LOCAL: '1' }, INTERACTIVE_RUNTIME), true);
  assert.equal(modoLocalPermitido({ SURICATA_WHATSAPP_LOCAL: '1' }, {
    stdin: { isTTY: false }, stdout: { isTTY: false }, stderr: { isTTY: false }
  }), false);
  assert.equal(ambienteCloudOuCi({ K_SERVICE: 'suricata' }), true);
  assert.equal(sanitizarErro(Object.assign(new Error('jid=5511999999999@s.whatsapp.net'), { code: 'ECONNRESET' })), 'Error: falha de transporte');
  const { detalhe, ...resto } = imprimirErro(new Error('URL secreta'));
  assert.deepEqual(resto, { sessao: 'erro', resultados: [], erro: 'falha no transporte WhatsApp' });
  // detalhe é lista branca de texto simples; nada com URL, @, = ou dígitos longos.
  assert.doesNotMatch(detalhe, /[@=\/]|\d{6,}/);
  assert.equal(imprimirErro(new Error('https://x.invalid/a?token=1')).detalhe, 'Error: <omitido>');
});

test('classifica falha segura da ponte com código e fase', () => {
  const erro = Object.assign(new Error('tempo excedido no envio WhatsApp'), {
    code: 'TIMEOUT',
    phase: 'send_message',
  });
  const resultado = imprimirErro(erro);
  assert.equal(resultado.failure_code, 'TIMEOUT');
  assert.equal(resultado.phase, 'send_message');
  assert.equal(resultado.sessao, 'timeout');
});
