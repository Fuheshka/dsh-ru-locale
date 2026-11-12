#!/usr/bin/env node
/**
 * Capture `ctx.locale.register(...)` calls from an installed client bundle by
 * running it in a VM with stubbed globals, a stubbed module loader, and a fake
 * client context whose locale service records registrations.
 *
 * Usage: node extract-plugin-locales-vm.cjs <bundle.js> [...]
 */
const fs = require('fs');
const vm = require('vm');

const noop = () => {};
const anyProxy = new Proxy(function any() {}, {
  get: (_t, prop) => {
    if (prop === 'then') return undefined;
    if (prop === Symbol.toPrimitive) return () => '';
    return anyProxy;
  },
  apply: () => anyProxy,
  construct: () => anyProxy,
});

function stubModule(id) {
  return new Proxy({ __esModule: true, default: anyProxy }, {
    get: (_t, prop) => {
      if (prop === '__esModule') return true;
      if (prop === 'then') return undefined;
      return anyProxy;
    },
  });
}

function capture(file) {
  const code = fs.readFileSync(file, 'utf8');
  const registrations = [];
  const modules = [];
  const loader = { load: (mod) => modules.push(mod) };

  const sandbox = {
    console: { log: noop, warn: noop, error: noop, info: noop, debug: noop },
    setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
    URL, URLSearchParams, TextEncoder, TextDecoder, performance,
    navigator: { language: 'ru', languages: ['ru'] },
    localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.self = sandbox;
  sandbox.document = {
    documentElement: { lang: 'ru', setAttribute: noop, style: {} },
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, addEventListener: noop }),
    head: { appendChild: noop },
    body: { appendChild: noop, classList: { add: noop, remove: noop } },
    addEventListener: noop,
    querySelector: () => null,
    querySelectorAll: () => [],
    getElementById: () => null,
  };
  sandbox.__ModuleLoader__ = loader;
  sandbox.__DSH_LOCALE__ = undefined;

  vm.createContext(sandbox);
  try {
    vm.runInContext(code, sandbox, { timeout: 15000 });
  } catch (error) {
    console.error(`# run failed for ${file}: ${error.message}`);
  }

  for (const mod of modules) {
    let plugin;
    try {
      plugin = mod.factory((id) => stubModule(id));
    } catch {
      continue;
    }
    if (!plugin || typeof plugin.apply !== 'function') continue;
    const locale = {
      register: (...args) => registrations.push(args),
      addLanguage: noop,
      bind: () => (key) => key,
      getSnapshot: () => ({ active: 'ru', locales: [], revision: 0 }),
      getLocale: () => ({ active: 'ru', locales: [], revision: 0 }),
      subscribe: () => noop,
      setLocale: noop,
      resolveText: (text) => (typeof text === 'string' ? text : text?.en ?? ''),
    };
    const ctx = new Proxy({}, {
      get: (_t, prop) => {
        if (prop === 'locale') return locale;
        if (prop === 'effect') return (fn) => { try { return fn(); } catch { return undefined; } };
        if (prop === 'inject') return () => undefined;
        if (prop === 'fiber') return { uid: 1 };
        if (prop === 'get') return () => undefined;
        return anyProxy;
      },
    });
    try {
      plugin.apply(ctx);
    } catch {
      /* slot registration needs real services; registrations captured so far are enough */
    }
  }

  const out = {};
  for (const args of registrations) {
    const [ns, ...rest] = args;
    if (typeof ns !== 'string') continue;
    if (rest.length >= 2 && typeof rest[0] === 'string' && rest[1] && typeof rest[1] === 'object') {
      out[ns] = out[ns] || {};
      out[ns][rest[0]] = rest[1];
    } else if (rest.length === 1 && rest[0] && typeof rest[0] === 'object') {
      out[ns] = out[ns] || {};
      for (const [locale, dict] of Object.entries(rest[0])) {
        if (dict && typeof dict === 'object') out[ns][locale] = dict;
      }
    }
  }
  return out;
}

const result = {};
for (const file of process.argv.slice(2)) {
  try {
    Object.assign(result, capture(file));
  } catch (error) {
    console.error(`# failed ${file}: ${error.message}`);
  }
}
process.stdout.write(JSON.stringify(result, null, 1));
