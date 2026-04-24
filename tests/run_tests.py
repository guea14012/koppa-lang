#!/usr/bin/env python3
"""
KOPPA Test Runner
Runs all .kop test files and reports pass/fail.

Usage:
    python tests/run_tests.py           # run all tests
    python tests/run_tests.py -v        # verbose output
    python tests/run_tests.py --fast    # skip slow network tests
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
TESTS_DIR    = PROJECT_ROOT / "tests"

# Ensure interpreter is importable
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ── Inline unit tests (no .kop files needed) ────────────────────────────────

def test_lexer_tokens():
    """Lexer produces correct token types for basic constructs."""
    from lexer import tokenize, TokenType
    tokens = {t.type for t in tokenize('let x = 42 + "hi"')}
    assert TokenType.LET       in tokens, "missing LET"
    assert TokenType.IDENTIFIER in tokens, "missing IDENTIFIER"
    assert TokenType.ASSIGN    in tokens, "missing ASSIGN"
    assert TokenType.INTEGER   in tokens, "missing INTEGER"
    assert TokenType.PLUS      in tokens, "missing PLUS"
    assert TokenType.STRING    in tokens, "missing STRING"


def test_lexer_operators():
    """Lexer handles compound operators: ||, ==, =>, |>"""
    from lexer import tokenize, TokenType
    src = "a || b == c => d |> e"
    tmap = {t.type: t for t in tokenize(src)}
    assert TokenType.OR        in tmap, "|| not tokenised"
    assert TokenType.EQ        in tmap, "== not tokenised"
    assert TokenType.FAT_ARROW in tmap, "=> not tokenised"
    assert TokenType.PIPE      in tmap, "|> not tokenised"


def test_parser_literal():
    """Parser wraps literals in LITERAL nodes."""
    from parser import parse, ASTNodeType
    ast = parse("42")
    # Root is MODULE; dig to the LITERAL node inside
    assert ast.node_type == ASTNodeType.MODULE
    stmt = ast.children[0]  # EXPRESSION_STMT or LITERAL
    # Walk one more level if needed
    leaf = stmt.children[0] if stmt.children else stmt
    assert leaf.node_type == ASTNodeType.LITERAL, f"expected LITERAL got {leaf.node_type}"
    assert leaf.value == 42, f"expected 42 got {leaf.value}"


def test_interpreter_arithmetic():
    """Interpreter evaluates arithmetic correctly."""
    from interpreter import Interpreter, ReturnException
    from parser import parse
    interp = Interpreter()
    ast = parse("let x = 3 + 4 * 2")
    interp.execute(ast)
    val = interp.env.get("x")
    assert val.value == 11, f"expected 11 got {val.value}"


def test_interpreter_string_concat():
    """String + int coercion works."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    ast = parse('let s = "port " + 80')
    interp.execute(ast)
    val = interp.env.get("s")
    assert val.value == "port 80", f"expected 'port 80' got {val.value!r}"


def test_interpreter_array():
    """Array literals and indexing work."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    ast = parse("let arr = [10, 20, 30]")
    interp.execute(ast)
    val = interp.env.get("arr")
    assert isinstance(val.value, list), "arr not a list"
    assert len(val.value) == 3
    assert val.value[1].value == 20


def test_interpreter_function():
    """Functions execute and return values."""
    from interpreter import Interpreter, ReturnException
    from parser import parse
    interp = Interpreter()
    src = """
fn add(a, b) {
    return a + b
}
let result = add(3, 7)
"""
    interp.execute(parse(src))
    val = interp.env.get("result")
    assert val.value == 10, f"expected 10 got {val.value}"


def test_interpreter_if_else():
    """If/else branching works."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    src = "let x = 5\nif x > 3 {\n  let msg = true\n}"
    interp.execute(parse(src))
    assert interp.env.get("x").value == 5


def test_string_interpolation():
    """String interpolation substitutes variables."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let name = "world"\nlet msg = "hello {name}"'))
    val = interp.env.get("msg")
    assert val.value == "hello world", f"got {val.value!r}"


def test_pkg_resolve_missing():
    """resolve_package_path returns None for non-existent package."""
    from pkg_manager import resolve_package_path
    result = resolve_package_path("__nonexistent_package_xyz__")
    assert result is None


# ── Script runner ────────────────────────────────────────────────────────────

def run_kop_file(path: Path, verbose: bool) -> bool:
    """Run a .kop file via the koppa CLI and return True if it exits 0."""
    try:
        result = subprocess.run(
            [sys.executable, str(SRC_DIR / "koppa.py"), "run", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        if verbose:
            if result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    print(f"    | {line}")
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines():
                    print(f"    ! {line}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# ── Registry ─────────────────────────────────────────────────────────────────

UNIT_TESTS = [
    test_lexer_tokens,
    test_lexer_operators,
    test_parser_literal,
    test_interpreter_arithmetic,
    test_interpreter_string_concat,
    test_interpreter_array,
    test_interpreter_function,
    test_interpreter_if_else,
    test_string_interpolation,
    test_pkg_resolve_missing,
]

# .kop files that must succeed (no network, no root needed)
SAFE_EXAMPLES = [
    "hello.kop",
    "hash_demo.kop",
]

# .kop files that require network / local services (skipped in --fast mode)
NETWORK_EXAMPLES = [
    "quick_scan.kop",
    "port_scanner.kop",
    "web_check.kop",
    "dns_recon.kop",
]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--fast", action="store_true", help="skip network-dependent tests")
    opts = parser.parse_args()

    passed = failed = skipped = 0

    # ── Unit tests ──────────────────────────────────────────────
    print("Unit tests:")
    for fn in UNIT_TESTS:
        name = fn.__name__
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            if opts.verbose:
                import traceback
                traceback.print_exc()
            failed += 1

    # ── Example scripts ─────────────────────────────────────────
    print("\nExample scripts:")
    for fname in SAFE_EXAMPLES:
        path = EXAMPLES_DIR / fname
        if not path.exists():
            print(f"  [SKIP] {fname} (file missing)")
            skipped += 1
            continue
        ok = run_kop_file(path, opts.verbose)
        if ok:
            print(f"  [PASS] {fname}")
            passed += 1
        else:
            print(f"  [FAIL] {fname}")
            failed += 1

    if not opts.fast:
        for fname in NETWORK_EXAMPLES:
            path = EXAMPLES_DIR / fname
            if not path.exists():
                skipped += 1
                continue
            ok = run_kop_file(path, opts.verbose)
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {fname}")
            if ok:
                passed += 1
            else:
                failed += 1
    else:
        skipped += len(NETWORK_EXAMPLES)

    # ── Summary ─────────────────────────────────────────────────
    total = passed + failed + skipped
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} passed  |  {failed} failed  |  {skipped} skipped")
    print(f"{'='*40}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
