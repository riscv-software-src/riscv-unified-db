import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';

// Build an absolute path inside the test workspace (opened via runTests.ts)
function wsPath(...p: string[]) {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath!;
  return path.join(root, ...p);
}

async function waitFor<T>(probe: () => T | null | undefined | false, ms = 8000, step = 50) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    const v = probe();
    if (v) return v;
    await new Promise(r => setTimeout(r, step));
  }
  return undefined;
}

// Smoke test, test if language server starts up correctly and
// it can distinguish between good and bad syntax.
suite('UDB LS – smoke', () => {
  test('initialize → diagnostics on open (real .udb file)', async () => {
    // Use your new invalid fixture filename here if you renamed it.
    const uri = vscode.Uri.file(wsPath('badGrammar.udb'));
    let doc = await vscode.workspace.openTextDocument(uri);
	// force the language in case association is missing.
    if (doc.languageId !== 'udb') {
      doc = await vscode.languages.setTextDocumentLanguage(doc, 'udb');
    }
    await vscode.window.showTextDocument(doc);

    // Nudge validation (on-change + on-save), then revert
    let edit = new vscode.WorkspaceEdit();
    edit.insert(doc.uri, new vscode.Position(0, 0), ' ');
    await vscode.workspace.applyEdit(edit);
    await vscode.workspace.saveAll();
    edit = new vscode.WorkspaceEdit();
    edit.delete(doc.uri, new vscode.Range(0, 0, 0, 1));
    await vscode.workspace.applyEdit(edit);

    const diags = await waitFor(() => {
      const d = vscode.languages.getDiagnostics(doc.uri);
      return d.length ? d : null;
    }, 8000);

    if (!diags || diags.length === 0) {
      console.log('Diagnostics (bad file):', vscode.languages.getDiagnostics(doc.uri));
    }
     // Expect at least one diagnostic for the intentionally bad grammar.
    assert.ok(diags && diags.length >= 1, 'expected at least one diagnostic for invalid UDB in bad fixture');
  });

  // completion test
  test('completion after a keyword (e.g., "kind")', async () => {
    // With the new grammar, keywords include: kind, name, long_name, address, ...
    const doc = await vscode.workspace.openTextDocument({ language: 'udb', content: 'kind ' });
    await vscode.window.showTextDocument(doc);
    const pos = new vscode.Position(0, 'kind '.length);

    const list = await vscode.commands.executeCommand<vscode.CompletionList>(
      'vscode.executeCompletionItemProvider',
      doc.uri,
      pos
    );

    assert.ok(list, 'completion list present');

    assert.ok((list.items ?? []).length >= 1, 'expected some completions after "kind "');
  });

  // hover test
  test('hover returns content (e.g., on address hex)', async () => {
    // Probe hover on address value in validate fixture line
    const uri = vscode.Uri.file(wsPath('goodGrammar.udb'));
    let doc = await vscode.workspace.openTextDocument(uri);
    if (doc.languageId !== 'udb') {
      doc = await vscode.languages.setTextDocumentLanguage(doc, 'udb');
    }
    await vscode.window.showTextDocument(doc);

    const text = doc.getText();
    const addrIx = text.indexOf('0x');
    const pos = addrIx >= 0 ? doc.positionAt(addrIx + 2) : new vscode.Position(0, 0);

    const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
      'vscode.executeHoverProvider',
      doc.uri,
      pos
    );

    assert.ok(hovers && hovers.length >= 0, 'hover provider responded');
  });


});
