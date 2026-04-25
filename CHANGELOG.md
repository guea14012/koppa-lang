# Changelog

All notable changes to KOPPA will be documented here.

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
