import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  main,
  validar,
  mensagemErroSegura,
  modoLocalPermitido,
  terminalLocalInterativo,
  ambienteCloudOuCi,
  listarGrupos,
  limparGruposAposConfirmacao,
  caminhoGrupos
} from '../whatsapp/parear.mjs';

const INTERACTIVE_RUNTIME = {
  stdin: { isTTY: true },
  stdout: { isTTY: true },
  stderr: { isTTY: true },
  env: {}
};

function localEnv(extra = {}) {
  return {
    ...process.env,
    ...extra,
    SURICATA_WHATSAPP_LOCAL: '1',
    CI: '',
    GITHUB_ACTIONS: '',
    K_SERVICE: '',
    CLOUD_RUN_JOB: '',
    CLOUD_RUN_SERVICE: '',
    BUILD_ID: '',
    BUILD_NUMBER: ''
  };
}

async function criarFixtureAuth(prefixo) {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), prefixo));
  const authDir = path.join(temp, '.wa-auth');
  await fs.mkdir(authDir);
  await fs.writeFile(path.join(authDir, 'creds.json'), '{}\n', { mode: 0o600 });
  return { temp, authDir };
}

test('bloqueia pareamento sem modo local explícito', () => {
  assert.equal(modoLocalPermitido({}, INTERACTIVE_RUNTIME), false);
  assert.equal(modoLocalPermitido({ SURICATA_WHATSAPP_LOCAL: '1' }, INTERACTIVE_RUNTIME), true);
  assert.equal(terminalLocalInterativo({
    stdin: { isTTY: true }, stdout: { isTTY: true }, stderr: { isTTY: false }
  }), false);
  // Um marcador de ambiente não transforma um processo sem TTY em terminal local.
  assert.equal(modoLocalPermitido({ SURICATA_WHATSAPP_LOCAL: '1' }, {
    stdin: { isTTY: false }, stdout: { isTTY: false }, stderr: { isTTY: false }
  }), false);
});

test('bloqueia Cloud/CI mesmo quando o modo local foi solicitado', () => {
  assert.equal(ambienteCloudOuCi({ SURICATA_WHATSAPP_LOCAL: '1', CI: 'true' }), true);
  assert.equal(ambienteCloudOuCi({ SURICATA_WHATSAPP_LOCAL: '1', K_SERVICE: 'suricata' }), true);
  assert.rejects(
    () => main(['--auth-dir', path.join(os.tmpdir(), 'suricata-cloud-auth')], {
      env: { ...process.env, SURICATA_WHATSAPP_LOCAL: '1', CI: 'true' }
    }),
    (error) => error.code === 'SURICATA_LOCAL_ONLY'
  );
});

test('não vaza erro Baileys com JID, URL ou payload', async () => {
  const segredo = 'jid 5511999999999@s.whatsapp.net https://wa.example/x payload noiseKey';
  const { temp, authDir } = await criarFixtureAuth('suricata-parear-baileys-');
  try {
    await assert.rejects(
      () => main(['--auth-dir', authDir], {
        env: localEnv(),
        runtime: INTERACTIVE_RUNTIME,
        fetchLatestBaileysVersion: async () => ({ version: [1, 2, 3] }),
        makeWASocket: () => { throw Object.assign(new Error(segredo), { name: 'BaileysError' }); },
        useMultiFileAuthState: async () => ({ state: {}, saveCreds: () => {} })
      }),
      (error) => {
        const seguro = mensagemErroSegura(error);
        assert.match(seguro, /^Falha no pareamento \(/);
        assert.ok(seguro.length <= 200);
        assert.doesNotMatch(seguro, /5511999999999|wa\.example|noiseKey|payload/);
        return true;
      }
    );
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
});

test('diretório inválido falha sem expor caminho', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'suricata-parear-'));
  const arquivo = path.join(temp, 'nao-e-diretorio');
  await fs.writeFile(arquivo, 'fixture');
  try {
    await assert.rejects(
      () => main(['--auth-dir', arquivo], { env: localEnv(), runtime: INTERACTIVE_RUNTIME }),
      (error) => {
        const seguro = mensagemErroSegura(error);
        assert.match(seguro, /^Diretório de autenticação inválido\.$/);
        assert.doesNotMatch(seguro, /nao-e-diretorio|C:\\|\//);
        return true;
      }
    );
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
});

test('rejeita auth-dir que usa symlink para dentro do repositório', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'suricata-symlink-'));
  const link = path.join(temp, 'auth-link');
  try {
    await fs.symlink(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), link, 'junction');
    assert.throws(() => validar({ authDir: link, png: null, codigo: null }), /inválido|repo/);
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
});

test('não imprime QR nem código de pareamento', async () => {
  const { temp, authDir } = await criarFixtureAuth('suricata-parear-stdout-');
  const linhas = [];
  const originalLog = console.log;
  const { EventEmitter } = await import('node:events');
  const ev = new EventEmitter();
  try {
    console.log = (...args) => linhas.push(args.join(' '));
    await main(['--auth-dir', authDir, '--codigo', '5511999999999'], {
      env: localEnv(),
      runtime: INTERACTIVE_RUNTIME,
      useMultiFileAuthState: async () => ({ state: {}, saveCreds: () => {} }),
      fetchLatestBaileysVersion: async () => ({ version: [1, 2, 3] }),
      makeWASocket: () => {
        const sock = { ev, requestPairingCode: async () => 'SEGREDO-123', end: () => {} };
        queueMicrotask(() => ev.emit('connection.update', { connection: 'connecting' }));
        queueMicrotask(() => ev.emit('connection.update', { connection: 'close' }));
        return sock;
      }
    });
    const output = linhas.join('\n');
    assert.doesNotMatch(output, /SEGREDO-123|QR|5511999999999/);
    assert.match(output, /codigo_pareamento_disponivel/);
    process.exitCode = 0;
  } finally {
    console.log = originalLog;
    await fs.rm(temp, { recursive: true, force: true });
  }
});

test('preserva grupos.json até a escolha H2', async () => {
  const { temp, authDir } = await criarFixtureAuth('suricata-parear-h2-');
  const grupos = path.join(temp, 'grupos.json');
  const sock = { groupFetchAllParticipating: async () => ({
    turma: { subject: 'Turma', id: '123@g.us', participants: [] }
  }) };
  try {
    await listarGrupos(sock, authDir);
    assert.equal((await fs.stat(grupos)).isFile(), true);
    assert.match(await fs.readFile(grupos, 'utf8'), /Turma/);
    assert.deepEqual((await fs.readdir(temp)).filter((nome) => nome.includes('.tmp-')), []);
    assert.equal(await limparGruposAposConfirmacao(authDir), false);
    assert.equal((await fs.stat(grupos)).isFile(), true);
    assert.equal(await limparGruposAposConfirmacao(authDir, { confirmado: true }), true);
    await assert.rejects(() => fs.stat(caminhoGrupos(authDir)), { code: 'ENOENT' });
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
});
