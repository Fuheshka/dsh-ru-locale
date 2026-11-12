#!/usr/bin/env node
/**
 * Extract `ctx.locale.register(...)` dictionaries from an installed plugin's
 * client bundle by parsing it with the TypeScript compiler and evaluating the
 * object literals statically (string values only).
 *
 * Usage: node extract-plugin-locales.cjs <bundle.js> [more.js ...]
 */
const fs = require('fs');
const ts = require('/Users/fuheshka/Documents/GitHub/deepseek-harness/node_modules/typescript');

const args = process.argv.slice(2);
const out = {};

function literalValue(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isTemplateExpression(node)) {
    // keep ${...} holes as {placeholder}
    let text = node.head.text;
    for (const span of node.templateSpans) {
      text += '{' + span.expression.getText().replace(/[{}]/g, '') + '}' + span.literal.text;
    }
    return text;
  }
  if (ts.isParenthesizedExpression(node)) return literalValue(node.expression);
  if (ts.isAsExpression(node) || ts.isSatisfiesExpression?.(node)) return literalValue(node.expression);
  return undefined;
}

function objectEntries(sf, node, depth = 0) {
  if (!ts.isObjectLiteralExpression(node)) return undefined;
  const result = {};
  for (const prop of node.properties) {
    if (ts.isShorthandPropertyAssignment(prop)) {
      const value = resolveObject(sf, declaration(sf, prop.name.text), depth + 1);
      if (value) result[prop.name.text] = value;
      continue;
    }
    if (!ts.isPropertyAssignment(prop)) continue;
    const name = ts.isStringLiteral(prop.name) || ts.isIdentifier(prop.name) || ts.isNumericLiteral(prop.name)
      ? prop.name.text
      : undefined;
    if (name === undefined) continue;
    const value = resolveValue(sf, prop.initializer, depth + 1);
    if (value !== undefined) result[name] = value;
  }
  return result;
}

let POSITION = Infinity;

function declaration(sf, name) {
  const candidates = [];
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name && node.initializer) {
      candidates.push(node);
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  // prefer a declaration before the call that resolves to an object literal
  const before = candidates.filter(d => d.getStart(sf) <= POSITION);
  const pool = before.length ? before : candidates;
  for (let i = pool.length - 1; i >= 0; i -= 1) {
    if (ts.isObjectLiteralExpression(pool[i].initializer)) return pool[i].initializer;
  }
  return pool.length ? pool[pool.length - 1].initializer : undefined;
}

function resolveValue(sf, node, depth = 0) {
  if (depth > 4 || !node) return undefined;
  const direct = literalValue(node);
  if (direct !== undefined) return direct;
  if (ts.isIdentifier(node)) {
    return resolveValue(sf, declaration(sf, node.text), depth + 1);
  }
  return undefined;
}

function resolveObject(sf, node, depth = 0) {
  if (depth > 4 || !node) return undefined;
  if (ts.isObjectLiteralExpression(node)) return objectEntries(sf, node, depth);
  if (ts.isIdentifier(node)) return resolveObject(sf, declaration(sf, node.text), depth + 1);
  return undefined;
}

for (const file of args) {
  const source = fs.readFileSync(file, 'utf8');
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS);
  const calls = [];
  const visit = (node) => {
    if (ts.isCallExpression(node)) {
      const text = node.expression.getText(sf);
      if (/(^|\.)locale\.register$/.test(text)) calls.push(node);
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  for (const call of calls) {
    POSITION = call.getStart(sf);
    const [nsArg, ...rest] = call.arguments;
    if (!nsArg) continue;
    let ns = literalValue(nsArg);
    if (ns === undefined) ns = resolveValue(sf, nsArg);
    if (!ns) continue;
    // two shapes: register(ns, {zh, en}) and register(ns, 'zh', dict)
    if (rest.length >= 2) {
      const locale = resolveValue(sf, rest[0]);
      const dict = resolveObject(sf, rest[1]);
      if (locale && dict) {
        out[ns] = out[ns] || {};
        out[ns][locale] = dict;
      }
    } else if (rest.length === 1 && ts.isObjectLiteralExpression(rest[0])) {
      out[ns] = out[ns] || {};
      for (const prop of rest[0].properties) {
        if (!ts.isPropertyAssignment(prop)) continue;
        const locale = ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name) ? prop.name.text : undefined;
        if (!locale) continue;
        const dict = resolveObject(sf, prop.initializer);
        if (dict) out[ns][locale] = dict;
      }
    }
  }
}

process.stdout.write(JSON.stringify(out, null, 1));
