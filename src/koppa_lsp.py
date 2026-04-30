"""
KOPPA Language Server (LSP)
Provides autocomplete, hover docs, and diagnostics for .kop files.

Requires: pip install pygls lsprotocol
Start:    python src/koppa_lsp.py
VS Code:  install KOPPA extension (vscode-extension/)
"""

import sys
import re
from pathlib import Path

try:
    from pygls.server import LanguageServer
    from lsprotocol import types
except ImportError:
    print("pygls not installed. Run: pip install pygls lsprotocol")
    sys.exit(1)

_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── KOPPA completion data ─────────────────────────────────────────────────────

KEYWORDS = [
    "fn", "async", "await", "let", "var", "const", "return",
    "if", "elif", "else", "for", "while", "in", "break", "continue",
    "import", "export", "try", "catch", "throw", "match",
    "parallel", "emit", "class", "new", "self", "unsafe", "true", "false", "null"
]

MODULES = {
    "log":     {"info": "log.info(msg)", "warn": "log.warn(msg)", "error": "log.error(msg)",
                "debug": "log.debug(msg)", "success": "log.success(msg)"},
    "net":     {"tcp_connect": "net.tcp_connect(host, port) → bool",
                "service_name": "net.service_name(port) → string",
                "banner": "net.banner(host, port) → string",
                "dns_resolve": "net.dns_resolve(hostname) → string"},
    "hash":    {"md5": "hash.md5(data) → hex", "sha256": "hash.sha256(data) → hex",
                "sha512": "hash.sha512(data) → hex", "ntlm": "hash.ntlm(password) → hex",
                "identify": "hash.identify(hash_str) → type", "file": "hash.file(path) → hex"},
    "encode":  {"b64_encode": "encode.b64_encode(data) → string",
                "b64_decode": "encode.b64_decode(b64) → string",
                "hex_encode": "encode.hex_encode(data) → string",
                "url_encode": "encode.url_encode(data) → string",
                "rot13": "encode.rot13(data) → string"},
    "jwt":     {"decode": "jwt.decode(token) → dict",
                "is_expired": "jwt.is_expired(token) → bool",
                "none_alg": "jwt.none_alg(token) → string",
                "crack": "jwt.crack(token, wordlist) → secret|null",
                "sign": "jwt.sign(payload, secret) → token"},
    "http":    {"get": "http.get(url) → response",
                "post": "http.post(url, data) → response",
                "get_headers": "http.get_headers(url, headers) → response"},
    "os":      {"exec": "os.exec(cmd) → {stdout, stderr, returncode}",
                "hostname": "os.hostname() → string",
                "platform": "os.platform() → string",
                "username": "os.username() → string",
                "getpid": "os.getpid() → int",
                "read_file": "os.read_file(path) → string",
                "write_file": "os.write_file(path, content) → bool"},
    "inject":  {"list_procs": "inject.list_procs() → array",
                "find_pid": "inject.find_pid(name) → int",
                "shellcode": "inject.shellcode(pid, bytes) → dict",
                "dll": "inject.dll(pid, path) → dict",
                "apc": "inject.apc(pid, bytes) → dict"},
    "mem":     {"read": "mem.read(pid, addr, size) → bytes",
                "write": "mem.write(pid, addr, data) → dict",
                "alloc": "mem.alloc(pid, size) → int",
                "scan": "mem.scan(pid, pattern) → array",
                "modules": "mem.modules(pid) → array"},
    "evasion": {"is_debugged": "evasion.is_debugged() → bool",
                "is_vm": "evasion.is_vm() → dict",
                "is_sandbox": "evasion.is_sandbox() → dict",
                "patch_amsi": "evasion.patch_amsi() → dict",
                "patch_etw": "evasion.patch_etw() → dict",
                "sleep": "evasion.sleep(seconds, jitter?) → dict",
                "check_parent": "evasion.check_parent() → dict"},
    "covert":  {"dns_encode": "covert.dns_encode(data, domain) → dict",
                "dns_decode": "covert.dns_decode(fqdn, domain?) → string",
                "dns_exfil": "covert.dns_exfil(data, domain, ns?) → dict",
                "icmp_send": "covert.icmp_send(host, data) → dict",
                "http_hide": "covert.http_hide(url, data, header?) → dict"},
    "crypt":   {"xor": "crypt.xor(data, key) → bytes",
                "rc4": "crypt.rc4(data, key) → bytes",
                "aes_encrypt": "crypt.aes_encrypt(pt, key, iv?) → dict",
                "aes_decrypt": "crypt.aes_decrypt(ct, key, iv) → bytes",
                "chacha20": "crypt.chacha20(data, key, nonce?) → dict",
                "rsa_gen": "crypt.rsa_gen(bits?) → dict",
                "derive_key": "crypt.derive_key(pwd, salt?) → dict",
                "gen_key": "crypt.gen_key(bits?) → bytes",
                "gen_iv": "crypt.gen_iv() → bytes",
                "hmac": "crypt.hmac(data, key) → hex"},
    "dns":     {"resolve": "dns.resolve(hostname) → ip",
                "reverse": "dns.reverse(ip) → hostname",
                "mx": "dns.mx(domain) → array",
                "ns": "dns.ns(domain) → array",
                "txt": "dns.txt(domain) → array",
                "cname": "dns.cname(domain) → string"},
    "fuzz":    {"dirs": "fuzz.dirs(url, wordlist) → array",
                "params": "fuzz.params(url, param, wordlist) → array",
                "headers": "fuzz.headers(url, header, wordlist) → array"},
    "str":     {"upper": "str.upper(s) → string", "lower": "str.lower(s) → string",
                "strip": "str.strip(s) → string", "split": "str.split(s, sep) → array",
                "replace": "str.replace(s, old, new) → string",
                "contains": "str.contains(s, sub) → bool",
                "len": "str.len(s) → int"},
    "math":    {"abs": "math.abs(x)", "sqrt": "math.sqrt(x)", "pow": "math.pow(x, y)"},
    "rand":    {"hex": "rand.hex(n) → string", "int": "rand.int(lo, hi) → int",
                "ua": "rand.ua() → user_agent_string", "uuid": "rand.uuid() → string"},
    "time":    {"now": "time.now() → string", "sleep": "time.sleep(seconds)",
                "timestamp": "time.timestamp() → int"},
    "regex":   {"match": "regex.match(pattern, s) → bool",
                "findall": "regex.findall(pattern, s) → array",
                "extract_ips": "regex.extract_ips(text) → array",
                "extract_emails": "regex.extract_emails(text) → array"},
    "json":    {"parse": "json.parse(s) → dict", "stringify": "json.stringify(obj) → string",
                "pretty": "json.pretty(obj) → string"},
    "fs":      {"read": "fs.read(path) → string", "write": "fs.write(path, content)",
                "exists": "fs.exists(path) → bool", "list": "fs.list(dir) → array"},
    "report":  {"finding": "report.finding(name, severity, desc) → dict",
                "summary": "report.summary(findings) → string",
                "terminal": "report.terminal(findings) → string",
                "save": "report.save(findings, path)"},
}

SNIPPETS = {
    "fn":      "fn ${1:name}(${2:params}) {\n\t${3:# body}\n}",
    "if":      "if ${1:condition} {\n\t${2}\n}",
    "for":     "for ${1:item} in ${2:collection} {\n\t${3}\n}",
    "while":   "while ${1:condition} {\n\t${2}\n}",
    "import":  "import ${1:module}",
    "try":     "try {\n\t${1}\n} catch (${2:err}) {\n\t${3}\n}",
    "match":   "match ${1:expr} {\n\t${2} => { ${3} }\n\t_ => { ${4} }\n}",
    "unsafe":  "unsafe {\n\t${1}\n}",
    "async":   "async fn ${1:name}(${2}) {\n\t${3}\n}",
    "class":   "class ${1:Name} {\n\tfn __init__(self) {\n\t\t${2}\n\t}\n}",
}

# ── LSP Server ────────────────────────────────────────────────────────────────
server = LanguageServer("koppa-lsp", "v1.0")

def _parse_diagnostics(source: str) -> list:
    """Run KOPPA parser and return diagnostics."""
    diagnostics = []
    try:
        from parser import parse
        parse(source)
    except Exception as e:
        msg = str(e)
        # Extract line number from error message if available
        line_match = re.search(r'[Ll]ine (\d+)', msg)
        line = int(line_match.group(1)) - 1 if line_match else 0
        diagnostics.append(types.Diagnostic(
            range=types.Range(
                start=types.Position(line=max(0, line), character=0),
                end=types.Position(line=max(0, line), character=100)
            ),
            message=msg,
            severity=types.DiagnosticSeverity.Error,
            source="koppa"
        ))
    return diagnostics


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params):
    doc = ls.workspace.get_document(params.text_document.uri)
    diags = _parse_diagnostics(doc.source)
    ls.publish_diagnostics(params.text_document.uri, diags)


@server.feature(
    types.TEXT_DOCUMENT_COMPLETION,
    types.CompletionOptions(trigger_characters=[".", " ", "\n"])
)
def completions(ls: LanguageServer, params: types.CompletionParams):
    doc   = ls.workspace.get_document(params.text_document.uri)
    lines = doc.source.split("\n")
    line  = lines[params.position.line] if params.position.line < len(lines) else ""
    col   = params.position.character
    prefix = line[:col]

    items = []

    # module.method completion
    dot_match = re.search(r'(\w+)\.$', prefix)
    if dot_match:
        mod_name = dot_match.group(1)
        if mod_name in MODULES:
            for method, doc_str in MODULES[mod_name].items():
                items.append(types.CompletionItem(
                    label=method,
                    kind=types.CompletionItemKind.Method,
                    detail=doc_str,
                    insert_text=method
                ))
        return types.CompletionList(is_incomplete=False, items=items)

    # Keyword completions
    for kw in KEYWORDS:
        snip = SNIPPETS.get(kw)
        items.append(types.CompletionItem(
            label=kw,
            kind=types.CompletionItemKind.Keyword,
            insert_text=snip or kw,
            insert_text_format=types.InsertTextFormat.Snippet if snip else types.InsertTextFormat.PlainText
        ))

    # Module name completions (after import or standalone)
    for mod in MODULES:
        items.append(types.CompletionItem(
            label=mod,
            kind=types.CompletionItemKind.Module,
            detail=f"KOPPA stdlib module: {mod}",
            insert_text=mod
        ))

    return types.CompletionList(is_incomplete=False, items=items)


@server.feature(types.TEXT_DOCUMENT_HOVER)
def hover(ls: LanguageServer, params: types.HoverParams):
    doc   = ls.workspace.get_document(params.text_document.uri)
    lines = doc.source.split("\n")
    line  = lines[params.position.line] if params.position.line < len(lines) else ""

    # Detect module.method under cursor
    col = params.position.character
    match = re.search(r'(\w+)\.(\w+)', line)
    if match and match.start() <= col <= match.end():
        mod, meth = match.group(1), match.group(2)
        if mod in MODULES and meth in MODULES[mod]:
            return types.Hover(
                contents=types.MarkupContent(
                    kind=types.MarkupKind.Markdown,
                    value=f"```koppa\n{MODULES[mod][meth]}\n```"
                )
            )
        if mod in MODULES:
            methods = "\n".join(f"- `{m}`" for m in MODULES[mod])
            return types.Hover(
                contents=types.MarkupContent(
                    kind=types.MarkupKind.Markdown,
                    value=f"**{mod}** module\n\n{methods}"
                )
            )
    return None


@server.feature(types.TEXT_DOCUMENT_SIGNATURE_HELP,
                types.SignatureHelpOptions(trigger_characters=["("]))
def signature_help(ls: LanguageServer, params: types.SignatureHelpParams):
    doc  = ls.workspace.get_document(params.text_document.uri)
    line = doc.source.split("\n")[params.position.line]
    col  = params.position.character
    prefix = line[:col]
    match = re.search(r'(\w+)\.(\w+)\($', prefix)
    if match:
        mod, meth = match.group(1), match.group(2)
        if mod in MODULES and meth in MODULES[mod]:
            sig_str = MODULES[mod][meth]
            return types.SignatureHelp(signatures=[
                types.SignatureInformation(label=sig_str)
            ])
    return None


if __name__ == "__main__":
    print("KOPPA Language Server starting (stdio mode)...")
    server.start_io()
