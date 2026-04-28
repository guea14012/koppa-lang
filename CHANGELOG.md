# Changelog

All notable changes to KOPPA will be documented here.

## [3.0.0] - 2026-04-25

### Language — New Features
- **`class` / `new` / `self`** — full OOP with method binding and `new ClassName(args)`
- **Byte literals** `b"\x90\x90\xcc"` — bytes type with `.xor()`, `.hex`, `.b64`, `.len`
- **Bitwise operators** `&` `|` `^` `~` `<<` `>>` — fixed `>>` (was wrongly GT), proper `&` and `|`
- **Ternary expression** `cond ? a : b`
- **Null coalescing** `val ?: default`
- **Optional chaining** `obj?.field?.method()`
- **List comprehensions** `[x * 2 for x in items if x > 0]`
- **Dict comprehensions** `{k: v for k, v in pairs}`
- **Default parameters** `fn scan(host, port = 80, timeout = 1.0)`
- **Variadic parameters** `fn log(*messages)`
- **Spread operator** `[...list1, ...list2]` and `{...defaults, host: "x"}`
- **`not in`, `is`, `is not`** operators
- **`break` / `continue`** in loops
- **`+=`, `-=`, `*=`, `/=`, `%=`** compound assignment
- **Power operator `**`** — `2 ** 10 = 1024`
- **Triple-quoted strings** `"""multi\nline"""`
- **Hex/binary/octal literals** `0xFF`, `0b1010`, `0o77`
- **`for...else`** — else block runs if loop completes without break
- **Tuple destructuring** `let (host, port) = parse_addr(addr)`
- **`import` inside functions** — not just at module level

### Security Stdlib — New Modules
- **`vuln`** — `sqli_payloads()`, `xss_payloads()`, `lfi_payloads()`, `ssrf_payloads()`, `ssti_payloads()`, `cmdi_payloads()`, `test_sqli()`, `test_xss()`, `test_lfi()`, `scan_headers()`
- **`payload`** — `reverse_shell(lang, host, port)` (bash/python/php/nc/perl/ruby/go/powershell), `webshell(lang)`, `encode()`, `msf_pattern()`, `xor_encode()`
- **`bypass`** — `xss_variants()`, `sqli_variants()`, `ip_variants()`, `encode_chain()`, `null_byte()`, `random_ua()`
- **`session`** — HTTP sessions with persistent cookies, `get()`, `post()`, `set_header()`, `set_proxy()`
- **`scan`** (upgraded) — `mass(host, ports)`, `udp()`, `banner()`, `service()`, `port_range()`, `top_ports()`

### Bug Fixes
- `parse_dict()` now supports string keys `{"key": val}` — was breaking JWT/dict literals
- `Frame.__slots__` conflict with `field(default_factory)` — VM was crashing on load
- `VMCompiler.FOR` — loop variable was never bound (fixed GET_ITER/FOR_ITER)
- `VMCompiler.IF` — hardcoded labels caused nested-if collisions (now unique labels)
- `>>` operator was wrongly tokenized as `GT` token
- `import` inside function bodies now works
- All `APOLLO` references renamed to `KOPPA` throughout codebase
- `apollo_opcodes.py` is now a backwards-compat shim; canonical file is `koppa_opcodes.py`
- `compile` command crashed on Windows (unicode arrow `->` fix)

### Infrastructure
- Version bump: 2.0.1 -> 3.0.0
- README.md completely rewritten for KOPPA v3.0
- VS Code extension: added `new`, `self`, `is`, byte literal highlighting, better interpolation regex
- Test suite: 20/20 passing, scan tests use 60s timeout, new `features_test.kop`
- CI: cross-platform (Ubuntu/Windows/macOS) x Python (3.8/3.10/3.12)

## [2.0.1] - 2026-04-25

### Fixed
- `pyproject.toml` license format for Python 3.8 compatibility
- HTTP response member access (`resp.status`, `resp.body`, `resp.headers`)
- Test workflow skips network-dependent tests in CI (`--fast` flag)

### Added
- Standard library: 23 native modules, 300+ functions (`str`, `list`, `math`, `rand`, `time`, `regex`, `json`, `fs`, `os`, `color`, `fmt`, `net`, `dns`, `ssl`, `encode`, `hash`, `jwt`, `fuzz`, `brute`, `parse`, `report`, `smtp`, `ftp`)
- `try/catch/throw` error handling in interpreter
- `async fn` — async function support
- `parallel {}` — concurrent execution block
- VS Code extension: syntax highlighting, snippets, language configuration
- Language Specification (`docs/LANGUAGE_SPEC.md`)
- Getting Started guide (`docs/GETTING_STARTED.md`)
- Package registry with 199+ community packages
- Website redesign — modern dark UI matching brand colors

## [2.0.0] - 2026-04-13

### Added
- Complete bytecode compiler and VM (`apollo_opcodes.py`, `compiler.py`, `vm.py`)
- Package manager (`koppa pkg install/uninstall/list/search`)
- REPL with multi-line block support
- `koppa compile` → `.kpc` bytecode
- `koppa disasm` → disassemble bytecode
- Built-in modules: `log`, `scan`, `crypto`, `io`, `http`, `recon`, `enum`
- Pipeline operator `|>`
- Match/pattern matching
- `for`, `while` loops
- String interpolation `{varname}`

## [1.0.0] - 2026-03-24

### Added
- Initial release
- Lexer, parser, tree-walk interpreter
- Basic security primitives: TCP scan, hash, base64, HTTP GET/POST, DNS
- CLI: `koppa run`, `koppa repl`, `koppa lex`, `koppa parse`
