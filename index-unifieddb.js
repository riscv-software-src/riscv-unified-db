#!/usr/bin/env node
'use strict';

const process = require('process');
const path = require('path');
const fs = require('fs');

const { readdir } = fs.promises;

const tree = {
  arch: {
    inst: { // TODO update this object to index new extension
      A: {},
      B: {},
      F: {},
      H: {},
      I: {},
      M: {},
      Q: {},
      S: {},
      Svinval: {},
      V: {},
      Zabha: {},
      Zacas: {},
      Zalasr: {},
      Zawrs: {},
      Zfbfmin: {},
      Zfh: {},
      Zicbom: {},
      Zicboz: {},
      Zicfiss: {},
      Zicond: {},
      Zicsr: {},
      Zifencei: {}
    }
  }
};

const rec = async (node, branch, root) => {
  const keys = Object.keys(node);
  if (keys.length === 0) {
    const fullPath = path.resolve(root, ...branch);
    const files = await readdir(fullPath);
    for (const file of files) {
      const baseName = path.basename(file, '.yaml');
      node[baseName] = {$ref: path.join(...branch, file)};
    }
  } else {
    for (const key of keys) {
      const newBranch = [...branch, key];
      await rec(node[key], newBranch, root);
    }
  }
  return node;
};

const main = async () => {
  const [, , root] = process.argv;
  if (root === undefined) {
    console.error('usage: ./index-unifieddb.js <path-to-unifieddb-root>');
    return;
  }
  const rootPath = path.resolve('.', root);
  await rec(tree, [], rootPath);
  console.log(JSON.stringify(tree, null, 2));
};

main();
