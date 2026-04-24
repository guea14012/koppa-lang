#!/usr/bin/env python3
"""
KOPPA Language Runner v2.0
Main entry point — interpreter-first, bytecode VM optional.

Usage:
    koppa run <script.kop> [args...]   # Run script (default: interpreter)
    koppa run --vm <script.kop>        # Run with bytecode VM
    koppa compile <script.kop>         # Compile to .kpc bytecode
    koppa disasm <file>                # Disassemble bytecode
    koppa repl                         # Interactive REPL
    koppa lex <script.kop>             # Show tokens
    koppa parse <script.kop>           # Show AST
    koppa version                      # Show version info
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path

# Ensure src/ is on the path regardless of where we're called from
_SRC_DIR = Path(__file__).parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

KOPPA_ROOT = _SRC_DIR.parent
VERSION = "2.0.0"
BANNER = r"""
 _  __  ___  ____  ____   _
| |/ / / _ \|  _ \|  _ \ / \
| ' / | | | | |_) | |_) / _ \
| . \ | |_| |  __/|  __/ ___ \
|_|\_\ \___/|_|   |_| /_/   \_\

  Advanced Pentesting DSL v{version}
"""


# ─── Helpers ────────────────────────────────────────────────────────────────

def _require_file(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    return p


# ─── Run modes ──────────────────────────────────────────────────────────────

def run_interpreter(filepath: str, script_args: list = None):
    """Run script with tree-walk interpreter (default, most compatible)"""
    from interpreter import Interpreter, ReturnException
    from parser import parse

    src = _require_file(filepath).read_text(encoding="utf-8")
    try:
        ast = parse(src)
        interp = Interpreter()
        # Expose CLI args as a built-in
        from interpreter import RuntimeValue
        cli = [RuntimeValue(a, "string") for a in (script_args or [])]
        interp.env.variables["__args__"] = RuntimeValue(cli, "array")
        try:
            result = interp.execute(ast)
        except ReturnException as e:
            result = e.value
        # Only print a result if it's non-None and the script didn't print it
        # (scripts use log.info for output; we don't auto-print)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        if os.getenv("KOPPA_DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_vm(filepath: str, script_args: list = None):
    """Run script with bytecode compiler + VM"""
    from compiler import Compiler, Optimizer
    from vm import VirtualMachine

    src = _require_file(filepath).read_text(encoding="utf-8")
    try:
        compiler = Compiler()
        optimizer = Optimizer()
        code = compiler.compile(src, str(filepath))
        code = optimizer.optimize(code)
        vm = VirtualMachine()
        vm.run(code, script_args=script_args or [])
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        if os.getenv("KOPPA_DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_bytecode(filepath: str, script_args: list = None):
    """Run pre-compiled .kpc bytecode"""
    import pickle
    from vm import VirtualMachine
    from apollo_opcodes import CodeObject

    p = _require_file(filepath)
    with open(p, "rb") as f:
        code = pickle.load(f)
    if not isinstance(code, CodeObject):
        print(f"Error: Invalid bytecode file: {filepath}", file=sys.stderr)
        sys.exit(1)
    vm = VirtualMachine()
    vm.run(code, script_args=script_args or [])


def compile_file(filepath: str, output: str = None):
    """Compile source to .kpc bytecode"""
    import pickle
    from compiler import Compiler

    src = _require_file(filepath).read_text(encoding="utf-8")
    out = output or str(filepath).replace(".kop", ".kpc").replace(".apo", ".kpc")
    compiler = Compiler()
    code = compiler.compile(src, str(filepath))
    with open(out, "wb") as f:
        pickle.dump(code, f)
    print(f"Compiled: {filepath} → {out}")
    print(f"  Instructions : {len(code.instructions)}")
    print(f"  Constants    : {len(code.constants)}")


def disasm(filepath: str):
    """Disassemble bytecode or show bytecode of source file"""
    import pickle
    from compiler import Compiler

    p = _require_file(filepath)
    if filepath.endswith((".kop", ".apo")):
        src = p.read_text(encoding="utf-8")
        compiler = Compiler()
        code = compiler.compile(src, filepath)
    else:
        with open(p, "rb") as f:
            code = pickle.load(f)

    print(f"Code Object : {code.name}  [{filepath}]")
    print(f"Constants   : {code.constants}")
    print(f"Names       : {code.names}")
    print()
    print("Instructions:")
    for i, instr in enumerate(code.instructions):
        print(f"  {i:04d}: {instr}")


def cmd_lex(filepath: str):
    """Print token stream"""
    from lexer import tokenize
    src = _require_file(filepath).read_text(encoding="utf-8")
    for tok in tokenize(src):
        print(tok)


def cmd_parse(filepath: str):
    """Print AST"""
    from parser import parse
    import json

    src = _require_file(filepath).read_text(encoding="utf-8")
    ast = parse(src)

    def node_to_dict(n):
        if n is None:
            return None
        return {
            "type": n.node_type.name,
            "value": str(n.value) if n.value is not None else None,
            "children": [node_to_dict(c) for c in n.children],
        }

    print(json.dumps(node_to_dict(ast), indent=2))


# ─── REPL ────────────────────────────────────────────────────────────────────

def repl():
    """Interactive interpreter REPL"""
    from interpreter import Interpreter, RuntimeValue, ReturnException
    from parser import parse

    print(BANNER.format(version=VERSION))
    print("Type 'exit' or Ctrl+C to quit  |  'help' for commands\n")

    interp = Interpreter()
    multiline_buf = []

    while True:
        try:
            prompt = "... " if multiline_buf else "koppa> "
            try:
                line = input(prompt)
            except EOFError:
                print()
                break

            # Built-in REPL commands
            stripped = line.strip()
            if stripped in ("exit", "quit"):
                break
            if stripped == "help":
                print("  exit / quit   — leave REPL")
                print("  modules       — list available modules")
                print("  clear         — clear screen")
                print("  Multi-line    — open a { block and close it with }")
                continue
            if stripped == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            if stripped == "modules":
                aliases = Interpreter._MODULE_ALIASES
                print("Built-in modules (use 'import <name>'):")
                for name in aliases:
                    print(f"  {name}")
                continue

            # Multi-line block buffering
            multiline_buf.append(line)
            src = "\n".join(multiline_buf)

            # Simple heuristic: if open braces exceed close braces, keep reading
            if src.count("{") > src.count("}"):
                continue

            multiline_buf = []

            if not src.strip():
                continue

            try:
                ast = parse(src)
                try:
                    result = interp.execute(ast)
                except ReturnException as e:
                    result = e.value
                if result is not None and getattr(result, "value", None) is not None:
                    print(f"= {result.value!r}")
            except Exception as e:
                print(f"Error: {e}")

        except KeyboardInterrupt:
            multiline_buf = []
            print("\n(Ctrl+C — buffer cleared. Type 'exit' to quit)")


# ─── Version ─────────────────────────────────────────────────────────────────

def show_version():
    print(BANNER.format(version=VERSION))
    print(f"Version   : {VERSION}")
    print(f"Python    : {sys.version.split()[0]}")
    print(f"Root      : {KOPPA_ROOT}")
    print()
    print("Built-in modules: log  scan  crypto  io  http  recon  enum")
    print("Run modes       : interpreter (default)  |  bytecode VM  |  Deno")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _run_source(source: str):
    """Execute a source string directly (used by -c flag)."""
    from interpreter import Interpreter, ReturnException
    from parser import parse
    try:
        ast = parse(source)
        interp = Interpreter()
        try:
            interp.execute(ast)
        except ReturnException:
            pass
    except Exception as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        if os.getenv("KOPPA_DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _usage():
    print(f"KOPPA Language v{VERSION}")
    print()
    print("Usage:")
    print("  koppa run [--vm] <script.kop> [args...]  — run script")
    print("  koppa -c 'code'                          — run inline code")
    print("  koppa compile <script.kop>               — compile to bytecode")
    print("  koppa disasm <file>                      — disassemble")
    print("  koppa repl                               — interactive REPL")
    print("  koppa lex <script.kop>                   — show tokens")
    print("  koppa parse <script.kop>                 — show AST")
    print("  koppa pkg <command>                      — package manager")
    print("  koppa version                            — version info")
    print()
    print("Environment:")
    print("  KOPPA_DEBUG=1   — show full tracebacks on error")


def main():
    args = sys.argv[1:]

    if not args:
        _usage()
        sys.exit(0)

    cmd = args[0]

    # Direct file execution: koppa script.kop [args]
    if cmd.endswith((".kop", ".apo", ".kpc")):
        if cmd.endswith(".kpc"):
            run_bytecode(cmd, args[1:])
        else:
            run_interpreter(cmd, args[1:])
        return

    if cmd == "run":
        rest = args[1:]
        use_vm = False
        if rest and rest[0] == "--vm":
            use_vm = True
            rest = rest[1:]
        if not rest:
            print("Error: no script file specified.", file=sys.stderr)
            sys.exit(1)
        filepath, script_args = rest[0], rest[1:]
        if use_vm:
            run_vm(filepath, script_args)
        else:
            run_interpreter(filepath, script_args)

    elif cmd == "interp":
        if len(args) < 2:
            print("Error: no script file specified.", file=sys.stderr)
            sys.exit(1)
        run_interpreter(args[1], args[2:])

    elif cmd == "vm":
        if len(args) < 2:
            print("Error: no script file specified.", file=sys.stderr)
            sys.exit(1)
        run_vm(args[1], args[2:])

    elif cmd == "compile":
        if len(args) < 2:
            print("Error: no script file specified.", file=sys.stderr)
            sys.exit(1)
        out = args[2] if len(args) > 2 else None
        compile_file(args[1], out)

    elif cmd == "disasm":
        if len(args) < 2:
            print("Error: no file specified.", file=sys.stderr)
            sys.exit(1)
        disasm(args[1])

    elif cmd == "lex":
        if len(args) < 2:
            print("Error: no file specified.", file=sys.stderr)
            sys.exit(1)
        cmd_lex(args[1])

    elif cmd == "parse":
        if len(args) < 2:
            print("Error: no file specified.", file=sys.stderr)
            sys.exit(1)
        cmd_parse(args[1])

    elif cmd == "repl":
        repl()

    elif cmd == "pkg":
        from pkg_manager import main as pkg_main
        pkg_main(args[1:])

    elif cmd in ("-c", "--eval"):
        if len(args) < 2:
            print("Error: no code provided after -c", file=sys.stderr)
            sys.exit(1)
        _run_source(args[1])

    elif cmd in ("version", "--version", "-v"):
        show_version()

    elif cmd in ("help", "--help", "-h"):
        _usage()

    else:
        print(f"Unknown command: {cmd!r}  (run 'koppa help' for usage)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
