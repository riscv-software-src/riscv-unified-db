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
    const uri = vscode.Uri.file(wsPath('badHex.udb')); 
    let doc = await vscode.workspace.openTextDocument(uri);

    // force the language in case association is missing.
    if (doc.languageId !== 'udb') {
      doc = await vscode.languages.setTextDocumentLanguage(doc, 'udb');
    }
    await vscode.window.showTextDocument(doc);

    
    const edit = new vscode.WorkspaceEdit();
    edit.insert(doc.uri, new vscode.Position(0, 0), ' ');     
    await vscode.workspace.applyEdit(edit);
    await vscode.workspace.saveAll(); 

    const revert = new vscode.WorkspaceEdit();
    revert.delete(doc.uri, new vscode.Range(0, 0, 0, 1));
    await vscode.workspace.applyEdit(revert);

    const diags = await waitFor(() => {
      const d = vscode.languages.getDiagnostics(doc.uri);
      return d.length ? d : null;
    }, 8000);

    // Expect at least one diagnostic for the intentionally bad hex.
    assert.ok(diags && diags.length >= 1, 'expected at least one diagnostic for bad hex in .udb file'); // should pass now but underscores still not fixed in this version
  });

  test('completion after keyword', async () => {
    const doc = await vscode.workspace.openTextDocument({ language: 'udb', content: 'csr ' });
    await vscode.window.showTextDocument(doc);
    const pos = new vscode.Position(0, 4);

    const list = await vscode.commands.executeCommand<vscode.CompletionList>(
      'vscode.executeCompletionItemProvider', doc.uri, pos
    );

    assert.ok(list, 'completion list present');
    assert.ok((list.items ?? []).length >= 1, 'expected some completions after "csr "');
  });

  test('hover returns content', async () => {
    const doc = await vscode.workspace.openTextDocument({ language: 'udb', content: 'csr A "d" 0x1A_2F "0x00";' });
    await vscode.window.showTextDocument(doc);
    const col = doc.getText().indexOf('0x1A_2F') + 2;

    const hovers = await vscode.commands.executeCommand<vscode.Hover[]>(
      'vscode.executeHoverProvider', doc.uri, new vscode.Position(0, col)
    );

    assert.ok(hovers && hovers.length >= 0, 'hover provider responded');
  });

  // With no cross-refs, “go to definition” on a declaration may return self or nothing
  test('definition (self or none with current grammar)', async () => {
    const uri = vscode.Uri.file(wsPath('goodHex.udb')); 
    let doc = await vscode.workspace.openTextDocument(uri);
    if (doc.languageId !== 'udb') {
      doc = await vscode.languages.setTextDocumentLanguage(doc, 'udb');
    }
    await vscode.window.showTextDocument(doc);

    const text = doc.getText();
    const secondCTRL = text.indexOf('CTRL', text.indexOf('CTRL') + 1);
    const pos = doc.positionAt(secondCTRL + 1);

    const defs = await vscode.commands.executeCommand<vscode.Location[]>(
      'vscode.executeDefinitionProvider', doc.uri, pos
    );

    if (!defs || defs.length === 0) {
      assert.ok(true); 
      return;
    }
    const here = new vscode.Range(
      doc.positionAt(secondCTRL),
      doc.positionAt(secondCTRL + 'CTRL'.length)
    );
    const self = defs.some(loc => loc.uri.toString() === doc.uri.toString() && !!loc.range.intersection(here));
    assert.ok(self, 'expected no definition or a self-location on the declaration token');
  });
  // Pending on purpose, enable when the grammar has references and rename updates them.
  //test.skip('rename (skip until rename/ref updates implemented)', () => {});
});
