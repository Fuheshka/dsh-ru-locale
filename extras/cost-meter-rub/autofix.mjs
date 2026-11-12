#!/usr/bin/env node
/**
 * Auto-fixer for the dsh-cost-meter RUB / DUAL patch.
 *
 * Scans every DSH profile that has dsh-cost-meter installed, runs the
 * idempotent patch.mjs --if-needed, and records the result. Designed to be
 * started by launchd every minute; it does nothing when the plugin is
 * already patched, and writes a snapshot before touching a new version.
 *
 * Logs:   autofix.log
 * State:  autofix-state.json
 * Lock:   .autofix.lock
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const PATCH = path.join(DIR, 'patch.mjs');
const LOG = path.join(DIR, 'autofix.log');
const STATE_FILE = path.join(DIR, 'autofix-state.json');
const LOCK_FILE = path.join(DIR, '.autofix.lock');
const BACKUP_DIR = path.join(DIR, 'backup');
const PROFILES = process.env.DSH_AUTOFIX_PROFILES || path.join(os.homedir(), '.dsh', 'profiles');
const LABEL = 'dsh-cost-meter RUB auto-fixer';

function now() {
  return new Date().toISOString();
}

function log(line) {
  try {
    fs.appendFileSync(LOG, '[' + now() + '] ' + line + '\n');
    if (fs.existsSync(LOG) && fs.statSync(LOG).size > 512 * 1024) {
      const tail = fs.readFileSync(LOG, 'utf8').slice(-200 * 1024);
      fs.writeFileSync(LOG, tail);
    }
  } catch {}
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}

function writeJson(file, value) {
  const tmp = file + '.tmp-' + process.pid;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2) + '\n', 'utf8');
  fs.renameSync(tmp, file);
}

function notify(message) {
  try {
    execFileSync('/usr/bin/osascript', ['-e',
      'display notification ' + JSON.stringify(String(message).slice(0, 180)) +
      ' with title ' + JSON.stringify(LABEL)], { stdio: 'ignore', timeout: 10000 });
  } catch {}
}

function acquireLock() {
  try {
    fs.writeFileSync(LOCK_FILE, String(process.pid), { flag: 'wx' });
    return true;
  } catch (e) {
    if (e.code !== 'EEXIST') return false;
    try {
      const age = Date.now() - fs.statSync(LOCK_FILE).mtimeMs;
      if (age < 10 * 60 * 1000) return false;
      fs.rmSync(LOCK_FILE, { force: true });
      fs.writeFileSync(LOCK_FILE, String(process.pid), { flag: 'wx' });
      return true;
    } catch {
      return false;
    }
  }
}

function releaseLock() {
  try { fs.rmSync(LOCK_FILE, { force: true }); } catch {}
}

function parseResult(stdout) {
  const line = String(stdout || '').trim().split('\n').filter(Boolean).pop();
  if (!line || !line.startsWith('{')) return null;
  try { return JSON.parse(line); } catch { return null; }
}

function firstError(stderr, stdout) {
  const text = String(stderr || '').trim() || String(stdout || '').trim();
  const line = text.split('\n').find((l) => l.startsWith('FAIL:') || l.startsWith('Error:')) || text.split('\n')[0];
  return line ? line.slice(0, 400) : 'unknown error';
}

if (!acquireLock()) process.exit(0);

const state = readJson(STATE_FILE, { profiles: {}, failures: {} });
state.failures ||= {};
let changedState = false;

try {
  if (!fs.existsSync(PROFILES)) {
    log('no DSH profiles directory at ' + PROFILES);
    releaseLock();
    process.exit(0);
  }

  const profiles = fs.readdirSync(PROFILES, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();

  for (const profile of profiles) {
    const pluginDir = path.join(PROFILES, profile, 'node_modules', 'dsh-cost-meter');
    const pkgFile = path.join(pluginDir, 'package.json');
    if (!fs.existsSync(pkgFile)) continue;

    let version = 'unknown';
    try { version = JSON.parse(fs.readFileSync(pkgFile, 'utf8')).version || version; } catch {}

    const patchState = path.join(DIR, '.patch-state-' + profile + '.json');
    const result = spawnSync(process.execPath, [PATCH, '--if-needed'], {
      cwd: DIR,
      env: {
        ...process.env,
        DSH_COST_METER_DIR: pluginDir,
        DSH_COST_METER_STATE: patchState,
        DSH_COST_METER_BACKUP: BACKUP_DIR,
      },
      encoding: 'utf8',
      timeout: 120000,
    });

    const parsed = parseResult(result.stdout);
    const previous = state.profiles[profile] || {};

    if (result.status !== 0 || !parsed || parsed.ok !== true) {
      const error = firstError(result.stderr, result.stdout);
      const key = version + '|' + error;
      if (state.failures[profile] !== key) {
        log('FAIL ' + profile + ' ' + version + ': ' + error);
        notify('Не удалось применить патч к ' + profile + ' ' + version + '. Подробности в autofix.log');
        state.failures[profile] = key;
      }
      state.profiles[profile] = { version, status: 'error', error, at: now() };
      changedState = true;
      continue;
    }

    if (state.failures[profile]) {
      delete state.failures[profile];
      changedState = true;
    }

    if (parsed.applied) {
      log('applied ' + profile + ' ' + version + ': ' + (parsed.changed || []).join(', '));
      state.profiles[profile] = {
        version,
        status: 'ok',
        appliedAt: now(),
        changed: parsed.changed || [],
      };
      changedState = true;
    } else if (previous.status !== 'ok' || previous.version !== version) {
      state.profiles[profile] = { version, status: 'ok', checkedAt: now(), changed: [] };
      changedState = true;
    } else {
      state.profiles[profile] = { ...previous, checkedAt: now() };
      changedState = true;
    }
  }
} catch (e) {
  const error = String(e && e.stack || e).slice(0, 800);
  log('FAIL unhandled: ' + error);
  state.fatal = error;
  changedState = true;
} finally {
  if (changedState) writeJson(STATE_FILE, state);
  releaseLock();
}
