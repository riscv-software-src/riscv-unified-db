import * as cp from 'child_process';
import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, StreamInfo } from 'vscode-languageclient/node';

let client: LanguageClient;

/**
 * Check if Java is installed and available
 * Returns the java command path if found, null otherwise
 */
async function checkJavaInstalled(): Promise<string | null> {
  return new Promise((resolve) => {
    const configuredJava = vscode.workspace.getConfiguration('udb').get<string>('javaPath');
    const javaCommand = configuredJava || 'java';

    cp.exec(`"${javaCommand}" -version`, (error, stdout, stderr) => {
      if (error) {
        // Java not found
        const message = configuredJava
          ? `Java not found at configured path: ${configuredJava}`
          : 'Java 21+ is required but not found on your system.';

        vscode.window.showErrorMessage(
          message + '\n\nInstall Java from:\n' +
          '• macOS: brew install openjdk@21\n' +
          '• Windows: https://adoptopenjdk.net/\n' +
          '• Linux: sudo apt install openjdk-21-jdk\n\n' +
          'Or configure udb.javaPath in VS Code settings if Java is installed elsewhere.'
        );
        resolve(null);
      } else {
        // Java found, verify it's version 21+
        const versionOutput = stdout + stderr;
        const versionMatch = versionOutput.match(/version "(\d+)/);

        if (versionMatch) {
          const majorVersion = parseInt(versionMatch[1]);
          if (majorVersion < 21) {
            vscode.window.showErrorMessage(
              `Java 21+ is required, but found Java ${majorVersion}. ` +
              `Please upgrade from https://adoptopenjdk.net/`
            );
            resolve(null);
          } else {
            resolve(javaCommand);
          }
        } else {
          // Couldn't parse version, but java command exists - try anyway
          resolve(javaCommand);
        }
      }
    });
  });
}

function getLanguageServerPath(ctx: vscode.ExtensionContext): string {
  return ctx.asAbsolutePath('server/udb-ls-all.jar');
}

export async function activate(ctx: vscode.ExtensionContext) {
  // Check Java before starting language server
  const javaPath = await checkJavaInstalled();
  if (!javaPath) {
    return; // Don't activate if Java not available
  }

  const chan = vscode.window.createOutputChannel('UDB Language Server');
  const jar = getLanguageServerPath(ctx);

  const serverOptions = async () => {
    chan.appendLine(`Launching: ${javaPath} -jar ${jar} -stdio`);
    const proc = cp.spawn(javaPath, ['-jar', jar, '-stdio'], { cwd: ctx.extensionPath });

    proc.on('error', (e) => chan.appendLine(`spawn error: ${String(e)}`));
    proc.on('exit',  (code, sig) => chan.appendLine(`server exit code=${code} signal=${sig}`));
    proc.stderr.on('data', d => chan.appendLine(String(d)));

    return { reader: proc.stdout!, writer: proc.stdin! } as StreamInfo;
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ language: 'udb', scheme: 'file' }],
  };

  client = new LanguageClient('udb', 'UDB Language Server', serverOptions, clientOptions);
  await client.start();
}

export async function deactivate() {
  if (client) await client.stop();
}
