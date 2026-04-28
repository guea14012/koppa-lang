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


def test_bitwise_ops():
    """Bitwise operators &, |, ^, ~, <<, >> work correctly."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse("""
let band  = 0xFF & 0x0F
let bor   = 0b001 | 0b010
let bxor  = 0xFF ^ 0x0F
let lsh   = 1 << 4
let rsh   = 0x100 >> 4
let bnot  = ~0
"""))
    assert interp.env.get("band").value  == 15,  "& failed"
    assert interp.env.get("bor").value   == 3,   "| failed"
    assert interp.env.get("bxor").value  == 0xF0, "^ failed"
    assert interp.env.get("lsh").value   == 16,  "<< failed"
    assert interp.env.get("rsh").value   == 16,  ">> failed"
    assert interp.env.get("bnot").value  == -1,  "~ failed"


def test_byte_literals():
    """Byte literals b\"..\" create KoppaBytes with correct hex/xor."""
    from interpreter import Interpreter, KoppaBytes
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let sc = b"\\x90\\x41\\xcc"'))
    val = interp.env.get("sc")
    assert isinstance(val.value, KoppaBytes), "not KoppaBytes"
    assert val.value.hex() == "9041cc", f"hex wrong: {val.value.hex()}"
    xored = val.value.xor(0x41)
    assert xored.data[1] == 0x00, "xor(0x41) of 0x41 should be 0x00"


def test_ternary():
    """Ternary expression cond ? a : b works."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let x = 10\nlet r = x > 5 ? "big" : "small"'))
    assert interp.env.get("r").value == "big", "ternary failed"


def test_null_coalesce():
    """Null coalescing ?: returns default when left is None."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let a = None\nlet b = a ?: "default"'))
    assert interp.env.get("b").value == "default", "?: failed"


def test_list_comprehension():
    """List comprehension [x for x in y if cond] works."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let nums = [1,2,3,4,5,6]\nlet evens = [n for n in nums if n % 2 == 0]'))
    evens = [v.value if hasattr(v, "value") else v for v in interp.env.get("evens").value]
    assert evens == [2, 4, 6], f"comprehension wrong: {evens}"


def test_class_definition():
    """class + new + self works with method calls."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse("""
class Counter {
    fn __init__(self, start) {
        self.count = start
    }
    fn inc(self) {
        self.count += 1
        return self.count
    }
}
let c = new Counter(10)
let v = c.inc()
"""))
    assert interp.env.get("v").value == 11, "class method failed"


def test_default_params():
    """Default function parameters work when args are omitted."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('fn greet(name, msg = "Hello") { return msg + " " + name }\nlet r = greet("World")'))
    assert interp.env.get("r").value == "Hello World", f"default params failed: {interp.env.get('r').value}"


def test_compound_assign():
    """Compound assignment operators +=, -= work."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let x = 10\nx += 5\nx *= 2'))
    assert interp.env.get("x").value == 30, f"compound assign failed: {interp.env.get('x').value}"


def test_break_continue():
    """break and continue work in loops."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse("""
let total = 0
let i = 0
while i < 10 {
    i += 1
    if i == 3 { continue }
    if i == 6 { break }
    total += i
}
"""))
    # Adds 1+2+4+5 = 12 (skips 3, stops before 6)
    assert interp.env.get("total").value == 12, f"break/continue: {interp.env.get('total').value}"


def test_not_in():
    """'not in' operator works for lists."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let blocked = ["evil.com"]\nlet ok = "good.com" not in blocked'))
    assert interp.env.get("ok").value is True, "not in failed"


def test_hex_binary_literals():
    """Hex 0xFF and binary 0b1010 parse to correct integers."""
    from interpreter import Interpreter
    from parser import parse
    interp = Interpreter()
    interp.execute(parse('let h = 0xFF\nlet b = 0b1010\nlet o = 0o77'))
    assert interp.env.get("h").value == 255
    assert interp.env.get("b").value == 10
    assert interp.env.get("o").value == 63


# ── Script runner ────────────────────────────────────────────────────────────

def run_kop_file(path: Path, verbose: bool, timeout: int = 20) -> bool:
    """Run a .kop file via the koppa CLI and return True if it exits 0."""
    try:
        result = subprocess.run(
            [sys.executable, str(SRC_DIR / "koppa.py"), "run", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
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
        if verbose:
            print(f"    ! timeout ({timeout}s)")
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
    # v3.0 features
    test_bitwise_ops,
    test_byte_literals,
    test_ternary,
    test_null_coalesce,
    test_list_comprehension,
    test_class_definition,
    test_default_params,
    test_compound_assign,
    test_break_continue,
    test_not_in,
    test_hex_binary_literals,
]

# .kop files that must succeed (no network, no root needed)
SAFE_EXAMPLES = [
    "hello.kop",
    "hash_demo.kop",
    "try_catch_demo.kop",
    "jwt_attack.kop",
    "features_test.kop",
]

# .kop files that require DNS/HTTP (fast, low timeout)
NETWORK_EXAMPLES = [
    "web_check.kop",
    "dns_recon.kop",
    "web_audit.kop",
]

# .kop files that scan local ports (may be slow, need longer timeout)
SCAN_EXAMPLES = [
    "quick_scan.kop",
    "port_scanner.kop",
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
            ok = run_kop_file(path, opts.verbose, timeout=20)
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {fname}")
            if ok:
                passed += 1
            else:
                failed += 1

        for fname in SCAN_EXAMPLES:
            path = EXAMPLES_DIR / fname
            if not path.exists():
                skipped += 1
                continue
            ok = run_kop_file(path, opts.verbose, timeout=60)
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {fname}")
            if ok:
                passed += 1
            else:
                failed += 1
    else:
        skipped += len(NETWORK_EXAMPLES) + len(SCAN_EXAMPLES)

    # ── Summary ─────────────────────────────────────────────────
    total = passed + failed + skipped
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} passed  |  {failed} failed  |  {skipped} skipped")
    print(f"{'='*40}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
