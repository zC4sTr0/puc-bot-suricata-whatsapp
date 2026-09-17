import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  main,
  parseArgs,
  imprimirErro,
  contarGrupos,
} from '../whatsapp/verificar.mjs';

function captureConsole() {
  const stdout = [];
  const stderr = [];
  const originalLog = console.log;
  const originalError = console.error;
  console.log = (...args) => stdout.push(args.join(' '));
  console.error = (...args) => stderr.push(args.join(' '));
  return {
    stdout,
    stderr,
    restore() {
      console.log = originalLog;
      console.error = originalError;
    },
  };
}

test('aceita auth-dir externo e conta grupos sem expor dados', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'suricata-verificar-'));
  const authDir = path.join(temp, '.wa-auth');
  await fs.mkdir(authDir);
  await fs.writeFile(path.join(authDir, 'creds.json'), '{}\n', { mode: 0o600 });
  const output = captureConsole();
  const calls = [];
  try {
    await main(['--auth-dir', authDir], {
      abrirSessao: async (authDir) => {
        calls.push(['abrir', authDir]);
        return {
          async groupFetchAllParticipating() {
            return {
              '5511999999999-123@g.us': { subject: 'Turma secreta' },
              '5511888888888-456@g.us': { subject: 'Outro grupo' },
            };
          },
        };
      },
      fecharSessao: async () => calls.push(['fechar']),
    });
  } finally {
    output.restore();
    await fs.rm(temp, { recursive: true, force: true });
  }

  assert.deepEqual(output.stdout, [JSON.stringify({ sessao: 'ok', grupos: 2 })]);
  assert.deepEqual(output.stderr, []);
  assert.deepEqual(calls, [['abrir', path.resolve(authDir)], ['fechar']]);
  assert.doesNotMatch(output.stdout[0], /Turma|5511999999999|@g\.us/);
});

test('conta listas e mapas, sem serializar os grupos', () => {
  assert.equal(contarGrupos([{ id: 'segredo@g.us' }]), 1);
  assert.equal(contarGrupos({ 'segredo@g.us': { subject: 'nome' } }), 1);
});

test('erro externo vira JSON sanitizado sem caminho, token ou payload', () => {
  const error = new Error('https://wa.example/segredo token=abc cookie=xyz jid=5511999999999@g.us payload=oculto');
  assert.deepEqual(imprimirErro(error), {
    sessao: 'erro',
    grupos: 0,
    erro: 'falha no transporte WhatsApp',
  });
});

test('argumentos inválidos não incorporam o valor recebido na mensagem', () => {
  assert.throws(() => parseArgs(['--auth-dir', '--timeout-ms']), (error) => {
    assert.equal(error.safeMessage, true);
    assert.equal(error.code, 'INVALID_INPUT');
    assert.match(error.message, /valor ausente/);
    assert.doesNotMatch(error.message, /timeout-ms/);
    return true;
  });
});

test('rejeita opções singleton duplicadas sem expor valores', () => {
  for (const argv of [
    ['--timeout-ms', '1000', '--timeout-ms', '2000'],
    ['--auth-dir', path.join(os.tmpdir(), 'suricata-verificar-duplicate-auth'), '--auth-dir', path.join(os.tmpdir(), 'suricata-segredo-auth')],
  ]) {
    assert.throws(() => parseArgs(argv), (error) => {
      assert.equal(error.safeMessage, true);
      assert.equal(error.code, 'INVALID_INPUT');
      assert.match(error.message, /opção repetida/);
      assert.doesNotMatch(error.message, /1000|2000|suricata-(verificar-duplicate|segredo)-auth/);
      return true;
    });
  }
});
