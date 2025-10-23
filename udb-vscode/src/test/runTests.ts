import * as path from 'path';
import { runTests } from '@vscode/test-electron';

async function main() {
  const extensionDevelopmentPath = path.resolve(__dirname, '../../');
  const extensionTestsPath = path.resolve(__dirname, './suite/index');
  const testWorkspace = path.resolve(__dirname, '../../test-fixtures');

  await runTests({
    extensionDevelopmentPath,
    extensionTestsPath,
    launchArgs: [
      testWorkspace,
      '--disable-extensions',
      '--new-window',
      path.join(extensionDevelopmentPath, 'test-fixtures') // workspace with .udb files
    ]
  });
}

main().catch(err => { console.error('Failed to run tests', err); process.exit(1); });
