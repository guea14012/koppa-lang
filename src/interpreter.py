"""
KOPPA Language Interpreter
Executes KOPPA AST with security primitives
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum, auto
import subprocess
import socket
import re
import json
import hashlib
import threading
import concurrent.futures
from pathlib import Path

from parser import ASTNode, ASTNodeType, parse


class KoppaBytes:
    """KOPPA bytes type — immutable byte sequence with security helpers"""
    def __init__(self, data):
        if isinstance(data, KoppaBytes):
            self.data = data.data
        elif isinstance(data, (bytes, bytearray)):
            self.data = bytes(data)
        elif isinstance(data, str):
            self.data = _parse_byte_escapes(data)
        else:
            self.data = bytes(data)

    def __repr__(self):    return f'b"{self.data.hex()}"'
    def __len__(self):     return len(self.data)
    def __add__(self, o):  return KoppaBytes(self.data + (o.data if isinstance(o, KoppaBytes) else bytes(o)))
    def __eq__(self, o):   return self.data == (o.data if isinstance(o, KoppaBytes) else o)

    def hex(self):
        return self.data.hex()

    def b64(self):
        import base64
        return base64.b64encode(self.data).decode()

    def xor(self, key):
        if isinstance(key, int):
            return KoppaBytes(bytes(b ^ key for b in self.data))
        k = key.data if isinstance(key, KoppaBytes) else bytes(key)
        if not k:
            return KoppaBytes(self.data)
        return KoppaBytes(bytes(self.data[i] ^ k[i % len(k)] for i in range(len(self.data))))

    def to_str(self):
        return self.data.decode('latin-1')

    def split_at(self, sep):
        parts = self.data.split(bytes([sep]) if isinstance(sep, int) else sep)
        return [KoppaBytes(p) for p in parts]

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            return KoppaBytes(self.data[idx])
        return self.data[idx]


def _parse_byte_escapes(s: str) -> bytes:
    """Convert escape sequences in a byte string literal to actual bytes"""
    result = bytearray()
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            esc = s[i + 1]
            if esc == 'x' and i + 3 < len(s):
                result.append(int(s[i+2:i+4], 16))
                i += 4
            elif esc == 'n':  result.append(10);  i += 2
            elif esc == 't':  result.append(9);   i += 2
            elif esc == 'r':  result.append(13);  i += 2
            elif esc == '0':  result.append(0);   i += 2
            elif esc == '\\': result.append(92);  i += 2
            else:
                result.append(ord(esc)); i += 2
        else:
            result.append(ord(s[i])); i += 1
    return bytes(result)


class RuntimeValue:
    """Base runtime value type"""
    def __init__(self, value: Any, value_type: str = "any"):
        self.value = value
        self.value_type = value_type

    def __repr__(self):
        return f"RuntimeValue({self.value!r}, {self.value_type})"


class RTTI(Enum):
    """Runtime Type Information"""
    NULL = auto()
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    ARRAY = auto()
    DICT = auto()
    FUNCTION = auto()
    ASYNC_FUNCTION = auto()
    MODULE = auto()
    RESULT = auto()
    STREAM = auto()
    SOCKET = auto()
    HTTP_REQUEST = auto()
    HTTP_RESPONSE = auto()
    FUTURE = auto()


@dataclass
class Environment:
    """Lexical environment for variable scope"""
    variables: Dict[str, RuntimeValue] = field(default_factory=dict)
    parent: Optional['Environment'] = None
    modules: Dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> RuntimeValue:
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable: {name}")

    def set(self, name: str, value: RuntimeValue, mutable: bool = True):
        self.variables[name] = value

    def define(self, name: str, value: RuntimeValue):
        self.variables[name] = value


class InterpreterError(Exception):
    """Runtime error"""
    pass


class ReturnException(Exception):
    """Used to propagate return values up the call stack"""
    def __init__(self, value: 'RuntimeValue'):
        self.value = value


class BreakException(Exception):
    """Signals a break statement inside a loop"""


class ContinueException(Exception):
    """Signals a continue statement inside a loop"""


def _rv_to_display(val) -> str:
    """Convert a RuntimeValue (or plain value) to a human-readable string"""
    if isinstance(val, RuntimeValue):
        val = val.value
    if val is None:
        return "None"
    if isinstance(val, list):
        inner = ", ".join(_rv_to_display(x) for x in val)
        return f"[{inner}]"
    if isinstance(val, dict):
        # skip internal keys
        pairs = []
        for k, v in val.items():
            if not str(k).startswith("__"):
                pairs.append(f"{k}: {_rv_to_display(v)}")
        return "{" + ", ".join(pairs) + "}"
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _interpolate_string(s: str, env: 'Environment') -> str:
    """Replace {expr} patterns in strings with live env values.
    Supports: {var}, {obj.field}, {obj.method()}, {fn('arg')}, {fn(var)}
    """
    if '{' not in s:
        return s

    def resolve_part(val, part):
        """Resolve one member access step"""
        if isinstance(val, RuntimeValue):
            val = val.value
        # KoppaBytes properties
        if isinstance(val, KoppaBytes):
            if part == "len":    return len(val)
            if part == "hex":    return val.hex()
            if part == "b64":    return val.b64()
            if part == "to_str": return val.to_str()
            return None
        if part == "len":
            return len(val) if isinstance(val, (list, dict, str)) else None
        if isinstance(val, dict):
            return val.get(part)
        if isinstance(val, list):
            if part in ("length", "size"):
                return len(val)
        if hasattr(val, part):
            attr = getattr(val, part)
            if callable(attr) and not isinstance(attr, (RuntimeValue,)):
                try:
                    return attr()
                except Exception:
                    pass
            return attr
        return None

    def replace_ref(m):
        expr = m.group(1).strip()
        interp = _get_interp_for_env(env)
        if not interp:
            return m.group(0)

        # Try to parse and execute the expression via the interpreter
        try:
            from parser import parse as koppa_parse, Parser
            from lexer import tokenize as koppa_tokenize
            tokens = koppa_tokenize(expr)
            p = Parser(tokens)
            ast_expr = p.parse_expression()
            old_env = interp.env
            interp.env = env
            try:
                result = interp.execute(ast_expr)
            finally:
                interp.env = old_env
            return _rv_to_display(result)
        except Exception:
            pass

        # Fallback: simple dotted-path resolution
        try:
            parts = expr.split('.')
            val = env.get(parts[0])
            for part in parts[1:]:
                val = resolve_part(val, part)
            return _rv_to_display(val)
        except Exception:
            return m.group(0)

    # Match {anything except newline} — greedy but non-nested
    result = re.sub(r'\{([^{}\n]+)\}', replace_ref, s)
    return result


# Global registry to allow interpolation to call methods
_interp_registry: List['Interpreter'] = []


def _get_interp_for_env(env: 'Environment') -> Optional['Interpreter']:
    """Return the most recent interpreter that can be used for string interpolation"""
    if _interp_registry:
        return _interp_registry[-1]
    return None


class SecurityPrimitive:
    """Base class for security primitives"""

    @staticmethod
    def scan_tcp(host: str, port: int, timeout: float = 1.0) -> RuntimeValue:
        """Perform TCP connect scan"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return RuntimeValue(result == 0, "bool")
        except Exception as e:
            return RuntimeValue(False, "bool")

    @staticmethod
    def scan_syn(host: str, port: int) -> RuntimeValue:
        """SYN scan (requires privileges)"""
        # Requires raw sockets - fallback to TCP connect
        return SecurityPrimitive.scan_tcp(host, port)

    @staticmethod
    def get_service(port: int) -> RuntimeValue:
        """Attempt service detection"""
        services = {
            21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
            53: "dns", 80: "http", 110: "pop3", 143: "imap",
            443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
            3306: "mysql", 3389: "rdp", 5432: "postgresql",
            6379: "redis", 8080: "http-proxy", 27017: "mongodb"
        }
        return RuntimeValue(services.get(port, "unknown"), "string")

    @staticmethod
    def http_get(url: str, headers: Dict = None) -> RuntimeValue:
        """HTTP GET request"""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=10) as response:
                return RuntimeValue({
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response.read().decode('utf-8', errors='ignore')
                }, "http_response")
        except Exception as e:
            return RuntimeValue({"error": str(e)}, "http_response")

    @staticmethod
    def http_post(url: str, data: Dict, headers: Dict = None) -> RuntimeValue:
        """HTTP POST request"""
        try:
            import urllib.request
            import urllib.parse
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data, headers=headers or {}, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                return RuntimeValue({
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response.read().decode('utf-8', errors='ignore')
                }, "http_response")
        except Exception as e:
            return RuntimeValue({"error": str(e)}, "http_response")

    @staticmethod
    def dns_resolve(hostname: str) -> RuntimeValue:
        """DNS resolution"""
        try:
            return RuntimeValue(socket.gethostbyname(hostname), "string")
        except Exception:
            return RuntimeValue(None, "null")

    @staticmethod
    def dns_reverse(ip: str) -> RuntimeValue:
        """Reverse DNS lookup"""
        try:
            return RuntimeValue(socket.gethostbyaddr(ip)[0], "string")
        except Exception:
            return RuntimeValue(None, "null")

    @staticmethod
    def hash_md5(data: str) -> RuntimeValue:
        """MD5 hash"""
        return RuntimeValue(hashlib.md5(data.encode()).hexdigest(), "string")

    @staticmethod
    def hash_sha256(data: str) -> RuntimeValue:
        """SHA-256 hash"""
        return RuntimeValue(hashlib.sha256(data.encode()).hexdigest(), "string")

    @staticmethod
    def hash_sha512(data: str) -> RuntimeValue:
        """SHA-512 hash"""
        return RuntimeValue(hashlib.sha512(data.encode()).hexdigest(), "string")

    @staticmethod
    def hash_ntlm(password: str) -> RuntimeValue:
        """NTLM hash (simplified - real implementation would need impacket)"""
        return RuntimeValue(hashlib.md5(password.encode('utf-16le')).hexdigest(), "string")

    @staticmethod
    def encode_base64(data: str) -> RuntimeValue:
        """Base64 encode"""
        import base64
        return RuntimeValue(base64.b64encode(data.encode()).decode(), "string")

    @staticmethod
    def decode_base64(data: str) -> RuntimeValue:
        """Base64 decode"""
        import base64
        return RuntimeValue(base64.b64decode(data.encode()).decode(), "string")

    @staticmethod
    def exec_command(cmd: str, shell: bool = True) -> RuntimeValue:
        """Execute system command"""
        try:
            result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=30)
            return RuntimeValue({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }, "exec_result")
        except Exception as e:
            return RuntimeValue({"error": str(e)}, "exec_result")

    @staticmethod
    def read_file(path: str) -> RuntimeValue:
        """Read file contents"""
        try:
            return RuntimeValue(Path(path).read_text(), "string")
        except Exception as e:
            return RuntimeValue({"error": str(e)}, "null")

    @staticmethod
    def write_file(path: str, content: str) -> RuntimeValue:
        """Write file contents"""
        try:
            Path(path).write_text(content)
            return RuntimeValue(True, "bool")
        except Exception as e:
            return RuntimeValue({"error": str(e)}, "null")

    @staticmethod
    def log_info(msg: str) -> RuntimeValue:
        """Log info message"""
        print(f"\033[34m[INFO]\033[0m {msg}")
        return RuntimeValue(None, "null")

    @staticmethod
    def log_warn(msg: str) -> RuntimeValue:
        """Log warning message"""
        print(f"\033[33m[WARN]\033[0m {msg}")
        return RuntimeValue(None, "null")

    @staticmethod
    def log_error(msg: str) -> RuntimeValue:
        """Log error message"""
        print(f"\033[31m[ERROR]\033[0m {msg}")
        return RuntimeValue(None, "null")

    @staticmethod
    def log_debug(msg: str) -> RuntimeValue:
        """Log debug message"""
        print(f"\033[36m[DEBUG]\033[0m {msg}")
        return RuntimeValue(None, "null")


class SecurityModule:
    """Built-in security modules"""

    @staticmethod
    def recon_module() -> Dict[str, Callable]:
        """Reconnaissance primitives"""
        return {
            "whois": lambda x: SecurityPrimitive.exec_command(f"whois {x}"),
            "dns_resolve": SecurityPrimitive.dns_resolve,
            "dns_reverse": SecurityPrimitive.dns_reverse,
            "subnet_hosts": lambda cidr: SecurityPrimitive.exec_command(f"nmap -sn {cidr}"),
        }

    @staticmethod
    def scan_module() -> Dict[str, Callable]:
        """Scanning primitives"""
        return {
            "tcp": SecurityPrimitive.scan_tcp,
            "syn": SecurityPrimitive.scan_syn,
            "udp": lambda h, p: SecurityPrimitive.exec_command(f"nmap -sU -p {p} {h}"),
            "service": SecurityPrimitive.get_service,
        }

    @staticmethod
    def enum_module() -> Dict[str, Callable]:
        """Enumeration primitives"""
        return {
            "http_directories": lambda u, w: SecurityPrimitive.exec_command(f"gobuster dir -u {u} -w {w}"),
            "http_params": lambda u: SecurityPrimitive.http_get(u),
            "smb_shares": lambda h: SecurityPrimitive.exec_command(f"nmap --script smb-enum-shares -p 445 {h}"),
            "smb_users": lambda h: SecurityPrimitive.exec_command(f"nmap --script smb-enum-users -p 445 {h}"),
            "ldap_users": lambda h: SecurityPrimitive.exec_command(f"ldapsearch -H ldap://{h} -x cn"),
            "snmp_walk": lambda h: SecurityPrimitive.exec_command(f"snmpwalk -v2c -c public {h}"),
        }

    @staticmethod
    def exploit_module() -> Dict[str, Callable]:
        """Exploitation primitives (stubs - real implementations would be dangerous)"""
        return {
            "payload_generate": lambda t, o: RuntimeValue({"type": t, "options": o}, "payload"),
            "handler_start": lambda o: RuntimeValue({"handler": "started", "options": o}, "handler"),
            "session_interact": lambda id: RuntimeValue({"session": id}, "session"),
        }

    @staticmethod
    def crypto_module() -> Dict[str, Callable]:
        """Cryptographic primitives"""
        return {
            "hash_md5": SecurityPrimitive.hash_md5,
            "hash_sha256": SecurityPrimitive.hash_sha256,
            "hash_sha512": SecurityPrimitive.hash_sha512,
            "hash_ntlm": SecurityPrimitive.hash_ntlm,
            "encode_base64": SecurityPrimitive.encode_base64,
            "decode_base64": SecurityPrimitive.decode_base64,
        }

    @staticmethod
    def http_module() -> Dict[str, Callable]:
        """HTTP primitives"""
        return {
            "request": lambda m, u, h={}, d=None: SecurityPrimitive.http_post(u, d, h) if m == "POST" else SecurityPrimitive.http_get(u, h),
            "get": SecurityPrimitive.http_get,
            "post": SecurityPrimitive.http_post,
        }

    @staticmethod
    def io_module() -> Dict[str, Callable]:
        """I/O primitives"""
        return {
            "read_file": SecurityPrimitive.read_file,
            "write_file": SecurityPrimitive.write_file,
            "exec": SecurityPrimitive.exec_command,
        }

    @staticmethod
    def log_module() -> Dict[str, Callable]:
        """Logging primitives"""
        return {
            "info": SecurityPrimitive.log_info,
            "warn": SecurityPrimitive.log_warn,
            "error": SecurityPrimitive.log_error,
            "debug": SecurityPrimitive.log_debug,
            "success": lambda msg: print(f"\033[32m[SUCCESS]\033[0m {msg}") or RuntimeValue(None, "null"),
        }


class Interpreter:
    """KOPPA language interpreter"""

    def __init__(self):
        self.env = Environment()
        self.load_builtins()
        _interp_registry.append(self)

    def load_builtins(self):
        """Load built-in modules"""
        # Legacy security modules
        self.env.modules["native_recon"] = SecurityModule.recon_module()
        self.env.modules["native_scan"] = SecurityModule.scan_module()
        self.env.modules["native_enum"] = SecurityModule.enum_module()
        self.env.modules["native_exploit"] = SecurityModule.exploit_module()
        self.env.modules["native_crypto"] = SecurityModule.crypto_module()
        self.env.modules["native_http"] = SecurityModule.http_module()
        self.env.modules["native_io"] = SecurityModule.io_module()
        self.env.modules["native_io"]["file_exists"] = lambda p: RuntimeValue(Path(p).exists(), "bool")
        self.env.modules["native_io"]["read_lines"] = lambda p: RuntimeValue([RuntimeValue(l, "string") for l in Path(p).read_text().splitlines()], "array")
        self.env.modules["native_io"]["write_json"] = lambda data, p: Path(p).write_text(__import__('json').dumps(data if not isinstance(data, RuntimeValue) else data.value, indent=2, default=str)) or RuntimeValue(None, "null")
        self.env.modules["native_log"] = SecurityModule.log_module()

        # Load full stdlib
        try:
            from stdlib_native import ALL_MODULES
            for name, factory in ALL_MODULES.items():
                self.env.modules[name] = factory()
        except ImportError:
            pass

        # Built-in functions
        self.env.variables["print"] = RuntimeValue(lambda *args: print(*[a if not isinstance(a, RuntimeValue) else a.value for a in args]) or None, "function")
        self.env.variables["str"]   = RuntimeValue(lambda x: RuntimeValue(str(x.value if isinstance(x, RuntimeValue) else x), "string"), "function")
        self.env.variables["int"]   = RuntimeValue(lambda x: RuntimeValue(int(x.value if isinstance(x, RuntimeValue) else x), "integer"), "function")
        self.env.variables["float"] = RuntimeValue(lambda x: RuntimeValue(float(x.value if isinstance(x, RuntimeValue) else x), "float"), "function")
        self.env.variables["bool"]  = RuntimeValue(lambda x: RuntimeValue(bool(x.value if isinstance(x, RuntimeValue) else x), "bool"), "function")
        self.env.variables["len"]   = RuntimeValue(lambda x: RuntimeValue(len(x.value if isinstance(x, RuntimeValue) else x), "int"), "function")
        self.env.variables["type"]  = RuntimeValue(lambda x: RuntimeValue(x.value_type if isinstance(x, RuntimeValue) else type(x).__name__, "string"), "function")
        self.env.variables["range"] = RuntimeValue(lambda *args: RuntimeValue([RuntimeValue(i, "integer") for i in range(*[a.value if isinstance(a, RuntimeValue) else a for a in args])], "array"), "function")
        self.env.variables["input"] = RuntimeValue(lambda prompt="": RuntimeValue(input(prompt.value if isinstance(prompt, RuntimeValue) else prompt), "string"), "function")
        self.env.variables["abs"]   = RuntimeValue(lambda x: RuntimeValue(abs(x.value if isinstance(x, RuntimeValue) else x), "number"), "function")
        self.env.variables["round"] = RuntimeValue(lambda x, n=RuntimeValue(0,'int'): RuntimeValue(round(x.value if isinstance(x, RuntimeValue) else x, n.value if isinstance(n, RuntimeValue) else n), "number"), "function")
        self.env.variables["min"]   = RuntimeValue(lambda *args: min(args, key=lambda a: a.value if isinstance(a, RuntimeValue) else a), "function")
        self.env.variables["max"]   = RuntimeValue(lambda *args: max(args, key=lambda a: a.value if isinstance(a, RuntimeValue) else a), "function")

    def execute(self, node: ASTNode) -> RuntimeValue:
        """Execute an AST node"""
        if node.node_type == ASTNodeType.MODULE:
            return self.execute_module(node)

        if node.node_type == ASTNodeType.IMPORT:
            return self.execute_import(node)

        if node.node_type == ASTNodeType.EXPORT:
            return self.execute_export(node)

        if node.node_type == ASTNodeType.FUNCTION:
            return self.execute_function(node)

        if node.node_type == ASTNodeType.VARIABLE:
            return self.execute_variable(node)

        if node.node_type == ASTNodeType.IF:
            return self.execute_if(node)

        if node.node_type == ASTNodeType.MATCH:
            return self.execute_match(node)

        if node.node_type == ASTNodeType.FOR:
            return self.execute_for(node)

        if node.node_type == ASTNodeType.WHILE:
            return self.execute_while(node)

        if node.node_type == ASTNodeType.RETURN:
            return self.execute_return(node)

        if node.node_type == ASTNodeType.BLOCK:
            return self.execute_block(node)

        if node.node_type == ASTNodeType.EXPRESSION_STMT:
            return self.execute(node.children[0])

        if node.node_type == ASTNodeType.IDENTIFIER:
            return self.execute_identifier(node)

        if node.node_type == ASTNodeType.MEMBER_ACCESS:
            return self.execute_member_access(node)

        if node.node_type == ASTNodeType.LITERAL:
            val = node.value
            if node.meta.get("type") == "bytes":
                return RuntimeValue(KoppaBytes(val), "bytes")
            if isinstance(val, str):
                val = _interpolate_string(val, self.env)
            return RuntimeValue(val, node.meta.get("type", "any"))

        if node.node_type == ASTNodeType.CALL:
            return self.execute_call(node)

        if node.node_type == ASTNodeType.PIPELINE:
            return self.execute_pipeline(node)

        if node.node_type == ASTNodeType.BINARY_OP:
            return self.execute_binary_op(node)

        if node.node_type == ASTNodeType.UNARY_OP:
            return self.execute_unary_op(node)

        if node.node_type == ASTNodeType.ARRAY:
            return self.execute_array(node)

        if node.node_type == ASTNodeType.INDEX:
            arr = self.execute(node.children[0])
            idx = self.execute(node.value)
            if isinstance(arr.value, list) and isinstance(idx.value, int):
                item = arr.value[idx.value]
                if not isinstance(item, RuntimeValue):
                    item = RuntimeValue(item, "any")
                return item
            if isinstance(arr.value, dict):
                key = idx.value
                val = arr.value.get(key)
                if val is None:
                    return RuntimeValue(None, "null")
                return val if isinstance(val, RuntimeValue) else RuntimeValue(val, "any")
            raise InterpreterError(f"Invalid index: {idx} on {arr}")

        if node.node_type == ASTNodeType.DICT:
            return self.execute_dict(node)

        if node.node_type == ASTNodeType.TRY_CATCH:
            return self.execute_try_catch(node)

        if node.node_type == ASTNodeType.THROW:
            return self.execute_throw(node)

        if node.node_type == ASTNodeType.BREAK:
            raise BreakException()

        if node.node_type == ASTNodeType.CONTINUE:
            raise ContinueException()

        if node.node_type == ASTNodeType.ASYNC_FUNCTION:
            return self.execute_async_function(node)

        if node.node_type == ASTNodeType.AWAIT:
            return self.execute_await(node)

        if node.node_type == ASTNodeType.PARALLEL:
            return self.execute_parallel(node)

        if node.node_type == ASTNodeType.EMIT:
            return self.execute_emit(node)

        # New node types
        if node.node_type == ASTNodeType.CLASS:
            return self.execute_class_node(node)

        if node.node_type == ASTNodeType.NEW:
            return self.execute_new(node)

        if node.node_type == ASTNodeType.TERNARY:
            cond = self.execute(node.children[0])
            if cond.value:
                return self.execute(node.children[1])
            else:
                return self.execute(node.children[2])

        if node.node_type == ASTNodeType.NULL_COALESCE:
            left = self.execute(node.children[0])
            if left.value is not None and left.value is not False and left.value != "":
                return left
            return self.execute(node.children[1])

        if node.node_type == ASTNodeType.OPTIONAL_CHAIN:
            obj = self.execute(node.children[0])
            if obj.value is None:
                return RuntimeValue(None, "null")
            member_name = node.value
            try:
                return self._get_member(obj, member_name)
            except Exception:
                return RuntimeValue(None, "null")

        if node.node_type == ASTNodeType.SPREAD:
            # Bare spread node — evaluate the inner expression
            return self.execute(node.children[0])

        if node.node_type == ASTNodeType.UNSAFE_BLOCK:
            # Execute block in unsafe context — full OS-level access via stdlib modules
            old_unsafe = getattr(self, '_unsafe_ctx', False)
            self._unsafe_ctx = True
            try:
                result = self.execute(node.children[0])
            finally:
                self._unsafe_ctx = old_unsafe
            return result

        if node.node_type == ASTNodeType.COMPREHENSION_LIST:
            return self.execute_comprehension_list(node)

        if node.node_type == ASTNodeType.COMPREHENSION_DICT:
            return self.execute_comprehension_dict(node)

        if node.node_type == ASTNodeType.DESTRUCTURE:
            return self.execute_destructure(node)

        raise InterpreterError(f"Unknown node type: {node.node_type}")

    # ── array / dict helpers ──────────────────────────────────────────────────

    def execute_array(self, node: ASTNode) -> RuntimeValue:
        """Execute array literal, handling spread elements"""
        elements = node.value if isinstance(node.value, list) else node.children
        result = []
        for elem in elements:
            if elem.node_type == ASTNodeType.SPREAD:
                spread_val = self.execute(elem.children[0])
                if isinstance(spread_val.value, list):
                    result.extend(spread_val.value)
                else:
                    result.append(spread_val)
            else:
                result.append(self.execute(elem))
        return RuntimeValue(result, "array")

    def execute_dict(self, node: ASTNode) -> RuntimeValue:
        """Execute dict literal, handling spread entries"""
        result_dict = {}
        for pair in node.value:
            if pair.get("spread"):
                spread_val = self.execute(pair["value"])
                if isinstance(spread_val.value, dict):
                    for k, v in spread_val.value.items():
                        if k not in ("__class__", "__instance__", "__methods__"):
                            result_dict[k] = v
            else:
                key = pair["key"]
                val = self.execute_value(pair["value"])
                result_dict[key] = val
        return RuntimeValue(result_dict, "dict")

    # ── comprehensions ────────────────────────────────────────────────────────

    def execute_comprehension_list(self, node: ASTNode) -> RuntimeValue:
        """Execute list comprehension [expr for var in iterable [if cond]]"""
        expr_node = node.children[0]
        var_name = node.children[1].value  # identifier node
        iterable = self.execute(node.children[2])
        condition = node.children[3] if len(node.children) > 3 else None

        result = []
        items = iterable.value if isinstance(iterable.value, list) else []
        for item in items:
            if not isinstance(item, RuntimeValue):
                item = RuntimeValue(item, "any")
            old_env = self.env
            self.env = Environment(parent=old_env)
            self.env.set(var_name, item)
            try:
                if condition is None or self.execute(condition).value:
                    result.append(self.execute(expr_node))
            finally:
                self.env = old_env
        return RuntimeValue(result, "array")

    def execute_comprehension_dict(self, node: ASTNode) -> RuntimeValue:
        """Execute dict comprehension {k: v for k, v in iterable}"""
        # children: [key_expr, val_expr, k_var_id, v_var_id, iterable, (optional cond)]
        key_expr = node.children[0]
        val_expr = node.children[1]
        k_var = node.children[2].value
        v_var = node.children[3].value
        iterable = self.execute(node.children[4])
        condition = node.children[5] if len(node.children) > 5 else None

        result = {}
        items = iterable.value if isinstance(iterable.value, list) else []
        for item in items:
            if not isinstance(item, RuntimeValue):
                item = RuntimeValue(item, "any")
            old_env = self.env
            self.env = Environment(parent=old_env)
            # item could be a list/tuple [k, v] or a dict with key/value
            if isinstance(item.value, list) and len(item.value) >= 2:
                k_item = item.value[0]
                v_item = item.value[1]
            else:
                k_item = item
                v_item = item
            if not isinstance(k_item, RuntimeValue):
                k_item = RuntimeValue(k_item, "any")
            if not isinstance(v_item, RuntimeValue):
                v_item = RuntimeValue(v_item, "any")
            self.env.set(k_var, k_item)
            self.env.set(v_var, v_item)
            try:
                if condition is None or self.execute(condition).value:
                    k = self.execute(key_expr)
                    v = self.execute(val_expr)
                    result[k.value if isinstance(k.value, str) else str(k.value)] = v
            finally:
                self.env = old_env
        return RuntimeValue(result, "dict")

    # ── destructuring ─────────────────────────────────────────────────────────

    def execute_destructure(self, node: ASTNode) -> RuntimeValue:
        """Execute destructuring assignment: let (a, b) = expr"""
        value = self.execute(node.children[0])
        names = node.value  # list of variable names
        if isinstance(value.value, list):
            for i, name in enumerate(names):
                if name != "_":
                    v = value.value[i] if i < len(value.value) else RuntimeValue(None, "null")
                    if not isinstance(v, RuntimeValue):
                        v = RuntimeValue(v, "any")
                    self.env.set(name, v)
        elif isinstance(value.value, (tuple, )):
            lst = list(value.value)
            for i, name in enumerate(names):
                if name != "_":
                    v = lst[i] if i < len(lst) else RuntimeValue(None, "null")
                    if not isinstance(v, RuntimeValue):
                        v = RuntimeValue(v, "any")
                    self.env.set(name, v)
        return value

    # ── module execution ──────────────────────────────────────────────────────

    def execute_module(self, node: ASTNode) -> RuntimeValue:
        """Execute module (file)"""
        result = RuntimeValue(None, "null")
        functions = {}

        for child in node.children:
            result = self.execute(child)
            if child.node_type in (ASTNodeType.FUNCTION, ASTNodeType.ASYNC_FUNCTION):
                functions[child.value] = result
                # Also register in environment for calling
                self.env.variables[child.value] = result

        # Auto-execute main() function if defined
        if "main" in functions:
            main_func = functions["main"]
            func_data = main_func.value
            old_env = self.env
            self.env = Environment(parent=func_data.get("env", self.env))

            # Call main with command line args (skip script name)
            import sys
            cli_args = sys.argv[2:] if len(sys.argv) > 2 else []
            args_val = RuntimeValue(cli_args, "array")
            self.env.set("args", args_val)

            for param, arg in zip(func_data["params"], [args_val]):
                self.env.set(param["name"], arg)

            try:
                result = self.execute(func_data["body"])
            except ReturnException as e:
                result = e.value
            self.env = old_env

        return result

    _MODULE_ALIASES = {
        # Legacy
        "log":     "native_log",
        "scan":    "native_scan",
        "crypto":  "native_crypto",
        "io":      "native_io",
        "http":    "native_http",
        "recon":   "native_recon",
        "enum":    "native_enum",
        "exploit": "native_exploit",
        # Core stdlib
        "str":     "native_str",
        "list":    "native_list",
        "math":    "native_math",
        "rand":    "native_rand",
        "time":    "native_time",
        "regex":   "native_regex",
        "json":    "native_json",
        "fs":      "native_fs",
        "os":      "native_os",
        "color":   "native_color",
        "fmt":     "native_fmt",
        # Network
        "net":     "native_net",
        "dns":     "native_dns",
        "ssl":     "native_ssl",
        "smtp":    "native_smtp",
        "ftp":     "native_ftp",
        # Security
        "encode":  "native_encode",
        "hash":    "native_hash",
        "jwt":     "native_jwt",
        "fuzz":    "native_fuzz",
        "brute":   "native_brute",
        "parse":   "native_parse",
        "report":  "native_report",
        # New cybersecurity modules
        "vuln":    "native_vuln",
        "session": "native_session",
        "payload": "native_payload",
        "bypass":  "native_bypass",
        "scan":    "native_advscan",  # override with advanced scan
        # Security-native modules
        "inject":  "native_inject",
        "mem":     "native_mem",
        "evasion": "native_evasion",
        "covert":  "native_covert",
        "crypt":   "native_crypt",
    }

    def execute_import(self, node: ASTNode) -> RuntimeValue:
        """Execute import statement"""
        imports = node.value
        for imp in imports:
            native_name = self._MODULE_ALIASES.get(imp, imp)
            if native_name in self.env.modules:
                self.env.variables[imp] = RuntimeValue(self.env.modules[native_name], "module")
            elif imp in self.env.modules:
                self.env.variables[imp] = RuntimeValue(self.env.modules[imp], "module")
            else:
                # Try to load from stdlib (.kop then .apo)
                loaded = False
                for ext in (".kop", ".apo"):
                    stdlib_path = Path(__file__).parent.parent / "stdlib" / f"{imp}{ext}"
                    if stdlib_path.exists():
                        try:
                            source = stdlib_path.read_text(encoding="utf-8")
                            self.execute(parse(source))
                            loaded = True
                        except Exception:
                            pass
                        break

                if not loaded:
                    # Try installed packages via pkg_manager
                    try:
                        from pkg_manager import resolve_package_path
                        pkg_path = resolve_package_path(imp)
                        if pkg_path and pkg_path.exists():
                            source = pkg_path.read_text(encoding="utf-8")
                            self.execute(parse(source))
                            loaded = True
                    except Exception:
                        pass

                if not loaded:
                    print(f"[warn] import '{imp}' not found (not a built-in, stdlib file, or installed package)")
        return RuntimeValue(None, "null")

    def execute_export(self, node: ASTNode) -> RuntimeValue:
        """Execute export statement"""
        value = self.execute(node.value)
        return value

    def execute_function(self, node: ASTNode) -> RuntimeValue:
        """Create function closure"""
        func = {
            "params": node.meta.get("params", []),
            "body": node.meta.get("body"),
            "return_type": node.meta.get("return_type"),
            "env": self.env
        }
        fn_val = RuntimeValue(func, "function")
        # Register the function in the current env by name
        if node.value:
            self.env.set(node.value, fn_val)
        return fn_val

    def execute_variable(self, node: ASTNode) -> RuntimeValue:
        """Execute variable declaration"""
        value = self.execute(node.children[0])
        name = node.value
        mutable = node.meta.get("mutability") != "constant"
        self.env.set(name, value, mutable)
        return value

    def execute_block(self, node: ASTNode) -> RuntimeValue:
        """Execute block of statements"""
        result = RuntimeValue(None, "null")
        for child in node.children:
            result = self.execute(child)
        return result

    def execute_if(self, node: ASTNode) -> RuntimeValue:
        """Execute if statement"""
        condition = self.execute(node.value)
        if condition.value:
            return self.execute(node.children[0])

        # Check elif blocks
        elif_blocks = node.meta.get("elif", [])
        for elif_cond, elif_block in elif_blocks:
            if self.execute(elif_cond).value:
                return self.execute(elif_block)

        # Check else
        else_block = node.meta.get("else")
        if else_block:
            return self.execute(else_block)

        return RuntimeValue(None, "null")

    def execute_match(self, node: ASTNode) -> RuntimeValue:
        """Execute match statement"""
        subject = self.execute(node.value)

        for arm in node.children:
            pattern = arm["pattern"]
            result_expr = arm["result"]

            # Simple pattern matching
            if pattern.value == "_" or pattern.value == subject.value:
                return self.execute(result_expr)

        return RuntimeValue(None, "null")

    def execute_for(self, node: ASTNode) -> RuntimeValue:
        """Execute for loop with break/continue/else and tuple destructuring"""
        var_name = node.value
        iterable = self.execute(node.children[0])
        body = node.children[1]

        result = RuntimeValue(None, "null")
        items = iterable.value if isinstance(iterable.value, list) else []

        broke = False
        for item in items:
            if not isinstance(item, RuntimeValue):
                item = RuntimeValue(item, "any")

            # Tuple destructuring in for: for (k, v) in ...
            if isinstance(var_name, tuple):
                if isinstance(item.value, list):
                    for i, vn in enumerate(var_name):
                        v = item.value[i] if i < len(item.value) else RuntimeValue(None, "null")
                        if not isinstance(v, RuntimeValue):
                            v = RuntimeValue(v, "any")
                        self.env.set(vn, v)
                else:
                    self.env.set(var_name[0], item)
            else:
                self.env.set(var_name, item)

            try:
                result = self.execute(body)
            except BreakException:
                broke = True
                break
            except ContinueException:
                continue

        # for...else: execute else block only if loop was not broken
        if not broke:
            else_block = node.meta.get("else_block")
            if else_block:
                result = self.execute(else_block)

        return result

    def execute_while(self, node: ASTNode) -> RuntimeValue:
        """Execute while loop (supports break/continue)"""
        condition_node = node.value
        body = node.children[0]

        result = RuntimeValue(None, "null")
        while self.execute(condition_node).value:
            try:
                result = self.execute(body)
            except BreakException:
                break
            except ContinueException:
                continue

        return result

    def execute_return(self, node: ASTNode) -> RuntimeValue:
        """Execute return statement"""
        if node.value:
            value = self.execute(node.value)
        else:
            value = RuntimeValue(None, "null")
        raise ReturnException(value)

    def execute_identifier(self, node: ASTNode) -> RuntimeValue:
        """Resolve identifier"""
        name = node.value
        # Handle 'None' as null
        if name == "None":
            return RuntimeValue(None, "null")
        try:
            return self.env.get(name)
        except NameError:
            # Check modules
            if name in self.env.modules:
                return RuntimeValue(self.env.modules[name], "module")
            raise

    def _get_member(self, obj: RuntimeValue, member_name: str) -> RuntimeValue:
        """Get a member from an object (shared logic for MEMBER_ACCESS and OPTIONAL_CHAIN)"""
        # KoppaBytes methods
        if isinstance(obj.value, KoppaBytes):
            kb = obj.value
            if member_name == "hex":    return RuntimeValue(kb.hex(), "string")
            if member_name == "b64":    return RuntimeValue(kb.b64(), "string")
            if member_name == "len":    return RuntimeValue(len(kb), "int")
            if member_name == "to_str": return RuntimeValue(kb.to_str(), "string")
            if member_name == "xor":
                def _xor_method(key):
                    k = key.value if isinstance(key, RuntimeValue) else key
                    return RuntimeValue(kb.xor(k), "bytes")
                return RuntimeValue(_xor_method, "method")

        # Session / arbitrary Python objects with methods
        if obj.value_type in ("session", "object", "any") and hasattr(obj.value, member_name):
            attr = getattr(obj.value, member_name)
            if callable(attr):
                def _make_bound(m):
                    def _bound(*call_args):
                        raw = [a.value if isinstance(a, RuntimeValue) else a for a in call_args]
                        result = m(*raw)
                        if isinstance(result, RuntimeValue): return result
                        if result is None: return RuntimeValue(None, "null")
                        return RuntimeValue(result, "any")
                    return RuntimeValue(_bound, "method")
                return _make_bound(attr)
            if isinstance(attr, RuntimeValue): return attr
            return RuntimeValue(attr, "any")

        if obj.value_type == "module" and isinstance(obj.value, dict):
            if member_name in obj.value:
                return RuntimeValue(obj.value[member_name], "method")

        # Array methods
        if obj.value_type == "array":
            if member_name == "len":
                return RuntimeValue(len(obj.value), "int")
            if member_name == "length":
                return RuntimeValue(len(obj.value), "int")
            if member_name == "push":
                def push(item):
                    obj.value.append(item)
                    return RuntimeValue(None, "null")
                return RuntimeValue(push, "method")
            if member_name == "pop":
                def pop_fn():
                    if obj.value:
                        return obj.value.pop()
                    return RuntimeValue(None, "null")
                return RuntimeValue(pop_fn, "method")
            if member_name == "map":
                def map_fn(fn):
                    return RuntimeValue([fn(x).value for x in obj.value], "array")
                return RuntimeValue(map_fn, "method")
            if member_name == "filter":
                def filter_fn(fn):
                    return RuntimeValue([x for x in obj.value if fn(x).value], "array")
                return RuntimeValue(filter_fn, "method")
            if member_name == "where":
                def where_fn(fn):
                    return RuntimeValue([x for x in obj.value if fn(x).value], "array")
                return RuntimeValue(where_fn, "method")
            if member_name == "join":
                def join_fn(sep=""):
                    sep = sep.value if isinstance(sep, RuntimeValue) else sep
                    parts = [str(x.value if isinstance(x, RuntimeValue) else x) for x in obj.value]
                    return RuntimeValue(sep.join(parts), "string")
                return RuntimeValue(join_fn, "method")

        # Object instance method/field access
        if obj.value_type == "object" and isinstance(obj.value, dict):
            methods = obj.value.get("__methods__", {})
            if member_name in methods:
                method = methods[member_name]
                def make_bound(m, o):
                    def bound(*args):
                        old_env = self.env
                        self.env = Environment(parent=m.get("env", old_env))
                        self.env.set("self", o)
                        params = m.get("params", [])
                        # skip 'self' param (first param)
                        non_self_params = [p for p in params if p.get("name") != "self"]
                        provided = list(args)
                        for i, param in enumerate(non_self_params):
                            if param.get("variadic"):
                                self.env.set(param["name"], RuntimeValue(list(provided[i:]), "array"))
                                break
                            elif i < len(provided):
                                self.env.set(param["name"], provided[i])
                            elif "default" in param:
                                self.env.set(param["name"], self.execute(param["default"]))
                            else:
                                self.env.set(param["name"], RuntimeValue(None, "null"))
                        try:
                            result = self.execute(m["body"])
                        except ReturnException as e:
                            result = e.value
                        finally:
                            self.env = old_env
                        return result
                    return bound
                return RuntimeValue(make_bound(method, obj), "method")
            if member_name in obj.value:
                v = obj.value[member_name]
                return v if isinstance(v, RuntimeValue) else RuntimeValue(v, "any")

        # Dict member access (also covers http_response, exec_result, etc. whose value is a dict)
        if isinstance(obj.value, dict):
            if member_name in obj.value:
                val = obj.value[member_name]
                if not isinstance(val, RuntimeValue):
                    val = RuntimeValue(val, "any")
                return val
            raise InterpreterError(f"Unknown key: {member_name} in {obj.value_type}")

        # String methods
        if isinstance(obj.value, str):
            s = obj.value
            if member_name == "len":
                return RuntimeValue(len(s), "int")
            if member_name == "length":
                return RuntimeValue(len(s), "int")
            if member_name == "contains":
                return RuntimeValue(lambda sub: RuntimeValue(sub in s, "bool"), "method")
            if member_name == "split":
                return RuntimeValue(lambda sep=" ": RuntimeValue([RuntimeValue(p, "string") for p in s.split(sep)], "array"), "method")
            if member_name == "upper":
                return RuntimeValue(s.upper(), "string")
            if member_name == "lower":
                return RuntimeValue(s.lower(), "string")
            if member_name == "strip":
                return RuntimeValue(s.strip(), "string")
            if member_name == "startswith":
                return RuntimeValue(lambda prefix: RuntimeValue(s.startswith(prefix), "bool"), "method")
            if member_name == "endswith":
                return RuntimeValue(lambda suffix: RuntimeValue(s.endswith(suffix), "bool"), "method")
            if member_name == "replace":
                return RuntimeValue(lambda old, new="": RuntimeValue(s.replace(old, new), "string"), "method")

        raise InterpreterError(f"Unknown member: {member_name} on {obj}")

    def execute_member_access(self, node: ASTNode) -> RuntimeValue:
        """Execute member access (e.g., log.info)"""
        obj = self.execute(node.children[0])
        member_name = node.value
        return self._get_member(obj, member_name)

    def execute_call(self, node: ASTNode) -> RuntimeValue:
        """Execute function call"""
        # node.value is the function/member, node.children are args
        func = self.execute(node.value)
        args = [self.execute(arg) for arg in node.children]

        # Class instantiation by calling class value directly
        if func.value_type == "class":
            return self.instantiate_class(func, args)

        if func.value_type in ("function", "async_function"):
            func_data = func.value
            old_env = self.env
            self.env = Environment(parent=func_data.get("env", self.env))

            # Bind parameters with defaults and variadic support
            params = func_data.get("params", [])
            provided = args
            for i, param in enumerate(params):
                if param.get("variadic"):
                    self.env.set(param["name"], RuntimeValue(list(provided[i:]), "array"))
                    break
                elif i < len(provided):
                    self.env.set(param["name"], provided[i])
                elif "default" in param:
                    self.env.set(param["name"], self.execute(param["default"]))
                else:
                    self.env.set(param["name"], RuntimeValue(None, "null"))

            try:
                result = self.execute(func_data["body"])
            except ReturnException as e:
                result = e.value
            self.env = old_env
            return result

        if func.value_type == "method" and callable(func.value):
            result = func.value(*[a.value if isinstance(a, RuntimeValue) else a for a in args])
            if not isinstance(result, RuntimeValue):
                result = RuntimeValue(result, "any")
            return result

        if func.value_type == "module":
            # Method call on module - func.value is a dict of {name: callable}
            if isinstance(func.value, dict) and len(node.children) > 0:
                member_node = node.children[0]
                if member_node.node_type == ASTNodeType.MEMBER_ACCESS:
                    method_name = member_node.value
                    if method_name in func.value:
                        return func.value[method_name](*[a.value for a in args])

        if callable(func.value):
            result = func.value(*[a.value if isinstance(a, RuntimeValue) else a for a in args])
            if not isinstance(result, RuntimeValue):
                result = RuntimeValue(result, "any")
            return result

        raise InterpreterError(f"Cannot call {func}")

    def execute_pipeline(self, node: ASTNode) -> RuntimeValue:
        """Execute pipeline (|> operator)"""
        result = self.execute(node.children[0])

        for i in range(1, len(node.children)):
            next_node = node.children[i]
            if next_node.node_type == ASTNodeType.CALL:
                # Pass result as first argument
                func = self.execute(next_node.value)
                args = [result] + [self.execute(arg) for arg in next_node.children]

                if func.value_type == "function":
                    func_data = func.value
                    old_env = self.env
                    self.env = Environment(parent=func_data.get("env", self.env))

                    for param, arg in zip(func_data["params"], args):
                        self.env.set(param["name"], arg)

                    try:
                        result = self.execute(func_data["body"])
                    except ReturnException as e:
                        result = e.value
                    self.env = old_env
                elif callable(func.value):
                    result = RuntimeValue(func.value(*[a.value for a in args]), "any")
                else:
                    result = RuntimeValue(func.value, "any")

        return result

    def execute_binary_op(self, node: ASTNode) -> RuntimeValue:
        """Execute binary operation"""
        op = node.value

        if op in ("+=", "-=", "*=", "/=", "%="):
            right = self.execute(node.children[1])
            lhs = node.children[0]
            base = op[0]

            def _apply(lv, rv):
                if base == "+":
                    return str(lv) + str(rv) if isinstance(lv, str) or isinstance(rv, str) else lv + rv
                if base == "-": return lv - rv
                if base == "*": return lv * rv
                if base == "/": return lv / rv
                return lv % rv

            if lhs.node_type == ASTNodeType.IDENTIFIER:
                current = self.env.get(lhs.value)
                new_val = RuntimeValue(_apply(current.value, right.value), current.value_type)
                self.env.set(lhs.value, new_val)
                return new_val

            if lhs.node_type == ASTNodeType.MEMBER_ACCESS:
                obj = self.execute(lhs.children[0])
                field = lhs.value
                if isinstance(obj.value, dict):
                    cur = obj.value.get(field)
                    cur_val = cur.value if isinstance(cur, RuntimeValue) else cur
                    nv = _apply(cur_val, right.value)
                    obj.value[field] = RuntimeValue(nv, "any")
                    return RuntimeValue(nv, "any")

            raise InterpreterError(f"Cannot use {op} on {lhs.node_type}")

        if op == "=":
            right = self.execute(node.children[1])
            lhs = node.children[0]
            if lhs.node_type == ASTNodeType.IDENTIFIER:
                self.env.set(lhs.value, right)
                return right
            if lhs.node_type == ASTNodeType.INDEX:
                container = self.execute(lhs.children[0])
                idx = self.execute(lhs.value)
                if isinstance(container.value, list) and isinstance(idx.value, int):
                    while len(container.value) <= idx.value:
                        container.value.append(None)
                    container.value[idx.value] = right
                elif isinstance(container.value, dict):
                    key = idx.value if not isinstance(idx.value, RuntimeValue) else idx.value.value
                    container.value[key] = right
                return right
            if lhs.node_type == ASTNodeType.MEMBER_ACCESS:
                obj = self.execute(lhs.children[0])
                if obj.value_type in ("object", "dict") and isinstance(obj.value, dict):
                    obj.value[lhs.value] = right
                    return right
                if isinstance(obj.value, dict):
                    obj.value[lhs.value] = right
                    return right
                raise InterpreterError(f"Cannot assign member on {obj.value_type}")
            if lhs.node_type == ASTNodeType.OPTIONAL_CHAIN:
                obj = self.execute(lhs.children[0])
                if obj.value is not None and isinstance(obj.value, dict):
                    obj.value[lhs.value] = right
                return right
            raise InterpreterError(f"Cannot assign to {lhs.node_type}")

        left = self.execute(node.children[0])
        right = self.execute(node.children[1])

        lv = left.value if isinstance(left, RuntimeValue) else left
        rv = right.value if isinstance(right, RuntimeValue) else right

        if op == "**":
            return RuntimeValue(lv ** rv, "number")
        if op == "==":
            return RuntimeValue(lv == rv, "bool")
        if op == "+":
            if isinstance(lv, str) or isinstance(rv, str):
                return RuntimeValue(str(lv) + str(rv), "string")
            return RuntimeValue(lv + rv, left.value_type)
        if op == "-":
            return RuntimeValue(lv - rv, "number")
        if op == "*":
            return RuntimeValue(lv * rv, "number")
        if op == "/":
            return RuntimeValue(lv / rv, "number")
        if op == "%":
            return RuntimeValue(lv % rv, "number")
        if op == "!=":
            return RuntimeValue(lv != rv, "bool")
        if op == "<":
            return RuntimeValue(lv < rv, "bool")
        if op == ">":
            return RuntimeValue(lv > rv, "bool")
        if op == "<=":
            return RuntimeValue(lv <= rv, "bool")
        if op == ">=":
            return RuntimeValue(lv >= rv, "bool")
        if op == "&&":
            return RuntimeValue(bool(lv) and bool(rv), "bool")
        if op == "||":
            return RuntimeValue(lv or rv, "bool")
        if op == "in":
            if isinstance(rv, list):
                return RuntimeValue(any(
                    (x.value if isinstance(x, RuntimeValue) else x) == lv
                    for x in rv
                ), "bool")
            return RuntimeValue(lv in rv, "bool")
        if op == "not in":
            if isinstance(rv, list):
                return RuntimeValue(not any(
                    (x.value if isinstance(x, RuntimeValue) else x) == lv
                    for x in rv
                ), "bool")
            return RuntimeValue(lv not in rv, "bool")
        if op == "is":
            return RuntimeValue(lv is rv or lv == rv, "bool")
        if op == "is not":
            return RuntimeValue(lv is not rv and lv != rv, "bool")

        # Bitwise operators
        if op == "&":
            if isinstance(lv, KoppaBytes):
                return RuntimeValue(KoppaBytes(bytes(b & int(rv) for b in lv.data)), "bytes")
            return RuntimeValue(int(lv) & int(rv), "int")
        if op == "|":
            return RuntimeValue(int(lv) | int(rv), "int")
        if op == "^":
            if isinstance(lv, KoppaBytes):
                return RuntimeValue(lv.xor(rv if isinstance(rv, KoppaBytes) else rv), "bytes")
            return RuntimeValue(int(lv) ^ int(rv), "int")
        if op == "<<":
            return RuntimeValue(int(lv) << int(rv), "int")
        if op == ">>":
            return RuntimeValue(int(lv) >> int(rv), "int")

        raise InterpreterError(f"Unknown operator: {op}")

    def execute_unary_op(self, node: ASTNode) -> RuntimeValue:
        """Execute unary operation"""
        operand = self.execute(node.children[0])
        op = node.value

        if op in ("!", "not"):
            return RuntimeValue(not operand.value, "bool")
        if op == "-":
            return RuntimeValue(-operand.value, "number")
        if op == "~":
            return RuntimeValue(~int(operand.value), "int")

        raise InterpreterError(f"Unknown unary operator: {op}")

    def execute_value(self, node) -> RuntimeValue:
        """Execute a value node"""
        if isinstance(node, ASTNode):
            return self.execute(node)
        return RuntimeValue(node, "any")

    # ── try/catch ────────────────────────────────────────────────────────────

    def execute_try_catch(self, node: ASTNode) -> RuntimeValue:
        """Execute try/catch block"""
        try_block = node.value
        catch_block = node.children[0] if node.children else None
        catch_var = node.meta.get("catch_var")
        try:
            return self.execute(try_block)
        except ReturnException:
            raise
        except InterpreterError as e:
            if catch_block:
                old_env = self.env
                self.env = Environment(parent=old_env)
                if catch_var:
                    self.env.set(catch_var, RuntimeValue(str(e), "string"))
                try:
                    result = self.execute(catch_block)
                finally:
                    self.env = old_env
                return result
            return RuntimeValue(None, "null")
        except Exception as e:
            if catch_block:
                old_env = self.env
                self.env = Environment(parent=old_env)
                if catch_var:
                    self.env.set(catch_var, RuntimeValue(str(e), "string"))
                try:
                    result = self.execute(catch_block)
                finally:
                    self.env = old_env
                return result
            return RuntimeValue(None, "null")

    def execute_throw(self, node: ASTNode) -> RuntimeValue:
        """Execute throw statement"""
        msg = self.execute(node.value) if node.value else RuntimeValue("Error", "string")
        raise InterpreterError(str(msg.value if isinstance(msg, RuntimeValue) else msg))

    # ── async / parallel ─────────────────────────────────────────────────────

    def execute_async_function(self, node: ASTNode) -> RuntimeValue:
        """Register async function"""
        func = {
            "params": node.meta.get("params", []),
            "body":   node.meta.get("body"),
            "return_type": node.meta.get("return_type"),
            "env":    self.env,
            "async":  True,
        }
        fn_val = RuntimeValue(func, "async_function")
        if node.value:
            self.env.set(node.value, fn_val)
        return fn_val

    def execute_await(self, node: ASTNode) -> RuntimeValue:
        """Execute await — run async function and wait for result"""
        val = self.execute(node.value) if node.value else RuntimeValue(None, "null")
        if isinstance(val, RuntimeValue) and val.value_type == "future":
            future = val.value
            if hasattr(future, 'result'):
                try:
                    return future.result(timeout=30)
                except Exception as e:
                    return RuntimeValue({"error": str(e)}, "dict")
        return val

    def execute_parallel(self, node: ASTNode) -> RuntimeValue:
        """Execute parallel block — run child statements concurrently"""
        results = []
        body = node.children[0] if node.children else node.value
        if not body:
            return RuntimeValue(results, "array")

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            stmts = body.children if hasattr(body, 'children') else [body]
            futures = []
            for stmt in stmts:
                interp = Interpreter()
                interp.env = Environment(parent=self.env)
                futures.append(executor.submit(interp.execute, stmt))
            for f in concurrent.futures.as_completed(futures, timeout=60):
                try:
                    results.append(f.result())
                except Exception:
                    pass

        return RuntimeValue(results, "array")

    def execute_emit(self, node: ASTNode) -> RuntimeValue:
        """Execute emit — yield a value from async stream"""
        val = self.execute(node.value) if node.value else RuntimeValue(None, "null")
        print(f"\033[36m[EMIT]\033[0m {val.value if isinstance(val, RuntimeValue) else val}")
        return val

    # ── class system ─────────────────────────────────────────────────────────

    def execute_class_node(self, node: ASTNode) -> RuntimeValue:
        """Register class definition from CLASS AST node"""
        class_name = node.value
        methods = {}
        fields = {}
        for method_node in node.children:
            if method_node.node_type == ASTNodeType.FUNCTION:
                fn_val = self.execute_function(method_node)
                methods[method_node.value] = fn_val.value
        cls_def = {
            "__class__": class_name,
            "__methods__": methods,
            "__fields__": fields,
            "__callable__": True,
        }
        cls_val = RuntimeValue(cls_def, "class")
        self.env.set(class_name, cls_val)
        return cls_val

    def execute_new(self, node: ASTNode) -> RuntimeValue:
        """Instantiate a class via 'new ClassName(args)'"""
        cls_val = self.env.get(node.value)
        args = [self.execute(arg) for arg in node.children]
        return self.instantiate_class(cls_val, args)

    def execute_class(self, name: str, methods: dict, fields: dict) -> RuntimeValue:
        """Create a class definition (legacy helper)"""
        cls = {
            "__class__": name,
            "__methods__": methods,
            "__fields__": fields,
        }
        constructor = RuntimeValue(cls, "class")
        self.env.set(name, constructor)
        return constructor

    def instantiate_class(self, cls_val: RuntimeValue, args: list) -> RuntimeValue:
        """Create a class instance"""
        cls = cls_val.value
        instance = {
            "__instance__": cls["__class__"],
            "__methods__": cls["__methods__"],
        }
        for k, v in cls.get("__fields__", {}).items():
            instance[k] = v
        obj = RuntimeValue(instance, "object")
        if "__init__" in cls["__methods__"]:
            init = cls["__methods__"]["__init__"]
            old_env = self.env
            self.env = Environment(parent=init.get("env", old_env))
            self.env.set("self", obj)
            params = init.get("params", [])
            non_self_params = [p for p in params if p.get("name") != "self"]
            provided = args
            for i, param in enumerate(non_self_params):
                if param.get("variadic"):
                    self.env.set(param["name"], RuntimeValue(list(provided[i:]), "array"))
                    break
                elif i < len(provided):
                    self.env.set(param["name"], provided[i])
                elif "default" in param:
                    self.env.set(param["name"], self.execute(param["default"]))
                else:
                    self.env.set(param["name"], RuntimeValue(None, "null"))
            try:
                self.execute(init["body"])
            except ReturnException:
                pass
            self.env = old_env
        return obj


def interpret(source: str) -> RuntimeValue:
    """Parse and interpret KOPPA source code"""
    ast = parse(source)
    interpreter = Interpreter()
    return interpreter.execute(ast)


if __name__ == "__main__":
    # Test the interpreter
    test_code = '''
import scan, log

fn main() {
    let target = "127.0.0.1"
    var port = 80

    log.info("Scanning {target}")

    if scan.tcp_connect(target, port) {
        log.info("Port {port} is open")
    }
}
'''

    result = interpret(test_code)
    print(f"Result: {result}")
