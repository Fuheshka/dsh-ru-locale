#!/usr/bin/env node
/**
 * dsh-cost-meter RUB / dual-currency patch
 * ---------------------------------------
 * Adds RUB (₽) next to USD/CNY/EUR and a "DUAL" mode that renders money as
 * "₽4.54 / $0.0549". Also switches the daily FX refresh to a source that
 * publishes RUB, so the rate updates automatically.
 *
 * Idempotent: safe to re-run after plugin updates.
 *
 * Usage:
 *   node patch.mjs                 # apply with the default RUB rate
 *   node patch.mjs --rate=82.66    # update the RUB preset / fallback rate
 *   node patch.mjs --check         # dry-run: report status, change nothing
 *   node patch.mjs --restore       # restore *.rub-bak backups
 *
 * Active display currency is stored in
 * ~/.dsh/storages/cost-meter/ledger.json and switched in DSH:
 * Settings -> Cost -> Display -> Currency.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const PLUGIN_DIR = process.env.DSH_COST_METER_DIR ||
  path.join(os.homedir(), '.dsh/profiles/desktop/node_modules/dsh-cost-meter');
const LIB = path.join(PLUGIN_DIR, 'lib');
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = process.env.DSH_COST_METER_STATE || path.join(SCRIPT_DIR, 'patch-state.json');
const BACKUP_DIR = process.env.DSH_COST_METER_BACKUP || path.join(SCRIPT_DIR, 'backup');
const CHECK = process.argv.includes('--check');
const RESTORE = process.argv.includes('--restore');
const IF_NEEDED = process.argv.includes('--if-needed');
const rateArg = process.argv.find((a) => a.startsWith('--rate='));
const RATE_EXPLICIT = Boolean(rateArg);
const RATE = rateArg ? Number(rateArg.split('=')[1]) : 82.6617;

if (!Number.isFinite(RATE) || RATE <= 0) {
  console.error('Invalid --rate');
  process.exit(2);
}
if (!fs.existsSync(path.join(PLUGIN_DIR, 'package.json'))) {
  console.error('FAIL: dsh-cost-meter not found at ' + PLUGIN_DIR);
  process.exit(1);
}
const VERSION = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, 'package.json'), 'utf8')).version || 'unknown';

const FILES = [
  'client.js',
  'client.display.js',
  'client.statistics.js',
  'typert.host.js',
  'billing-export.js',
  'index.js',
  'exchange-rates.js',
  'exchange-rate-refresh.js',
  'pricing.js',
];
const report = [];

function fail(msg) {
  console.error('FAIL: ' + msg);
  process.exit(1);
}

function replaceOnce(src, from, to, label) {
  const n = src.split(from).length - 1;
  if (n !== 1) fail(label + ': expected exactly 1 anchor, found ' + n);
  return src.replace(from, () => to);
}

function patchPreset(src) {
  const presetRe = /RUB:\{symbol:"₽",decimals:\d+,exchangeRate:[\d.]+\}(?:,DUAL:\{symbol:"₽",decimals:\d+,exchangeRate:[\d.]+\})?/;
  const existing = presetRe.exec(src);
  if (existing) {
    // Без явного --rate сохраняем уже настроенный курс, чтобы авто-фиксер
    // не откатывал ручную настройку при каждом запуске.
    const current = Number((/exchangeRate:([\d.]+)/.exec(existing[0]) || [])[1]);
    const rate = RATE_EXPLICIT ? RATE : (Number.isFinite(current) && current > 0 ? current : RATE);
    return src.replace(presetRe,
      'RUB:{symbol:"₽",decimals:2,exchangeRate:' + rate + '},' +
      'DUAL:{symbol:"₽",decimals:2,exchangeRate:' + rate + '}');
  }
  return replaceOnce(
    src,
    'EUR:{symbol:"€",decimals:6,exchangeRate:.92}}',
    'EUR:{symbol:"€",decimals:6,exchangeRate:.92},' +
    'RUB:{symbol:"₽",decimals:2,exchangeRate:' + RATE + '},' +
    'DUAL:{symbol:"₽",decimals:2,exchangeRate:' + RATE + '}}',
    'currency preset'
  );
}

function patchJo(src) {
  if (src.includes('RUB:"₽",DUAL:"₽"')) return src;
  if (src.includes('RUB:"₽"}')) {
    return replaceOnce(src, 'RUB:"₽"}', 'RUB:"₽",DUAL:"₽"}', 'balance symbol map');
  }
  return replaceOnce(
    src,
    'const Jo={USD:"$",CNY:"¥",EUR:"€"};',
    'const Jo={USD:"$",CNY:"¥",EUR:"€",RUB:"₽",DUAL:"₽"};',
    'balance symbol map'
  );
}

const OLD_G = 'function G(e,t){const o=Number(t?.exchangeRate),a=e*(Number.isFinite(o)&&o>0?o:1);return me(a,t)}';
const NEW_G = 'function G(e,t){const o=Number(t?.exchangeRate),a=e*(Number.isFinite(o)&&o>0?o:1);if(String(t?.currency).toUpperCase()==="DUAL"){const d=Math.max(2,Math.min(4,Math.floor(Number(t?.decimals)||2))),u=4;return me(a,{symbol:"₽",decimals:d})+" / "+me(e,{symbol:"$",decimals:u})}return me(a,t)}';

function patchFormatCost(src) {
  if (src.includes('u=4;')) return src;
  const v1 = 'if(String(t?.currency).toUpperCase()==="DUAL"){const d=Math.max(0,Math.min(10,Math.floor(Number(t?.decimals)||2))),u=Math.max(4,d);';
  const v2 = 'if(String(t?.currency).toUpperCase()==="DUAL"){const d=Math.max(2,Math.min(4,Math.floor(Number(t?.decimals)||2))),u=4;';
  if (src.includes(v1)) return replaceOnce(src, v1, v2, 'cost formatter precision');
  return replaceOnce(src, OLD_G, NEW_G, 'cost formatter');
}

const OLD_JE = 'function je(e,t,o){const a=typeof o=="string"?o.toUpperCase():"",s=typeof t?.symbol=="string"&&t.symbol.length>0?t.symbol:"$";return me(e,{symbol:Jo[a]??s,decimals:Math.max(2,Math.min(10,Math.floor(Number(t?.decimals)||2)))})}';
const CURRENT_JE = 'function je(e,t,o){const a=typeof o=="string"?o.toUpperCase():"",d=typeof t?.currency=="string"?t.currency.toUpperCase():"",fx=t?.fxRates??{};let v=Number(e)||0,raw=0;if(a&&d&&a!==d){raw=a==="USD"?1:a==="CNY"?Number(fx.CNY):a==="EUR"?Number(fx.EUR):0;const dr=Number(t?.exchangeRate);if(raw>0&&dr>0)v=v/raw*dr}const s=typeof t?.symbol=="string"&&t.symbol.length>0?t.symbol:"$";return me(v,{symbol:(raw>0?Jo[d]:void 0)??Jo[a]??s,decimals:Math.max(2,Math.min(10,Math.floor(Number(t?.decimals)||2)))})}';
const DUAL_JE = 'function je(e,t,o){const a=typeof o=="string"?o.toUpperCase():"",d=typeof t?.currency=="string"?t.currency.toUpperCase():"",fx=t?.fxRates??{};const v0=Number(e)||0;let raw=0;if(a){raw=a==="USD"?1:a==="CNY"?Number(fx.CNY):a==="EUR"?Number(fx.EUR):0}const dec=Math.max(2,Math.min(10,Math.floor(Number(t?.decimals)||2)));if(d==="DUAL"){const usd=raw>0?v0/raw:v0,rr=Number(t?.exchangeRate),rub=usd*(Number.isFinite(rr)&&rr>0?rr:1);return me(rub,{symbol:"₽",decimals:Math.max(2,Math.min(4,dec))})+" / "+me(usd,{symbol:"$",decimals:4})}let v=v0;if(a&&d&&a!==d&&raw>0){const dr=Number(t?.exchangeRate);if(dr>0)v=v0/raw*dr}const s=typeof t?.symbol=="string"&&t.symbol.length>0?t.symbol:"$";return me(v,{symbol:(raw>0?Jo[d]:void 0)??Jo[a]??s,decimals:dec})}';

function patchBalanceConvert(src) {
  if (src.includes('me(rub,{symbol:"₽",decimals:Math.max(2,Math.min(4,dec))})')) return src;
  const oldReturn = 'return me(rub,{symbol:"₽",decimals:dec})+" / "+me(usd,{symbol:"$",decimals:Math.max(4,dec)})';
  const newReturn = 'return me(rub,{symbol:"₽",decimals:Math.max(2,Math.min(4,dec))})+" / "+me(usd,{symbol:"$",decimals:4})';
  if (src.includes('if(d==="DUAL"){const usd=')) return replaceOnce(src, oldReturn, newReturn, 'balance dual precision');
  if (src.includes(CURRENT_JE)) return replaceOnce(src, CURRENT_JE, DUAL_JE, 'balance dual formatter');
  return replaceOnce(src, OLD_JE, DUAL_JE, 'balance dual formatter');
}

function patchCustomBalanceSymbol(src) {
  if (src.includes('s==="RUB"?"₽"')) return src;
  return replaceOnce(
    src,
    '(i?"":s==="CNY"?"¥":s==="EUR"?"€":"$")',
    '(i?"":s==="CNY"?"¥":s==="EUR"?"€":s==="RUB"?"₽":s==="DUAL"?"₽":"$")',
    'custom balance symbol'
  );
}

function patchEnums(src) {
  src = src.split('["USD","CNY","EUR"]').join('["USD","RUB","CNY","EUR","DUAL"]');
  src = src.split('["USD","RUB","CNY","EUR"]').join('["USD","RUB","CNY","EUR","DUAL"]');
  src = src.split("['USD', 'CNY', 'EUR']").join("['USD', 'RUB', 'CNY', 'EUR', 'DUAL']");
  src = src.split("['USD', 'RUB', 'CNY', 'EUR']").join("['USD', 'RUB', 'CNY', 'EUR', 'DUAL']");
  return src;
}

function assertNoOldEnums(src, file) {
  if (src.includes('["USD","CNY","EUR"]') || src.includes("['USD', 'CNY', 'EUR']") ||
      src.includes('["USD","RUB","CNY","EUR"]') || src.includes("['USD', 'RUB', 'CNY', 'EUR']")) {
    fail(file + ': an unpatched currency enum is still present');
  }
}

function assertDualEnums(src, file, quote) {
  const marker = quote === '"' ? '["USD","RUB","CNY","EUR","DUAL"]' : "['USD', 'RUB', 'CNY', 'EUR', 'DUAL']";
  if (!src.includes(marker)) fail(file + ': missing ' + marker);
}

function patchDisplay(src) {
  if (!src.includes('["DUAL","RUB + USD (₽ / $)"]')) {
    const plain = '[["CNY",v("currencyCny")],["USD",v("currencyUsd")],["EUR",v("currencyEur")]]';
    const withRub = '[["CNY",v("currencyCny")],["USD",v("currencyUsd")],["EUR",v("currencyEur")],["RUB","RUB (₽)"]]';
    const dual = '["RUB","RUB (₽)"],["DUAL","RUB + USD (₽ / $)"]';
    if (src.includes(withRub)) {
      src = replaceOnce(src, withRub, withRub.slice(0, -1) + ',' + dual + ']', 'currency select options');
    } else {
      src = replaceOnce(src, plain, plain.slice(0, -1) + ',' + dual + ']', 'currency select options');
    }
  }
  if (!src.includes('i==="DUAL"?"RUB":i')) {
    src = replaceOnce(
      src,
      'e.fxRates?.[i]??K[i].exchangeRate',
      'e.fxRates?.[i==="DUAL"?"RUB":i]??K[i].exchangeRate',
      'currency select rate'
    );
  }
  return src;
}

function patchFxRates(src) {
  if (!src.includes('RUB: 82.66')) {
    src = replaceOnce(
      src,
      'const rates = { USD: 1, CNY: 7.2, EUR: 0.92 }',
      'const rates = { USD: 1, CNY: 7.2, EUR: 0.92, RUB: ' + RATE + ' }',
      'FX rate defaults'
    );
  }
  src = src.replace("for (const key of ['CNY', 'EUR']) if (positive(config.fxRates?.[key])) rates[key] = config.fxRates[key]",
    "for (const key of ['CNY', 'EUR', 'RUB']) if (positive(config.fxRates?.[key])) rates[key] = config.fxRates[key]");
  src = src.replace("if (['CNY', 'EUR'].includes(config.currency) && positive(config.exchangeRate)) rates[config.currency] = config.exchangeRate",
    "if (['CNY', 'EUR', 'RUB'].includes(config.currency) && positive(config.exchangeRate)) rates[config.currency] = config.exchangeRate");
  return src;
}

const NEW_REFRESH = `/** Daily reference rates with RUB support via currency-api (jsDelivr). No account or inference request. */
import { readJsonBounded } from './net.js'
export const EXCHANGE_RATE_URL = 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json'
export function parseExchangeRates(payload, now = Date.now()) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw Error('Invalid exchange rates')
  const date = payload.date
  const at = Date.parse(date + 'T00:00:00Z')
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(date) || !Number.isFinite(at) || at > now + 86400000 || at < now - 14 * 86400000) throw Error('Invalid exchange rate date')
  const usd = payload.usd
  if (!usd || typeof usd !== 'object') throw Error('Invalid exchange rates')
  const result = { USD: 1 }
  for (const [code, key] of [['CNY', 'cny'], ['EUR', 'eur'], ['RUB', 'rub']]) {
    const rate = Number(usd[key])
    if (!Number.isFinite(rate) || rate <= 0 || rate > 1e6) throw Error('Invalid exchange rate quote')
    result[code] = rate
  }
  return { rates: result, date }
}
export function createExchangeRateRefresh(ledger, { request = fetch, now = Date.now } = {}) {
  let pending = null, controller = null, disposed = false, lastAttempt = 0
  return {
    refresh() {
      const current = now(), config = ledger.config
      if (disposed || ledger.closed || config.exchangeRateAuto === false || new Date(config.exchangeRateCheckedAt || 0).toISOString().slice(0, 10) === new Date(current).toISOString().slice(0, 10)) return Promise.resolve(false)
      if (pending) return pending
      if (lastAttempt && current - lastAttempt < 3600000) return Promise.resolve(false)
      lastAttempt = current; controller = new AbortController()
      const timeout = setTimeout(() => controller?.abort(), 10000); timeout.unref?.()
      pending = (async () => {
        const response = await request(EXCHANGE_RATE_URL, { signal: controller.signal, credentials: 'omit', redirect: 'error' })
        if (!response.ok) throw Error('Exchange rate service unavailable')
        const { rates, date } = parseExchangeRates(await readJsonBounded(response, 16384, { signal: controller.signal, timeoutMs: 10000 }), current)
        if (disposed || ledger.closed || ledger.config.exchangeRateAuto === false) return false
        const code = ledger.config.currency === 'DUAL' ? 'RUB' : ledger.config.currency
        ledger.config = { ...ledger.config, fxRates: rates, exchangeRate: rates[code] ?? ledger.config.exchangeRate,
          exchangeRateDate: date, exchangeRateCheckedAt: current }
        ledger.scheduleWrite()
        return true
      })().finally(() => { clearTimeout(timeout); pending = null; controller = null })
      return pending
    },
    dispose() { disposed = true; controller?.abort() },
  }
}
`;

const NEW_PARSE = `export function parseExchangeRates(payload, now = Date.now()) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw Error('Invalid exchange rates')
  const date = payload.date
  const at = Date.parse(date + 'T00:00:00Z')
  if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(date) || !Number.isFinite(at) || at > now + 86400000 || at < now - 14 * 86400000) throw Error('Invalid exchange rate date')
  const usd = payload.usd
  if (!usd || typeof usd !== 'object') throw Error('Invalid exchange rates')
  const result = { USD: 1 }
  for (const [code, key] of [['CNY', 'cny'], ['EUR', 'eur'], ['RUB', 'rub']]) {
    const rate = Number(usd[key])
    if (!Number.isFinite(rate) || rate <= 0 || rate > 1e6) throw Error('Invalid exchange rate quote')
    result[code] = rate
  }
  return { rates: result, date }
}
`;

function patchRefresh(src) {
  const currencyApi = 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json';
  const oldUrl = 'https://api.frankfurter.dev/v2/providers/ecb/rates?base=USD&quotes=CNY,EUR';
  if (!src.includes(currencyApi)) {
    src = replaceOnce(src, oldUrl, currencyApi, 'exchange-rate URL');
    const parseRe = /export function parseExchangeRates\([^\n]*\) \{[\s\S]*?\n\}\n/;
    const count = (src.match(/export function parseExchangeRates\(/g) || []).length;
    if (count !== 1) fail('exchange-rate parser: expected exactly 1 function, found ' + count);
    const match = parseRe.exec(src);
    if (!match) fail('exchange-rate parser: function body anchor not found');
    src = replaceOnce(src, match[0], NEW_PARSE, 'exchange-rate parser');
  }
  const dateSkip = " || new Date(config.exchangeRateCheckedAt || 0).toISOString().slice(0, 10) === new Date(current).toISOString().slice(0, 10)";
  if (src.includes(dateSkip)) src = src.replace(dateSkip, '');
  src = src.replace('/** Public daily ECB reference rates via Frankfurter. No account or inference request. */',
    '/** Public daily reference rates with RUB support via currency-api (jsDelivr). No account or inference request. */');
  const oldRate = 'exchangeRate: rates[ledger.config.currency] ?? ledger.config.exchangeRate';
  const newRate = "exchangeRate: rates[ledger.config.currency === 'DUAL' ? 'RUB' : ledger.config.currency] ?? ledger.config.exchangeRate";
  if (src.includes(oldRate)) src = replaceOnce(src, oldRate, newRate, 'refresh DUAL rate');
  return src;
}

const CLIENT_FX_MARK = 'CM_RUB_FX_REFRESH';
const CLIENT_FX = `const CM_RUB_FX_REFRESH=async()=>{try{const S=l.getSnapshot().state,C=S?.config;if(!C||C.exchangeRateAuto===false||!["DUAL","RUB"].includes(String(C.currency||"").toUpperCase()))return;const last=Number(C.exchangeRateCheckedAt)||0;if(last&&Date.now()-last<36e5)return;const ac=new AbortController(),tm=setTimeout(()=>ac.abort(),1e4);let res;try{res=await fetch("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",{signal:ac.signal,cache:"no-store"})}finally{clearTimeout(tm)}if(!res.ok)return;const d=await res.json(),rub=Number(d?.usd?.rub);if(!Number.isFinite(rub)||rub<=0)return;await j.updateConfig({exchangeRate:rub,fxRates:{...(C.fxRates||{}),RUB:rub},exchangeRateDate:typeof d.date==="string"?d.date:"",exchangeRateCheckedAt:Date.now()})}catch{}};setTimeout(CM_RUB_FX_REFRESH,3000);setInterval(CM_RUB_FX_REFRESH,6e4);`;

function patchClientAutoRefresh(src) {
  const existing = /const CM_RUB_FX_REFRESH=async\(\)=>\{[\s\S]*?setInterval\(CM_RUB_FX_REFRESH,6e4\);/;
  if (existing.test(src)) return src.replace(existing, () => CLIENT_FX);
  return replaceOnce(src, 'A();const R=e.get("slots")', 'A();' + CLIENT_FX + 'const R=e.get("slots")', 'client auto FX refresh');
}

function patchIndex(src) {
  if (src.includes("patch.currency === 'DUAL'")) return src;
  const n = src.split('fxRatesOf(ledger.config)[patch.currency] ?? patch.exchangeRate').length - 1;
  if (n !== 2) fail('applyConfigPatch: expected 2 anchors, found ' + n);
  return src.split('fxRatesOf(ledger.config)[patch.currency] ?? patch.exchangeRate')
    .join("fxRatesOf(ledger.config)[patch.currency === 'DUAL' ? 'RUB' : patch.currency] ?? patch.exchangeRate");
}

const OLD_FM_RE = /export function formatMoney\(usdCost, display\) \{[\s\S]*?\n\}\n/;
const NEW_FM = `export function formatMoney(usdCost, display) {
  const rate0 = Number(display?.exchangeRate)
  const rate = Number.isFinite(rate0) && rate0 > 0 ? rate0 : 1
  const req = Number(display?.decimals)
  const decimals = Math.max(0, Math.min(10, Number.isFinite(req) ? Math.floor(req) : 2))
  const money = (value, symbol, digits) => {
    let effective = digits
    if (value > 0 && value < 10 ** -digits) effective = digits + 2
    const fixed = value.toFixed(effective)
    const trimmed = fixed.includes('.') ? fixed.replace(/0+$/, '').replace(/\\.$/, '') : fixed
    return symbol + trimmed
  }
  if (String(display?.currency).toUpperCase() === 'DUAL') {
    return money(usdCost * rate, '₽', Math.max(2, Math.min(4, decimals))) + ' / ' + money(usdCost, '$', 4)
  }
  const symbol = typeof display?.symbol === 'string' && display.symbol.length > 0 ? display.symbol : '$'
  return money(usdCost * rate, symbol, decimals)
}
`;

function patchPricing(src) {
  if (src.includes('Math.max(2, Math.min(4, decimals))')) return src;
  const oldReturn = "return money(usdCost * rate, '₽', decimals) + ' / ' + money(usdCost, '$', Math.max(4, decimals))";
  const newReturn = "return money(usdCost * rate, '₽', Math.max(2, Math.min(4, decimals))) + ' / ' + money(usdCost, '$', 4)";
  if (src.includes("String(display?.currency).toUpperCase() === 'DUAL'")) return replaceOnce(src, oldReturn, newReturn, 'formatMoney dual precision');
  if (!OLD_FM_RE.test(src)) fail('formatMoney: anchor not found');
  return src.replace(OLD_FM_RE, () => NEW_FM);
}

if (RESTORE) {
  let n = 0;
  for (const f of fs.readdirSync(LIB)) {
    if (!f.endsWith('.rub-bak')) continue;
    const bak = path.join(LIB, f);
    const target = bak.slice(0, -'.rub-bak'.length);
    fs.copyFileSync(bak, target);
    console.log('restored ' + target);
    n++;
  }
  try { fs.rmSync(STATE_FILE, { force: true }); } catch {}
  console.log(n ? 'Restored ' + n + ' file(s).' : 'No .rub-bak backups found.');
  process.exit(0);
}

let client = fs.readFileSync(path.join(LIB, 'client.js'), 'utf8');
const clientBefore = client;
client = patchPreset(client);
client = patchJo(client);
client = patchFormatCost(client);
client = patchBalanceConvert(client);
client = patchCustomBalanceSymbol(client);
client = patchEnums(client);
client = patchClientAutoRefresh(client);
assertNoOldEnums(client, 'client.js');
assertDualEnums(client, 'client.js', '"');
report.push({ file: 'client.js', changed: client !== clientBefore, rub: (client.match(/RUB/g) || []).length, dual: (client.match(/DUAL/g) || []).length });

let display = fs.readFileSync(path.join(LIB, 'client.display.js'), 'utf8');
const displayBefore = display;
display = patchDisplay(display);
report.push({ file: 'client.display.js', changed: display !== displayBefore, rub: (display.match(/RUB/g) || []).length, dual: (display.match(/DUAL/g) || []).length });

let stats = fs.readFileSync(path.join(LIB, 'client.statistics.js'), 'utf8');
const statsBefore = stats;
stats = patchEnums(stats);
assertNoOldEnums(stats, 'client.statistics.js');
assertDualEnums(stats, 'client.statistics.js', '"');
report.push({ file: 'client.statistics.js', changed: stats !== statsBefore, rub: (stats.match(/RUB/g) || []).length, dual: (stats.match(/DUAL/g) || []).length });

let typert = fs.readFileSync(path.join(LIB, 'typert.host.js'), 'utf8');
const typertBefore = typert;
typert = patchEnums(typert);
assertNoOldEnums(typert, 'typert.host.js');
assertDualEnums(typert, 'typert.host.js', "'");
report.push({ file: 'typert.host.js', changed: typert !== typertBefore, rub: (typert.match(/RUB/g) || []).length, dual: (typert.match(/DUAL/g) || []).length });

let billing = fs.readFileSync(path.join(LIB, 'billing-export.js'), 'utf8');
const billingBefore = billing;
billing = patchEnums(billing);
assertNoOldEnums(billing, 'billing-export.js');
assertDualEnums(billing, 'billing-export.js', "'");
report.push({ file: 'billing-export.js', changed: billing !== billingBefore, rub: (billing.match(/RUB/g) || []).length, dual: (billing.match(/DUAL/g) || []).length });

let index = fs.readFileSync(path.join(LIB, 'index.js'), 'utf8');
const indexBefore = index;
index = patchIndex(index);
report.push({ file: 'index.js', changed: index !== indexBefore });

let fx = fs.readFileSync(path.join(LIB, 'exchange-rates.js'), 'utf8');
const fxBefore = fx;
fx = patchFxRates(fx);
report.push({ file: 'exchange-rates.js', changed: fx !== fxBefore, rub: (fx.match(/RUB/g) || []).length });

let refresh = fs.readFileSync(path.join(LIB, 'exchange-rate-refresh.js'), 'utf8');
const refreshBefore = refresh;
refresh = patchRefresh(refresh);
report.push({ file: 'exchange-rate-refresh.js', changed: refresh !== refreshBefore, rub: (refresh.match(/RUB/g) || []).length });

let pricing = fs.readFileSync(path.join(LIB, 'pricing.js'), 'utf8');
const pricingBefore = pricing;
pricing = patchPricing(pricing);
report.push({ file: 'pricing.js', changed: pricing !== pricingBefore, dual: (pricing.match(/DUAL/g) || []).length });

const out = {
  'client.js': client,
  'client.display.js': display,
  'client.statistics.js': stats,
  'typert.host.js': typert,
  'billing-export.js': billing,
  'index.js': index,
  'exchange-rates.js': fx,
  'exchange-rate-refresh.js': refresh,
  'pricing.js': pricing,
};

// Syntax-check every changed bundle in a temp dir before touching the plugin.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cm-rub-'));
try {
  for (const [name, src] of Object.entries(out)) {
    const p = path.join(tmp, name.replace(/\.js$/, '.mjs'));
    fs.writeFileSync(p, src);
    try {
      execFileSync(process.execPath, ['--check', p], { stdio: 'pipe' });
    } catch (e) {
      const stderr = e.stderr ? e.stderr.toString().slice(0, 2000) : String(e);
      fail('syntax check failed for ' + name + ':\n' + stderr);
    }
  }
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}

function sha256(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

function readState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch { return {}; }
}

function atomicWrite(file, text) {
  const tmp = file + '.tmp-' + process.pid;
  fs.writeFileSync(tmp, text, 'utf8');
  fs.renameSync(tmp, file);
}

function makeVersionBackup() {
  fs.mkdirSync(BACKUP_DIR, { recursive: true });
  const archive = path.join(BACKUP_DIR, 'dsh-cost-meter-' + VERSION + '.tgz');
  if (!fs.existsSync(archive)) {
    execFileSync('/usr/bin/tar', [
      '-czf', archive,
      '--exclude=*.rub-bak',
      '-C', path.dirname(PLUGIN_DIR),
      path.basename(PLUGIN_DIR),
    ], { stdio: 'pipe' });
  }
  const keep = fs.readdirSync(BACKUP_DIR)
    .filter((f) => /^dsh-cost-meter-.*\.tgz$/.test(f))
    .map((f) => ({ f, t: fs.statSync(path.join(BACKUP_DIR, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t);
  for (const old of keep.slice(3)) fs.rmSync(path.join(BACKUP_DIR, old.f), { force: true });
  return archive;
}

if (CHECK) {
  console.log(JSON.stringify({ ok: true, checkOnly: true, pluginDir: PLUGIN_DIR, version: VERSION, rate: RATE, files: report }, null, 2));
  console.log('Dry run: no files written.');
  process.exit(0);
}

const changed = [];
for (const [name, src] of Object.entries(out)) {
  if (fs.readFileSync(path.join(LIB, name), 'utf8') !== src) changed.push(name);
}

const state = readState();
const compact = (applied) => JSON.stringify({
  ok: true,
  applied,
  version: VERSION,
  pluginDir: PLUGIN_DIR,
  rate: state.rate ?? RATE,
  changed,
});

if (changed.length === 0) {
  // Ничего не пишем, но фиксируем версию и хэши: следующий запуск отличит
  // уже пропатченный файл от свежего после обновления плагина.
  const files = {};
  for (const [name, src] of Object.entries(out)) files[name] = sha256(src);
  atomicWrite(STATE_FILE, JSON.stringify({ version: VERSION, rate: state.rate ?? RATE, patchedAt: new Date().toISOString(), files }, null, 2) + '\n');
  if (IF_NEEDED) {
    console.log(compact(false));
  } else {
    console.log(JSON.stringify({ ok: true, pluginDir: PLUGIN_DIR, version: VERSION, alreadyPatched: true, changed: [] }, null, 2));
  }
  process.exit(0);
}

if (state.version !== VERSION) {
  const archive = makeVersionBackup();
  if (!IF_NEEDED) console.log('Snapshot before patch: ' + archive);
}

const nextFiles = { ...(state.files || {}) };
for (const name of changed) {
  const p = path.join(LIB, name);
  const bak = p + '.rub-bak';
  const current = fs.readFileSync(p, 'utf8');
  const known = state.files?.[name];
  if (known !== undefined && sha256(current) !== known) {
    // Файл заменили извне (обновление плагина) — обновляем точку отката.
    fs.copyFileSync(p, bak);
  } else if (known === undefined && !fs.existsSync(bak)) {
    fs.copyFileSync(p, bak);
  }
  atomicWrite(p, out[name]);
  nextFiles[name] = sha256(out[name]);
}
for (const [name, src] of Object.entries(out)) nextFiles[name] = sha256(src);

atomicWrite(STATE_FILE, JSON.stringify({
  version: VERSION,
  rate: RATE_EXPLICIT ? RATE : (state.rate ?? RATE),
  patchedAt: new Date().toISOString(),
  files: nextFiles,
}, null, 2) + '\n');

if (IF_NEEDED) {
  console.log(compact(true));
} else {
  console.log(JSON.stringify({ ok: true, pluginDir: PLUGIN_DIR, version: VERSION, rate: RATE, files: report }, null, 2));
  console.log('Done. Reload DSH (Cmd+R), then Settings -> Cost -> Display -> Currency -> RUB + USD (₽ / $).');
}
