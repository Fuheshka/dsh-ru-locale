#!/usr/bin/env python3
"""Assemble the translated corpus into the client half of the language pack.

Reads corpus.jsonl (authoritative ns/key order) and out/group-*.jsonl (final
Russian text), then writes pkg/client.js with the dictionary embedded.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.jsonl")
OUT = os.path.join(HERE, "out")
# Third-party plugin strings: the corpus/out pair for bundles installed into the
# profile, kept apart so the upstream corpus stays a byte-stable snapshot.
VENDOR_CORPUS = os.path.join(HERE, "vendor", "vendor-corpus.jsonl")
VENDOR_OUT = os.path.join(HERE, "out-vendor")
CLIENT = os.path.normpath(os.path.join(HERE, "..", "pkg", "client.js"))
LOCALE_ID = "ru-x-dsh"
LABEL = "Русский (улучшенный)"


def load(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    corpus = list(load(CORPUS))
    vendor = list(load(VENDOR_CORPUS)) if os.path.exists(VENDOR_CORPUS) else []
    translated = {}
    for directory in (OUT, VENDOR_OUT):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".jsonl"):
                continue
            for row in load(os.path.join(directory, name)):
                translated[(row["ns"], row["key"])] = row["ru"]

    overrides_path = os.path.join(HERE, "overrides.jsonl")
    if os.path.exists(overrides_path):
        for row in load(overrides_path):
            translated[(row["ns"], row["key"])] = row["ru"]

    all_rows = corpus + vendor
    missing = [r for r in all_rows if (r["ns"], r["key"]) not in translated]
    if missing:
        print(f"missing {len(missing)} keys, e.g. {[(m['ns'], m['key']) for m in missing[:5]]}")
        return 1

    tree = {}
    order = []
    for row in all_rows:
        ns = row["ns"]
        if ns not in tree:
            tree[ns] = {}
            order.append(ns)
        tree[ns][row["key"]] = translated[(row["ns"], row["key"])]

    payload = {ns: tree[ns] for ns in order}
    body = json.dumps(payload, ensure_ascii=False, indent=0, separators=(",", ":"))
    body = body.replace("\n", "")

    js = f"""/**
 * Reviewed Russian UI language pack: registers the `{LOCALE_ID}` language with
 * `ru` as its fallback, so every string this pack does not override still comes
 * from the shipped Russian dictionary, and anything missing there falls to English.
 *
 * Generated from the translation corpus; edit the corpus, not this file.
 */
window.__ModuleLoader__.load({{
  id: '@local/dsh-locale-ru',
  factory() {{
    const LOCALE_ID = '{LOCALE_ID}';
    const DICT = {body};
    return {{
      inject: ['locale'],
      apply(ctx) {{
        ctx.effect(
          () => ctx.locale.addLanguage({{ id: LOCALE_ID, label: '{LABEL}', fallback: 'ru' }}),
          'ru-locale: language definition',
        );
        for (const [ns, dict] of Object.entries(DICT)) {{
          ctx.effect(
            () => ctx.locale.register(ns, LOCALE_ID, dict),
            `ru-locale: ${{ns}} dictionary`,
          );
        }}
        // Bridge for plugins that keep their own copy chain instead of reading the
        // registry (dsh-better-sidebar's `t()` only knows zh/en unless a
        // `betterLocale` service hands it another language). We publish that
        // service, so a plugin that registers its dictionaries with us gets its
        // Russian text served while our locale is active. Every method is a no-op
        // or `undefined` when we cannot answer, so an unbridged plugin keeps its
        // own behaviour instead of breaking.
        const vendorDicts = {{}};
        const vendorListeners = new Set();
        const vendorRuActive = () => {{
          try {{
            const active = ctx.locale.getSnapshot().active;
            return typeof active === 'string' && active.toLowerCase().startsWith('ru') ? active : undefined;
          }} catch (error) {{
            return undefined;
          }}
        }};
        const vendorNotify = () => {{
          for (const listener of [...vendorListeners]) {{
            try {{
              listener();
            }} catch (error) {{
              console.warn('[ru-locale] bridge listener failed:', error);
            }}
          }}
        }};
        const vendorStore = {{
          // The Sidebar re-renders on this value, so it must be a plain string and
          // stable between locale changes.
          get active() {{
            return vendorRuActive();
          }},
          subscribe(listener) {{
            if (typeof listener !== 'function') return () => {{}};
            vendorListeners.add(listener);
            return () => vendorListeners.delete(listener);
          }},
          register(ns, dicts) {{
            if (typeof ns !== 'string' || dicts === null || typeof dicts !== 'object') return () => {{}};
            vendorDicts[ns] = dicts;
            vendorNotify();
            return () => {{
              delete vendorDicts[ns];
              vendorNotify();
            }};
          }},
          // 'ru' is the only language this pack speaks; any other active locale
          // (zh/en/…) falls through to the plugin's own chain.
          getOverride(active, ns, key) {{
            if (typeof active !== 'string' || !active.toLowerCase().startsWith('ru')) return undefined;
            try {{
              const own = DICT[ns];
              if (own !== undefined && typeof own[key] === 'string') return own[key];
              const vendor = vendorDicts[ns];
              const ru = vendor && vendor.ru;
              if (ru !== null && typeof ru === 'object' && typeof ru[key] === 'string') return ru[key];
            }} catch (error) {{
              console.warn('[ru-locale] bridge lookup failed:', error);
            }}
            return undefined;
          }},
          isOverrideActive(active) {{
            return typeof active === 'string' && active.toLowerCase().startsWith('ru');
          }},
        }};
        try {{
          if (typeof ctx.provide === 'function') ctx.provide('betterLocale', vendorStore);
        }} catch (error) {{
          console.warn('[ru-locale] another plugin already provides betterLocale:', error);
        }}
        try {{
          ctx.effect(() => ctx.locale.subscribe(() => vendorNotify()), 'ru-locale: bridge repaint');
        }} catch (error) {{
          console.warn('[ru-locale] could not follow locale changes:', error);
        }}
        // One-time adoption: a reader already on the shipped Russian dictionary
        // gets the reviewed pack without hunting for a switch. The marker keeps
        // a deliberate choice of the shipped Russian from being overridden again.
        try {{
          const marker = 'dsh-ru-locale-pack:adopted';
          let adopted = false;
          try {{ adopted = globalThis.localStorage?.getItem(marker) === '1'; }} catch {{}}
          if (!adopted && ctx.locale.getSnapshot().active === 'ru') {{
            ctx.locale.setLocale(LOCALE_ID);
            try {{ globalThis.localStorage?.setItem(marker, '1'); }} catch {{}}
          }}
        }} catch (error) {{
          console.warn('[ru-locale] could not adopt the review pack:', error);
        }}
      }},
    }};
  }},
}});
"""
    with open(CLIENT, "w", encoding="utf-8") as fh:
        fh.write(js)
    size = os.path.getsize(CLIENT)
    print(f"wrote {CLIENT}: {len(order)} namespaces, {len(all_rows)} strings, {size // 1024} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
