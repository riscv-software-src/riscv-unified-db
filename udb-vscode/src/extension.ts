import * as cp from 'child_process';
import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, StreamInfo } from 'vscode-languageclient/node';

let client: LanguageClient;

export async function activate(ctx: vscode.ExtensionContext) {
  const chan = vscode.window.createOutputChannel('UDB Language Server');
  const java = vscode.workspace.getConfiguration('udb').get<string>('javaPath') || 'java';
  const jar = ctx.asAbsolutePath('server/udb-ls-all.jar');

  const serverOptions = async () => {
    chan.appendLine(`Launching: ${java} -jar ${jar} -stdio`);
    const proc = cp.spawn(java, ['-jar', jar, '-stdio'], { cwd: ctx.extensionPath });

    proc.on('error', (e) => chan.appendLine(`spawn error: ${String(e)}`));
    proc.on('exit',  (code, sig) => chan.appendLine(`server exit code=${code} signal=${sig}`));
    proc.stderr.on('data', d => chan.appendLine(String(d)));
    // optional if you want to see server stdout too:
    // proc.stdout.on('data', d => chan.appendLine('[LS] ' + String(d)));

    return { reader: proc.stdout!, writer: proc.stdin! } as StreamInfo;
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ language: 'udb', scheme: 'file' }],
  };

  client = new LanguageClient('udb', 'UDB Language Server', serverOptions, clientOptions);
  await client.start();
}

export async function deactivate() { if (client) await client.stop(); }
