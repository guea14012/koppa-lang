const vscode = require('vscode')
const path   = require('path')
const { LanguageClient, TransportKind } = require('vscode-languageclient/node')

let client = null

function activate(context) {
  const config = vscode.workspace.getConfiguration('koppa')

  // ── Commands ───────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('koppa.runFile', () => {
      const editor = vscode.window.activeTextEditor
      if (!editor) return
      const file = editor.document.fileName
      const term = vscode.window.createTerminal('KOPPA Run')
      term.show()
      term.sendText(`koppa run "${file}"`)
    }),
    vscode.commands.registerCommand('koppa.openPlayground', () => {
      vscode.env.openExternal(vscode.Uri.parse(
        'https://guea14012.github.io/koppa-lang/playground.html'
      ))
    }),
    vscode.commands.registerCommand('koppa.openRegistry', () => {
      vscode.env.openExternal(vscode.Uri.parse(
        'https://guea14012.github.io/koppa-registry-/'
      ))
    })
  )

  // ── LSP ────────────────────────────────────────────────────────────────────
  if (!config.get('lsp.enabled')) return

  const python     = config.get('lsp.pythonPath') || 'python'
  const serverPath = config.get('lsp.serverPath') ||
    path.join(__dirname, '..', 'src', 'koppa_lsp.py')

  const serverOptions = {
    run:   { command: python, args: [serverPath], transport: TransportKind.stdio },
    debug: { command: python, args: [serverPath], transport: TransportKind.stdio }
  }

  const clientOptions = {
    documentSelector: [{ scheme: 'file', language: 'koppa' }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.kop')
    }
  }

  client = new LanguageClient('koppa-lsp', 'KOPPA Language Server',
                               serverOptions, clientOptions)
  client.start()
  context.subscriptions.push(client)

  vscode.window.setStatusBarMessage('$(check) KOPPA LSP active', 3000)
}

function deactivate() {
  if (client) return client.stop()
}

module.exports = { activate, deactivate }
