"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const cp = __importStar(require("child_process"));
const vscode = __importStar(require("vscode"));
const node_1 = require("vscode-languageclient/node");
let client;
async function activate(ctx) {
    const java = vscode.workspace.getConfiguration('udb').get('javaPath') || 'java';
    const jar = ctx.asAbsolutePath('server/udb-ls-all.jar');
    const serverOptions = async () => {
        const proc = cp.spawn(java, ['-jar', jar, '-stdio'], { cwd: ctx.extensionPath });
        proc.stderr.on('data', d => console.error(String(d)));
        return Promise.resolve({ reader: proc.stdout, writer: proc.stdin });
    };
    const clientOptions = {
        documentSelector: [{ language: 'udb', scheme: 'file' }],
    };
    client = new node_1.LanguageClient('udb', 'UDB Language Server', serverOptions, clientOptions);
    await client.start();
}
async function deactivate() { if (client)
    await client.stop(); }
//# sourceMappingURL=extension.js.map
