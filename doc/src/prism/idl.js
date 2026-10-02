// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear
//
// Prism language definition for IDL (ISA Description Language).
//
// THIS IS THE CANONICAL SOURCE for IDL syntax highlighting.
// The TextMate grammar at tools/vscode/idl/syntaxes/idl.tmLanguage.json
// is generated from this file. To regenerate it, run:
//
//   mise run gen:idl-grammar
//

module.exports = function (Prism) {
  Prism.languages.idl = {
    // Comments: # to end of line
    comment: {
      pattern: /#.*/,
      greedy: true,
    },

    // description { ... } block — content is treated as a string
    description: {
      pattern: /\bdescription\s*\{[^}]*\}/,
      greedy: true,
      inside: {
        keyword: /\bdescription\b/,
        punctuation: /[{}]/,
      },
    },

    // Double-quoted strings
    string: {
      pattern: /"[^"]*"/,
      greedy: true,
    },

    // Verilog-style sized literals: 32'hDEAD, 8'd255, 1'b1, 4'o7
    "verilog-literal": {
      pattern: /\b(?:\d+|MXLEN)'s?[bBoOdDhH][0-9a-fA-F_]+\b/,
      alias: "number",
    },

    // C-style hex literals: 0xDEAD
    "hex-literal": {
      pattern: /\b0x[0-9a-fA-F_]+\b/,
      alias: "number",
    },

    // Binary literals: 0b1010
    "binary-literal": {
      pattern: /\b0b[01_]+\b/,
      alias: "number",
    },

    // Decimal integers
    number: /\b\d+\b/,

    // Keywords
    keyword:
      /\b(?:if|else|for|returns|return|arguments|description|body|builtin|function|enum|bitfield|struct)\b/,

    // Builtin variables and cast operators ($ prefix)
    builtin:
      /\$(?:pc|encoding|signed|bits|enum_to_a|enum|array_size|enum_size|enum_element_size)\b/,

    // Boolean literals
    boolean: /\b(?:true|false)\b/,

    // Type aliases
    "type-alias": {
      pattern: /\b(?:Bits|XReg|U64|U32|Boolean|String)\b/,
      alias: "class-name",
    },

    // CSR access: CSR[name] or CSR[name].field
    csr: {
      pattern: /\bCSR\b/,
      alias: "keyword",
    },

    // Enum/bitfield scope operator: Type::Member
    "scope-resolution": {
      pattern: /\b([A-Z][a-zA-Z0-9_]*)(::[A-Za-z][A-Za-z0-9_]*)\b/,
      inside: {
        "class-name": /^[A-Z][a-zA-Z0-9_]*/,
        punctuation: /::/,
        property: /[A-Za-z][A-Za-z0-9_]*$/,
      },
    },

    // Function declarations: function name
    "function-declaration": {
      pattern: /(\bfunction\s+)[a-z][a-zA-Z0-9_]*\??/,
      lookbehind: true,
      alias: "function",
    },

    // Function calls: name( or name<...>(
    "function-call": {
      pattern: /\b([a-z][a-zA-Z0-9_]*\??)\s*(?:<[^>]*>\s*)?\(/,
      inside: {
        function: /^[a-z][a-zA-Z0-9_]*\??/,
        punctuation: /[<>(),]/,
      },
    },

    // Constants and type names (uppercase-first identifiers)
    constant: /\b[A-Z][a-zA-Z0-9_]*\b/,

    // Widening operators (backtick prefix)
    "widening-operator": {
      pattern: /`[+\-*]|`<</,
      alias: "operator",
    },

    // Operators
    operator: /->|[+\-*/%&|^~]|<<=?|>>=?|<=?|>=?|[!=]=|&&|\|\||[!~]/,

    // Punctuation
    punctuation: /[{}[\]();,.:]/,
  };
};
