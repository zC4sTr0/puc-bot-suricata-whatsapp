#!/usr/bin/env node
// Lista os grupos em que o chip participa: nome, JID e quantidade de participantes.
// Nunca imprime números de telefone, sessão ou conteúdo de mensagens.
import process from 'node:process';
import { abrirSessao, fecharSessao } from './sessao.mjs';

async function main() {
  const i = process.argv.indexOf('--auth-dir');
  const authDir = i >= 0 ? process.argv[i + 1] : null;
  let sock;
  try {
    sock = await abrirSessao(authDir, { timeoutMs: 45_000 });
    const grupos = await sock.groupFetchAllParticipating();
    const lista = Object.values(grupos).map((g) => ({
      nome: String(g.subject ?? '').slice(0, 100),
      jid: g.id,
      participantes: Array.isArray(g.participants) ? g.participants.length : null,
    }));
    console.log(JSON.stringify({ sessao: 'ok', grupos: lista }));
  } catch (error) {
    const sessao = error?.motivo === 'logged_out' ? 'logged_out' : error?.motivo === 'timeout' ? 'timeout' : 'erro';
    console.log(JSON.stringify({ sessao, grupos: [], erro: error?.safeMessage ? String(error.message).slice(0, 160) : 'falha' }));
    process.exitCode = sessao === 'logged_out' ? 10 : 1;
  } finally {
    if (sock) await fecharSessao(sock);
  }
}

main();
