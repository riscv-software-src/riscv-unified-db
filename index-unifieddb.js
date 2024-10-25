#!/usr/bin/env node
'use strict';

const process = require('process');
const path = require('path');
const fs = require('fs');

const { readdir, stat } = fs.promises;

const rec = async (branch, root) => {
  const node = {};
  const localPath = path.resolve(root, ...branch);
  const els = await readdir(localPath);
  for (const el of els) {
    const isFile = (await stat(path.resolve(localPath, el))).isFile();
    const fileExt = path.extname(el);
    const baseName = path.basename(el, fileExt);
    console.log(localPath, el, baseName, fileExt, isFile);
    if (isFile) {
      if (['.yaml', '.json'].includes(fileExt)) {
        node[baseName] = {$ref: path.join(...branch, el)};
      }
    } else {
      node[el] = await rec([...branch, el], root);
    }
  }
  return node;
};

const main = async () => {
  const [, , root] = process.argv;
  if (root === undefined) {
    console.error('usage: ./index-unifieddb.js <path-to-unifieddb-arch-folder>');
    return;
  }
  const rootPath = path.resolve('.', root);
  const tree = await rec([], rootPath);
  console.log(JSON.stringify(tree, null, 2));
};

main();
