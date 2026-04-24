"""
APOLLO Virtual Machine
Stack-based bytecode execution engine with security primitives
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from apollo_opcodes import OpCode, Instruction, CodeObject
import sys
import socket
import hashlib
import subprocess
import re
from pathlib import Path


@dataclass
class Frame:
    """Execution frame for function calls"""
    __slots__ = ('code', 'locals_', 'globals_', 'stack', 'ip', 'base_pointer')
    code: CodeObject
    locals_: Dict[str, Any] = field(default_factory=dict)
    globals_: Dict[str, Any] = field(default_factory=dict)
    stack: List[Any] = field(default_factory=list)
    ip: int = 0  # Instruction pointer
    base_pointer: int = 0

    def __repr__(self):
        return f"<Frame {self.code.name} ip={self.ip}>"


@dataclass
class VMError(Exception):
    """VM runtime error"""
    message: str
    frame: Optional[Frame] = None
    instruction: Optional[Instruction] = None

    def __str__(self):
        return f"VMError: {self.message}"


class VirtualMachine:
    """
    Stack-based Virtual Machine for APOLLO bytecode

    Architecture:
    - Register-based stack machine
    - Frame-based call handling
    - Global environment for modules
    - Native hooks for security primitives
    """

    def __init__(self):
        self.frames: List[Frame] = []
        self.globals_: Dict[str, Any] = {}
        self.modules: Dict[str, Any] = {}
        self.hooks: Dict[str, Callable] = {}
        self.running = False
        self.result = None

        # Load built-in modules
        self._load_builtins()
        self._init_dispatch()

    def _init_dispatch(self):
        """Pre-bind handlers for faster lookup"""
        self._dispatch = {
            OpCode.HALT: self._halt,
            OpCode.NOP: lambda: None,
            OpCode.PUSH: self.push,
            OpCode.POP: self.pop,
            OpCode.DUP: lambda: self.push(self.peek()),
            OpCode.SWAP: self._swap,
            OpCode.LOAD_CONST: self.load_const,
            OpCode.LOAD_VAR: self.load_var,
            OpCode.STORE_VAR: self.store_var,
            OpCode.LOAD_GLOBAL: self.load_global,
            OpCode.STORE_GLOBAL: self.store_global,
            OpCode.LOAD_FAST: self.load_fast,
            OpCode.STORE_FAST: self.store_fast,
            OpCode.ADD: self._add,
            OpCode.SUB: self._sub,
            OpCode.MUL: self._mul,
            OpCode.DIV: self._div,
            OpCode.MOD: self._mod,
            OpCode.NEG: self._neg,
            OpCode.EQ: self._eq,
            OpCode.NEQ: self._neq,
            OpCode.LT: self._lt,
            OpCode.GT: self._gt,
            OpCode.LTE: self._lte,
            OpCode.GTE: self._gte,
            OpCode.NOT: self._not,
            OpCode.AND: self._and,
            OpCode.OR: self._or,
            OpCode.JUMP: self.jump,
            OpCode.JUMP_IF_FALSE: self._jump_if_false,
            OpCode.JUMP_IF_TRUE: self._jump_if_true,
            OpCode.CALL: self._call,
            OpCode.CALL_METHOD: self._call_method,
            OpCode.RETURN: self._return,
            OpCode.BUILD_LIST: self._build_list,
            OpCode.BUILD_DICT: self._build_dict,
            OpCode.SUBSCR: self._subscr,
            OpCode.LOAD_ATTR: self._load_attr,
            OpCode.PRINT: self._print,
            OpCode.SYSCALL: self._syscall,
            OpCode.NATIVE_CALL: self._native_call,
            OpCode.IMPORT_NAME: self._import_name,
            OpCode.GET_ITER: self._get_iter,
            OpCode.FOR_ITER: self._for_iter,
            OpCode.STORE_SUBSCR: self._store_subscr,
        }

    def _load_builtins(self):
        """Load security primitive modules"""
        self.modules["native_log"] = {
            "info": self._log_info,
            "warn": self._log_warn,
            "error": self._log_error,
            "debug": self._log_debug,
        }
        self.modules["native_scan"] = {
            "tcp": self._scan_tcp,
            "service": self._get_service,
        }
        self.modules["native_recon"] = {
            "whois": self._whois,
            "dns_resolve": self._dns_resolve,
            "dns_reverse": self._dns_reverse,
            "subnet_hosts": self._subnet_hosts,
        }
        self.modules["native_enum"] = {
            "http_directories": lambda u, w: self._exec(f"gobuster dir -u {u} -w {w}"),
            "http_params": self._http_get,
            "smb_shares": lambda h: self._exec(f"nmap --script smb-enum-shares -p 445 {h}"),
            "smb_users": lambda h: self._exec(f"nmap --script smb-enum-users -p 445 {h}"),
            "ldap_users": lambda h: self._exec(f"ldapsearch -H ldap://{h} -x cn"),
            "snmp_walk": lambda h: self._exec(f"snmpwalk -v2c -c public {h}"),
        }
        self.modules["native_crypto"] = {
            "md5": self._hash_md5,
            "sha256": self._hash_sha256,
            "sha512": self._hash_sha512,
            "base64_encode": self._base64_encode,
            "base64_decode": self._base64_decode,
        }
        self.modules["native_http"] = {
            "request": self._http_request,
            "get": self._http_get,
            "post": self._http_post,
        }
        self.modules["native_io"] = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "read_lines": self._read_lines,
            "write_lines": self._write_lines,
            "exec": self._exec,
        }

        # Built-in functions available globally
        self.globals_["len"] = self._builtin_len
        self.globals_["str"] = str
        self.globals_["int"] = int
        self.globals_["float"] = float
        self.globals_["print"] = print
        self.globals_["range"] = self._builtin_range
        self.globals_["type"] = type

    # === Security Primitives ===

    def _interpolate(self, msg: str) -> str:
        """Substitute {expr} patterns using current frame locals/globals"""
        if '{' not in str(msg):
            return str(msg)
        frame = self.current_frame() if self.frames else None
        locals_ = frame.locals_ if frame else {}

        def resolve_name(name: str):
            if name in locals_:
                return locals_[name]
            if name in self.globals_:
                return self.globals_[name]
            return None

        def resolve_idx(key: str):
            """Resolve bracket key: variable lookup or literal int"""
            val = resolve_name(key)
            if val is not None:
                return val
            try:
                return int(key)
            except ValueError:
                return key

        def resolve_expr(expr: str):
            """Resolve simple expressions like var, var.attr, var.attr[key]"""
            try:
                parts = expr.split('.')
                obj = resolve_name(parts[0])
                for part in parts[1:]:
                    # Handle index access like attr[key] or attr[0]
                    idx_match = re.match(r'^(\w+)\[(\w+)\]$', part)
                    if idx_match:
                        attr, idx_key = idx_match.group(1), idx_match.group(2)
                        if isinstance(obj, dict):
                            obj = obj.get(attr)
                        elif hasattr(obj, attr):
                            obj = getattr(obj, attr)
                        idx_val = resolve_idx(idx_key)
                        if isinstance(obj, dict):
                            obj = obj.get(idx_val)
                        elif isinstance(obj, (list, tuple)):
                            try:
                                obj = obj[int(idx_val)]
                            except (IndexError, TypeError):
                                obj = None
                    elif part == 'len':
                        obj = len(obj) if obj is not None else 0
                    elif isinstance(obj, dict):
                        obj = obj.get(part)
                    elif hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        obj = None
                return str(obj) if obj is not None else "None"
            except Exception:
                return expr

        def replacer(m):
            expr = m.group(1)
            return resolve_expr(expr)

        return re.sub(r'\{([\w.\[\]]+)\}', replacer, str(msg))

    def _log_info(self, msg):
        print(f"\033[34m[INFO]\033[0m {self._interpolate(msg)}")
        return None

    def _log_warn(self, msg):
        print(f"\033[33m[WARN]\033[0m {self._interpolate(msg)}")
        return None

    def _log_error(self, msg):
        print(f"\033[31m[ERROR]\033[0m {self._interpolate(msg)}")
        return None

    def _log_debug(self, msg):
        print(f"\033[36m[DEBUG]\033[0m {self._interpolate(msg)}")
        return None

    def _scan_tcp(self, host: str, port: int, timeout: float = 1.0) -> bool:
        """TCP connect scan"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _get_service(self, port: int) -> str:
        """Service detection"""
        services = {
            21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
            53: "dns", 80: "http", 110: "pop3", 143: "imap",
            443: "https", 445: "smb", 3306: "mysql",
            3389: "rdp", 5432: "postgresql", 6379: "redis",
            8080: "http-proxy", 27017: "mongodb"
        }
        return services.get(port, "unknown")

    def _whois(self, domain: str) -> str:
        return self._exec(f"whois {domain}")

    def _dns_resolve(self, hostname: str) -> str:
        try:
            return socket.gethostbyname(hostname)
        except Exception:
            return None

    def _dns_reverse(self, ip: str) -> str:
        try:
            return socket.gethostbyaddr(ip)[0]
        except Exception:
            return None

    def _subnet_hosts(self, cidr: str) -> str:
        return self._exec(f"nmap -sn {cidr}")

    def _hash_md5(self, data: str) -> str:
        return hashlib.md5(data.encode()).hexdigest()

    def _hash_sha256(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _hash_sha512(self, data: str) -> str:
        return hashlib.sha512(data.encode()).hexdigest()

    def _base64_encode(self, data: str) -> str:
        import base64
        return base64.b64encode(data.encode()).decode()

    def _base64_decode(self, data: str) -> str:
        import base64
        return base64.b64decode(data.encode()).decode()

    def _http_get(self, url: str, headers: Dict = None) -> Dict:
        """HTTP GET request"""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response.read().decode('utf-8', errors='ignore')
                }
        except Exception as e:
            return {"error": str(e)}

    def _http_post(self, url: str, data: Dict, headers: Dict = None) -> Dict:
        """HTTP POST request"""
        try:
            import urllib.request
            import urllib.parse
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data, headers=headers or {}, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response.read().decode('utf-8', errors='ignore')
                }
        except Exception as e:
            return {"error": str(e)}

    def _http_request(self, method: str, url: str, headers: Dict = None, data: Dict = None) -> Dict:
        if method == "POST":
            return self._http_post(url, data, headers)
        return self._http_get(url, headers)

    def _read_file(self, path: str) -> str:
        return Path(path).read_text()

    def _read_lines(self, path: str) -> list:
        return Path(path).read_text().splitlines()

    def _write_file(self, path: str, content: str):
        Path(path).write_text(content)
        return None

    def _write_lines(self, path: str, lines: list):
        Path(path).write_text('\n'.join(str(l) for l in lines))
        return None

    def _builtin_len(self, obj) -> int:
        if isinstance(obj, (list, tuple, dict, str)):
            return len(obj)
        return 0

    def _builtin_range(self, *args) -> list:
        return list(range(*args))

    def _exec(self, cmd: str) -> dict:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    # === VM Core ===

    def push_frame(self, frame: Frame):
        self.frames.append(frame)

    def pop_frame(self) -> Frame:
        return self.frames.pop()

    def current_frame(self) -> Frame:
        return self.frames[-1]

    def push(self, value: Any):
        self.current_frame().stack.append(value)

    def pop(self) -> Any:
        return self.current_frame().stack.pop()

    def peek(self, offset: int = 0) -> Any:
        return self.current_frame().stack[-(1 + offset)]

    def _halt(self):
        """Stop execution"""
        self.running = False

    def run(self, code: CodeObject, globals_: Dict = None, script_args: List = None) -> Any:
        """Execute code object, then call main() if defined"""
        frame = Frame(
            code=code,
            locals_={},
            globals_=globals_ or self.globals_,
            stack=[]
        )
        self.push_frame(frame)
        self.running = True

        try:
            self._execute_code(code)

            # Promote module-level locals to globals so functions can access them
            if self.frames:
                module_frame = self.current_frame()
                for k, v in module_frame.locals_.items():
                    self.globals_[k] = v

            # Auto-run main function if defined
            if "main" in self.globals_:
                main_fn = self.globals_["main"]
                if isinstance(main_fn, CodeObject):
                    main_frame = Frame(
                        code=main_fn,
                        locals_={},
                        globals_=self.globals_,
                        stack=[]
                    )
                    # Push script args so STORE_VAR for params can pop them
                    args_list = list(script_args or [])
                    if main_fn.argcount > 0 or self._function_has_params(main_fn):
                        main_frame.stack.append(args_list)
                    self.push_frame(main_frame)
                    self._execute_code(main_fn)
                    if self.frames:
                        self.pop_frame()
        except VMError as e:
            raise e
        finally:
            if self.frames:
                self.pop_frame()
            self.running = False

        return self.result

    def _function_has_params(self, code: CodeObject) -> bool:
        """Check if compiled function starts with STORE_VAR (has params)"""
        if code.instructions:
            return code.instructions[0].opcode == OpCode.STORE_VAR
        return False

    def _execute_code(self, code: CodeObject):
        """Main execution loop - optimized with critical path inlining"""
        frame = self.current_frame()
        frame.ip = 0
        instructions = code.instructions
        instr_len = len(instructions)
        dispatch = self._dispatch
        constants = code.constants
        locals_ = frame.locals_
        globals_ = self.globals_
        modules = self.modules
        stack = frame.stack

        while frame.ip < instr_len:
            instr = instructions[frame.ip]
            op = instr.opcode
            arg = instr.arg if instr.arg is not None else instr.operand

            # Inline critical paths for speed (load/store, arithmetic, return)
            if op == OpCode.LOAD_CONST:
                stack.append(constants[arg])
            elif op == OpCode.LOAD_VAR:
                if arg in locals_:
                    stack.append(locals_[arg])
                elif arg in globals_:
                    stack.append(globals_[arg])
                elif arg in modules:
                    stack.append(modules[arg])
                else:
                    stack.append(None)
            elif op == OpCode.STORE_VAR:
                locals_[arg] = stack.pop()
            elif op == OpCode.ADD:
                b = stack.pop()
                a = stack.pop()
                stack.append(a + b)
            elif op == OpCode.SUB:
                b = stack.pop()
                a = stack.pop()
                stack.append(a - b)
            elif op == OpCode.PUSH:
                stack.append(arg)
            elif op == OpCode.POP:
                stack.pop()
            elif op == OpCode.RETURN:
                if stack:
                    self.result = stack.pop()
                else:
                    self.result = None
                frame.ip = instr_len
                break
            else:
                # Dispatch for less frequent ops
                handler = dispatch.get(op)
                if handler:
                    if arg is not None:
                        handler(arg)
                    else:
                        handler()
                else:
                    raise VMError(f"Unknown opcode: {op}", frame, instr)

            frame.ip += 1

    # === Stack Operations ===

    def _swap(self):
        frame = self.current_frame()
        frame.stack[-1], frame.stack[-2] = frame.stack[-2], frame.stack[-1]

    def load_const(self, index: int):
        code = self.current_frame().code
        self.push(code.constants[index])

    def load_var(self, name: str):
        frame = self.current_frame()
        # Check locals first, then globals, then modules
        if name in frame.locals_:
            self.push(frame.locals_[name])
        elif name in self.globals_:
            self.push(self.globals_[name])
        elif name in self.modules:
            self.push(self.modules[name])
        else:
            self.push(None)

    def store_var(self, name: str):
        frame = self.current_frame()
        value = self.pop()
        frame.locals_[name] = value

    def load_global(self, name: str):
        self.push(self.globals_.get(name, None))

    def store_global(self, name: str):
        self.globals_[name] = self.pop()

    # Map friendly module names → native VM modules
    _MODULE_ALIASES = {
        "log": "native_log",
        "scan": "native_scan",
        "crypto": "native_crypto",
        "io": "native_io",
        "http": "native_http",
        "recon": "native_recon",
        "enum": "native_enum",
    }

    def _import_name(self, name: str):
        """Import a module by friendly name or native name"""
        native_name = self._MODULE_ALIASES.get(name, name)
        if native_name in self.modules:
            self.globals_[name] = self.modules[native_name]
        elif name in self.modules:
            self.globals_[name] = self.modules[name]
        else:
            self.globals_[name] = {}

    def load_fast(self, index: int):
        frame = self.current_frame()
        names = list(frame.locals_.keys())
        self.push(frame.locals_[names[index]])

    def store_fast(self, index: int):
        frame = self.current_frame()
        names = list(frame.locals_.keys())
        frame.locals_[names[index]] = self.pop()

    # === Arithmetic ===

    def _add(self):
        b, a = self.pop(), self.pop()
        self.push(a + b)

    def _sub(self):
        b, a = self.pop(), self.pop()
        self.push(a - b)

    def _mul(self):
        b, a = self.pop(), self.pop()
        self.push(a * b)

    def _div(self):
        b, a = self.pop(), self.pop()
        self.push(a / b)

    def _mod(self):
        b, a = self.pop(), self.pop()
        self.push(a % b)

    def _neg(self):
        self.push(-self.pop())

    # === Comparison ===

    def _eq(self):
        b, a = self.pop(), self.pop()
        self.push(a == b)

    def _neq(self):
        b, a = self.pop(), self.pop()
        self.push(a != b)

    def _lt(self):
        b, a = self.pop(), self.pop()
        self.push(a < b)

    def _gt(self):
        b, a = self.pop(), self.pop()
        self.push(a > b)

    def _lte(self):
        b, a = self.pop(), self.pop()
        self.push(a <= b)

    def _gte(self):
        b, a = self.pop(), self.pop()
        self.push(a >= b)

    # === Logic ===

    def _not(self):
        self.push(not self.pop())

    def _and(self):
        b, a = self.pop(), self.pop()
        self.push(a and b)

    def _or(self):
        b, a = self.pop(), self.pop()
        self.push(a or b)

    # === Control Flow ===

    def jump(self, target: int):
        # -1 because _execute_code adds +1 after every instruction
        self.current_frame().ip = target - 1

    def _jump_if_false(self, arg: int):
        if not self.pop():
            self.current_frame().ip = arg - 1

    def _jump_if_true(self, arg: int):
        if self.pop():
            self.current_frame().ip = arg - 1

    # === Functions ===

    def _call(self, arg: int):
        """Call function with arg count"""
        frame = self.current_frame()
        func = frame.stack[-(arg + 1)]
        # Args are on stack top-to-bottom as: argN, ..., arg1, arg0, func
        # We want [arg0, arg1, ..., argN] so reverse
        args = [frame.stack[-(i + 1)] for i in range(arg)][::-1]

        # Pop function and args
        for _ in range(arg + 1):
            self.pop()

        if callable(func):
            result = func(*args)
            self.push(result)
        elif isinstance(func, CodeObject):
            self._call_function(func, args)
        elif hasattr(func, 'code'):
            self._call_function(func.code, args)
        else:
            raise VMError(f"Cannot call {func}")

    def _list_method(self, lst: list, name: str, args: list):
        """Handle APOLLO list/array methods"""
        if name in ("push", "append"):
            lst.append(args[0])
            return None
        if name == "pop":
            return lst.pop() if lst else None
        if name in ("len", "length", "size"):
            return len(lst)
        if name == "contains":
            return args[0] in lst
        if name == "join":
            sep = args[0] if args else ""
            return sep.join(str(x) for x in lst)
        if name == "reverse":
            lst.reverse()
            return None
        if name == "sort":
            lst.sort()
            return None
        if name == "map":
            fn = args[0]
            return [fn(x) for x in lst] if callable(fn) else lst
        if name == "filter":
            fn = args[0]
            return [x for x in lst if fn(x)] if callable(fn) else lst
        if name in ("where", "find"):
            fn = args[0]
            return [x for x in lst if fn(x)] if callable(fn) else lst
        if name == "first":
            return lst[0] if lst else None
        if name == "last":
            return lst[-1] if lst else None
        if name == "slice":
            start = args[0] if args else 0
            end = args[1] if len(args) > 1 else len(lst)
            return lst[start:end]
        if name == "flat_map":
            fn = args[0]
            result = []
            for x in lst:
                val = fn(x) if callable(fn) else x
                if isinstance(val, list):
                    result.extend(val)
                else:
                    result.append(val)
            return result
        raise VMError(f"Unknown list method: {name}")

    def _string_method(self, s: str, name: str, args: list):
        """Handle APOLLO string methods"""
        if name in ("len", "length"):
            return len(s)
        if name == "contains":
            return args[0] in s
        if name == "starts_with":
            return s.startswith(args[0])
        if name == "ends_with":
            return s.endswith(args[0])
        if name == "to_upper":
            return s.upper()
        if name == "to_lower":
            return s.lower()
        if name == "trim":
            return s.strip()
        if name == "split":
            return s.split(args[0]) if args else s.split()
        if name == "replace":
            return s.replace(args[0], args[1]) if len(args) >= 2 else s
        if name == "to_int":
            return int(s)
        if name == "to_float":
            return float(s)
        if name == "is_empty":
            return len(s) == 0
        raise VMError(f"Unknown string method: {name}")

    def _dict_method(self, d: dict, name: str, args: list):
        """Handle APOLLO dict/object methods"""
        if name in ("len", "size"):
            return len(d)
        if name == "keys":
            return list(d.keys())
        if name == "values":
            return list(d.values())
        if name == "has":
            return args[0] in d
        if name == "get":
            return d.get(args[0], args[1] if len(args) > 1 else None)
        if name == "set":
            d[args[0]] = args[1]
            return None
        if name == "remove":
            return d.pop(args[0], None)
        raise VMError(f"Unknown dict method: {name}")

    def _call_method(self, arg: int):
        """Call method (name on stack)"""
        frame = self.current_frame()

        # Stack layout: [obj, arg1, arg2, ..., method_name]
        # arg includes method_name, so actual args = arg - 1
        method_name = self.pop()
        args = [self.pop() for _ in range(arg - 1)][::-1]
        obj = self.pop()

        if isinstance(obj, dict) and method_name in obj:
            method = obj[method_name]
            if callable(method):
                result = method(*args)
                self.push(result)
            else:
                self.push(method)
        elif isinstance(obj, list):
            result = self._list_method(obj, method_name, args)
            self.push(result)
        elif isinstance(obj, str):
            result = self._string_method(obj, method_name, args)
            self.push(result)
        elif isinstance(obj, dict):
            result = self._dict_method(obj, method_name, args)
            self.push(result)
        elif hasattr(obj, method_name):
            method = getattr(obj, method_name)
            if callable(method):
                result = method(*args)
                self.push(result)
            else:
                self.push(method)
        else:
            raise VMError(f"Unknown method: {method_name} on {type(obj).__name__}")

    def _call_function(self, func, args: list):
        """Call compiled function"""
        frame = self.current_frame()
        code = func.code if hasattr(func, 'code') else func
        new_frame = Frame(
            code=code,
            locals_={},
            globals_=frame.globals_,
            stack=[]
        )

        # Push args onto the new frame's stack in reverse so first param is popped first
        for arg in reversed(args):
            new_frame.stack.append(arg)

        self.push_frame(new_frame)
        self._execute_code(code)
        self.pop_frame()

        # Push return value
        self.push(self.result)

    def _return(self):
        """Return from function — set result and signal loop exit (don't pop frame)"""
        frame = self.current_frame()
        if frame.stack:
            self.result = self.pop()
        else:
            self.result = None
        # Force the _execute_code while-loop to exit; _call_function will pop the frame
        frame.ip = len(frame.code.instructions) - 1

    # === Data Structures ===

    def _build_list(self, arg: int):
        """Build list from top N stack values"""
        items = [self.pop() for _ in range(arg)][::-1]
        self.push(items)

    def _build_dict(self, arg: int):
        """Build dict from key-value pairs"""
        items = {}
        for _ in range(arg):
            value = self.pop()
            key = self.pop()
            items[key] = value
        self.push(items)

    def _subscr(self):
        """Subscript access"""
        index = self.pop()
        container = self.pop()
        if isinstance(container, (list, tuple)):
            self.push(container[index])
        elif isinstance(container, dict):
            self.push(container[index])
        else:
            raise VMError(f"Cannot subscript {container}")

    def _load_attr(self):
        """Load attribute"""
        name = self.pop()
        obj = self.pop()
        if isinstance(obj, dict) and name in obj:
            self.push(obj[name])
        elif isinstance(obj, (list, str, tuple)) and name == "len":
            self.push(len(obj))
        elif isinstance(obj, dict) and name == "len":
            self.push(len(obj))
        elif hasattr(obj, name):
            self.push(getattr(obj, name))
        else:
            raise VMError(f"Unknown attribute '{name}' on {type(obj).__name__}")

    def _store_subscr(self):
        """Store subscript: stack = value, container, index"""
        index = self.pop()
        container = self.pop()
        value = self.pop()
        if isinstance(container, list):
            container[index] = value
        elif isinstance(container, dict):
            container[index] = value
        else:
            raise VMError(f"Cannot subscript-assign to {type(container).__name__}")

    def _get_iter(self):
        """Convert top of stack to Python iterator"""
        obj = self.pop()
        if isinstance(obj, (list, tuple, range, str)):
            self.push(iter(obj))
        elif hasattr(obj, '__iter__'):
            self.push(iter(obj))
        else:
            raise VMError(f"Object of type {type(obj).__name__} is not iterable")

    def _for_iter(self, target: int):
        """Advance iterator: push next value, or jump to target and pop iterator"""
        iterator = self.peek()
        try:
            value = next(iterator)
            self.push(value)
        except StopIteration:
            self.pop()  # Remove exhausted iterator
            # Jump to target (-1 compensates for loop's +1)
            self.current_frame().ip = target - 1

    # === Special ===

    def _print(self):
        print(self.pop())

    def _syscall(self):
        """System call via native hook"""
        cmd = self.pop()
        result = self._exec(cmd)
        self.push(result)

    def _native_call(self):
        """Call native/built-in function"""
        module = self.pop()
        func_name = self.pop()
        arg_count = self.peek()

        if module in self.modules:
            func = self.modules[module].get(func_name)
            if func:
                args = [self.pop() for _ in range(arg_count)][::-1]
                result = func(*args)
                self.push(result)
            else:
                raise VMError(f"Unknown function: {func_name}")
        else:
            raise VMError(f"Unknown module: {module}")

    # === Debugging ===

    def get_stack_trace(self) -> list:
        """Get current call stack"""
        return [f.code.name for f in self.frames]

    def dump_frame(self, frame: Frame) -> dict:
        """Dump frame state for debugging"""
        return {
            "code": frame.code.name,
            "ip": frame.ip,
            "locals": frame.locals_,
            "stack": frame.stack.copy(),
        }


class VMCompiler:
    """Compile AST to VM bytecode"""

    def __init__(self):
        self.code_objects = {}

    def compile(self, ast_node, name="<module>") -> CodeObject:
        """Compile AST node to bytecode"""
        from parser import ASTNodeType

        builder = OpcodeBuilder()
        self._compile_node(ast_node, builder)
        builder.add(OpCode.HALT)
        return builder.build(name)

    def _compile_node(self, node, builder):
        """Compile single AST node"""
        from parser import ASTNodeType

        if node.node_type == ASTNodeType.MODULE:
            for child in node.children:
                self._compile_node(child, builder)

        elif node.node_type == ASTNodeType.VARIABLE:
            self._compile_node(node.children[0], builder)
            builder.add(OpCode.STORE_VAR, node.value)

        elif node.node_type == ASTNodeType.LITERAL:
            idx = builder.const_index(node.value)
            builder.add(OpCode.LOAD_CONST, idx)

        elif node.node_type == ASTNodeType.IDENTIFIER:
            builder.add(OpCode.LOAD_VAR, node.value)

        elif node.node_type == ASTNodeType.BINARY_OP:
            self._compile_node(node.children[0], builder)
            self._compile_node(node.children[1], builder)
            op_map = {
                "+": OpCode.ADD, "-": OpCode.SUB,
                "*": OpCode.MUL, "/": OpCode.DIV,
                "%": OpCode.MOD, "==": OpCode.EQ,
                "!=": OpCode.NEQ, "<": OpCode.LT,
                ">": OpCode.GT, "<=": OpCode.LTE,
                ">=": OpCode.GTE, "&&": OpCode.AND,
                "||": OpCode.OR,
            }
            op = op_map.get(node.value, OpCode.ADD)
            builder.add(op)

        elif node.node_type == ASTNodeType.CALL:
            # Compile function
            self._compile_node(node.children[0], builder)
            # Compile args
            for arg in node.children[1:]:
                self._compile_node(arg, builder)
            builder.add(OpCode.CALL, len(node.children) - 1)

        elif node.node_type == ASTNodeType.IF:
            # Condition
            self._compile_node(node.value, builder)
            builder.jump_if_false("else")
            # Then block
            self._compile_node(node.children[0], builder)
            builder.jump("end")
            builder.label("else")
            # Else block
            if node.meta.get("else"):
                self._compile_node(node.meta["else"], builder)
            builder.label("end")

        elif node.node_type == ASTNodeType.FOR:
            builder.label("loop_start")
            # Loop body
            for stmt in node.children[1].children:
                self._compile_node(stmt, builder)
            builder.jump("loop_start")

        elif node.node_type == ASTNodeType.FUNCTION:
            # Compile function body
            func_code = self.compile(node.meta["body"], node.value)
            self.code_objects[node.value] = func_code
            # Store function
            builder.add(OpCode.LOAD_CONST, builder.const_index(func_code))
            builder.add(OpCode.STORE_GLOBAL, node.value)

        elif node.node_type == ASTNodeType.RETURN:
            if node.value:
                self._compile_node(node.value, builder)
            builder.add(OpCode.RETURN)

        elif node.node_type == ASTNodeType.BLOCK:
            for child in node.children:
                self._compile_node(child, builder)

        elif node.node_type == ASTNodeType.EXPRESSION_STMT:
            self._compile_node(node.children[0], builder)
            builder.add(OpCode.POP)  # Discard result

        elif node.node_type == ASTNodeType.MEMBER_ACCESS:
            self._compile_node(node.children[0], builder)
            idx = builder.const_index(node.value)
            builder.add(OpCode.LOAD_CONST, idx)
            builder.add(OpCode.LOAD_ATTR)

        elif node.node_type == ASTNodeType.IMPORT:
            for mod in node.value:
                if mod in ["log", "scan", "crypto", "io"]:
                    idx = builder.const_index(mod)
                    builder.add(OpCode.LOAD_CONST, idx)
                    builder.add(OpCode.STORE_GLOBAL, mod)
