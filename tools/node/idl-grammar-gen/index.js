#!/usr/bin/env node
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear
//
// Generates tools/vscode/idl/syntaxes/idl.tmLanguage.json from
// doc/src/prism/idl.js (the canonical IDL syntax definition).
//
// Usage:
//   node tools/node/idl-grammar-gen/index.js
//   mise run gen:idl-grammar

const path = require('path');
const fs   = require('fs');

const ROOT         = path.resolve(__dirname, '..', '..', '..');
const PRISM_SRC    = path.join(ROOT, 'doc', 'src', 'prism', 'idl.js');
const TMLANG_OUT   = path.join(ROOT, 'tools', 'vscode', 'idl', 'syntaxes', 'idl.tmLanguage.json');

// ---------------------------------------------------------------------------
// Load the Prism definition by executing the IIFE against a stub Prism object
// ---------------------------------------------------------------------------

// Load the Prism definition. The file exports a function(Prism) that registers
// the language when called.
const Prism = { languages: {} };
const registerIdl = require(PRISM_SRC);
registerIdl(Prism);
const lang = Prism.languages.idl;

// ---------------------------------------------------------------------------
// Scope mapping: Prism token name (or alias) -> TextMate scope
// ---------------------------------------------------------------------------

const SCOPE = {
  comment:              'comment.line.number-sign.idl',
  string:               'string.quoted.double.idl',
  number:               'constant.numeric.idl',
  'verilog-literal':    'constant.numeric.idl',
  'hex-literal':        'constant.numeric.idl',
  'binary-literal':     'constant.numeric.idl',
  keyword:              'keyword.control.idl',
  builtin:              'support.function.builtin.idl',
  boolean:              'constant.language.idl',
  'type-alias':         'storage.type.idl',
  'class-name':         'entity.name.type.idl',
  csr:                  'keyword.control.idl',
  constant:             'constant.language.idl',
  function:             'entity.name.function.idl',
  'function-declaration': 'entity.name.function.idl',
  operator:             'keyword.operator.idl',
  'widening-operator':  'keyword.operator.idl',
  punctuation:          'punctuation.idl',
  property:             'variable.other.member.idl',
};

function scopeFor(name, token) {
  const alias = token && token.alias;
  if (alias && SCOPE[alias]) return SCOPE[alias];
  return SCOPE[name] || `meta.${name}.idl`;
}

// ---------------------------------------------------------------------------
// Convert a single Prism token to one or more TextMate pattern objects
// ---------------------------------------------------------------------------

function regexSource(r) {
  if (r instanceof RegExp) return r.source;
  if (typeof r === 'string') return r.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&');
  return null;
}

function convertToken(name, token) {
  if (!token) return null;

  if (Array.isArray(token)) {
    return token.flatMap(t => convertToken(name, t)).filter(Boolean);
  }

  const scope = scopeFor(name, token);

  if (token instanceof RegExp) {
    return [{ name: scope, match: regexSource(token) }];
  }

  if (typeof token === 'object') {
    const pattern = token.pattern instanceof RegExp ? token.pattern : null;
    if (!pattern) return null;

    const src = regexSource(pattern);

    if (token.inside) {
      // description block: the one begin/end construct
      if (name === 'description') {
        return [{
          name: 'meta.description.idl',
          begin: '\\b(description)\\s*(\\{)',
          end: '\\}',
          beginCaptures: {
            '1': { name: 'keyword.control.idl' },
            '2': { name: 'punctuation.idl' },
          },
          endCaptures: {
            '0': { name: 'punctuation.idl' },
          },
          contentName: 'string.other.description.idl',
        }];
      }

      // scope-resolution: Type::Member
      if (name === 'scope-resolution') {
        return [{
          match: '\\b([A-Z][a-zA-Z0-9_]*)(::)([A-Za-z][A-Za-z0-9_]*)\\b',
          captures: {
            '1': { name: 'entity.name.type.idl' },
            '2': { name: 'punctuation.idl' },
            '3': { name: 'variable.other.member.idl' },
          },
        }];
      }

      // function-call: name( or name<...>(
      if (name === 'function-call') {
        return [{
          match: '\\b([a-z][a-zA-Z0-9_]*\\??)\\s*(?:<[^>]*>\\s*)?\\(',
          captures: {
            '1': { name: 'entity.name.function.idl' },
          },
        }];
      }

      return [{ name: scope, match: src }];
    }

    // lookbehind: first capture group is the lookbehind context, second is the real match
    if (token.lookbehind) {
      return [{
        match: src,
        captures: {
          '1': { name: 'keyword.control.idl' },
          '2': { name: scope },
        },
      }];
    }

    return [{ name: scope, match: src }];
  }

  return null;
}

// ---------------------------------------------------------------------------
// Build the TextMate grammar
// ---------------------------------------------------------------------------

const patterns = [];
const repository = {};

for (const [name, token] of Object.entries(lang)) {
  const converted = convertToken(name, token);
  if (!converted || converted.length === 0) continue;

  repository[name] = { patterns: converted };
  patterns.push({ include: `#${name}` });
}

const tmLanguage = {
  $schema: 'https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json',
  name: 'IDL',
  scopeName: 'source.idl',
  // AUTO-GENERATED — do not edit by hand.
  // Edit doc/src/prism/idl.js and run: mise run gen:idl-grammar
  patterns,
  repository,
};

// ---------------------------------------------------------------------------
// Write output
// ---------------------------------------------------------------------------

const generated = JSON.stringify(tmLanguage, null, 2) + '\n';
if (process.argv.includes('--check')) {
  const current = fs.existsSync(TMLANG_OUT) ? fs.readFileSync(TMLANG_OUT, 'utf8') : null;
  if (current !== generated) {
    console.log(path.relative(ROOT, TMLANG_OUT));
    process.exitCode = 1;
  }
} else {
  fs.mkdirSync(path.dirname(TMLANG_OUT), { recursive: true });
  fs.writeFileSync(TMLANG_OUT, generated);
  console.log(`Written: ${path.relative(ROOT, TMLANG_OUT)}`);
}
