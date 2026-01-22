import * as path from 'path';
import Mocha = require('mocha');
import glob = require('glob');

export function run(): Promise<void> {
  const mocha = new Mocha({ ui: 'tdd', timeout: 20000 });
  const testsRoot = path.resolve(__dirname);

  const files: string[] = glob.sync('**/*.test.js', { cwd: testsRoot });
  for (const f of files) {
    mocha.addFile(path.resolve(testsRoot, f));
  }

  return new Promise<void>((resolve, reject) => {
    try {
      mocha.run((failures: number) => failures ? reject(new Error(`${failures} tests failed`)) : resolve());
    } catch (e) {
      reject(e as Error);
    }
  });
}
