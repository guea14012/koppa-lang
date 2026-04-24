"""
APOLLO Language Interpreter
Executes APOLLO AST with security primitives
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum, auto
import subprocess
import socket
import re
import json
import hashlib
from pathlib import Path

from parser import ASTNode, ASTNodeType, parse


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


def _interpolate_string(s: str, env: 'Environment') -> str:
    """Replace {varname} and {obj.field} patterns in strings with live env values"""
    if '{' not in s:
        return s
    def resolve_part(val, part):
        """Resolve one member access step"""
        if isinstance(val, RuntimeValue):
            val = val.value
        if part == "len":
            return len(val) if isinstance(val, (list, dict, str)) else None
        if isinstance(val, dict):
            return val.get(part)
        if isinstance(val, list):
            if part == "length" or part == "size":
                return len(val)
        if hasattr(val, part):
            return getattr(val, part)
        return None
    _MISSING = object()  # sentinel for "variable not found"

    def replace_ref(m):
        expr = m.group(1)
        try:
            parts = expr.split('.')
            try:
                val = env.get(parts[0])
            except Exception:
                return m.group(0)  # variable not defined → leave literal
            for part in parts[1:]:
                val = resolve_part(val, part)
            if isinstance(val, RuntimeValue):
                val = val.value
            return str(val) if val is not None else "(none)"
        except Exception:
            return m.group(0)
    return re.sub(r'\{([\w.]+)\}', replace_ref, s)


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
        # Simplified NTLM hash
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
    """APOLLO language interpreter"""

    def __init__(self):
        self.env = Environment()
        self.load_builtins()

    def load_builtins(self):
        """Load built-in modules"""
        self.env.modules["native_recon"] = SecurityModule.recon_module()
        self.env.modules["native_scan"] = SecurityModule.scan_module()
        self.env.modules["native_enum"] = SecurityModule.enum_module()
        self.env.modules["native_exploit"] = SecurityModule.exploit_module()
        self.env.modules["native_crypto"] = SecurityModule.crypto_module()
        self.env.modules["native_http"] = SecurityModule.http_module()
        self.env.modules["native_io"] = SecurityModule.io_module()
        # Extend io module with additional functions
        self.env.modules["native_io"]["file_exists"] = lambda p: RuntimeValue(Path(p).exists(), "bool")
        self.env.modules["native_io"]["read_lines"] = lambda p: RuntimeValue([RuntimeValue(l, "string") for l in Path(p).read_text().splitlines()], "array")
        self.env.modules["native_io"]["write_json"] = lambda data, p: Path(p).write_text(__import__('json').dumps(data if not isinstance(data, RuntimeValue) else data.value, indent=2, default=str)) or RuntimeValue(None, "null")
        self.env.modules["native_log"] = SecurityModule.log_module()
        # Built-in functions
        self.env.variables["print"] = RuntimeValue(lambda *args: print(*[a if not isinstance(a, RuntimeValue) else a.value for a in args]) or None, "function")
        self.env.variables["str"] = RuntimeValue(lambda x: RuntimeValue(str(x.value if isinstance(x, RuntimeValue) else x), "string"), "function")
        self.env.variables["int"] = RuntimeValue(lambda x: RuntimeValue(int(x.value if isinstance(x, RuntimeValue) else x), "integer"), "function")
        self.env.variables["len"] = RuntimeValue(lambda x: RuntimeValue(len(x.value if isinstance(x, RuntimeValue) else x), "int"), "function")
        self.env.variables["range"] = RuntimeValue(lambda *args: RuntimeValue([RuntimeValue(i, "integer") for i in range(*[a.value if isinstance(a, RuntimeValue) else a for a in args])], "array"), "function")

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
            elements = node.value if isinstance(node.value, list) else node.children
            return RuntimeValue([self.execute(elem) for elem in elements], "array")

        if node.node_type == ASTNodeType.INDEX:
            arr = self.execute(node.children[0])
            idx = self.execute(node.value)
            if arr.value_type == "array" and isinstance(idx.value, int):
                return RuntimeValue(arr.value[idx.value], "any")
            raise InterpreterError(f"Invalid index: {idx} on {arr}")

        if node.node_type == ASTNodeType.DICT:
            result_dict = {}
            for pair in node.value:
                key = pair["key"]
                val = self.execute_value(pair["value"])
                result_dict[key] = val
            return RuntimeValue(result_dict, "dict")

        raise InterpreterError(f"Unknown node type: {node.node_type}")

    def execute_module(self, node: ASTNode) -> RuntimeValue:
        """Execute module (file)"""
        result = RuntimeValue(None, "null")
        functions = {}

        for child in node.children:
            result = self.execute(child)
            if child.node_type == ASTNodeType.FUNCTION:
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
        "log": "native_log",
        "scan": "native_scan",
        "crypto": "native_crypto",
        "io": "native_io",
        "http": "native_http",
        "recon": "native_recon",
        "enum": "native_enum",
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
        # Register exported value in parent modules list if needed
        # For now, just return it
        return value

    def execute_function(self, node: ASTNode) -> RuntimeValue:
        """Create function closure"""
        func = {
            "params": node.meta.get("params", []),
            "body": node.meta.get("body"),
            "return_type": node.meta.get("return_type"),
            "env": self.env
        }
        return RuntimeValue(func, "function")

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
        """Execute for loop"""
        var_name = node.value
        iterable = self.execute(node.children[0])
        body = node.children[1]

        result = RuntimeValue(None, "null")

        if isinstance(iterable.value, list):
            for item in iterable.value:
                if not isinstance(item, RuntimeValue):
                    item = RuntimeValue(item, "any")
                self.env.set(var_name, item)
                result = self.execute(body)

        return result

    def execute_while(self, node: ASTNode) -> RuntimeValue:
        """Execute while loop"""
        condition_node = node.value
        body = node.children[0]

        result = RuntimeValue(None, "null")
        while self.execute(condition_node).value:
            result = self.execute(body)

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
        try:
            return self.env.get(name)
        except NameError:
            # Check modules
            if name in self.env.modules:
                return RuntimeValue(self.env.modules[name], "module")
            raise

    def execute_member_access(self, node: ASTNode) -> RuntimeValue:
        """Execute member access (e.g., log.info)"""
        obj = self.execute(node.children[0])
        member_name = node.value

        if obj.value_type == "module" and isinstance(obj.value, dict):
            if member_name in obj.value:
                return RuntimeValue(obj.value[member_name], "method")

        # Array methods
        if obj.value_type == "array":
            if member_name == "len":
                return RuntimeValue(len(obj.value), "int")
            if member_name == "push":
                def push(item):
                    obj.value.append(item)
                    return RuntimeValue(None, "null")
                return RuntimeValue(push, "method")
            if member_name == "map":
                def map_fn(fn):
                    return RuntimeValue([fn(x).value for x in obj.value], "array")
                return RuntimeValue(map_fn, "method")
            if member_name == "where":
                def where_fn(fn):
                    return RuntimeValue([x for x in obj.value if fn(x).value], "array")
                return RuntimeValue(where_fn, "method")

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

    def execute_call(self, node: ASTNode) -> RuntimeValue:
        """Execute function call"""
        # node.value is the function/member, node.children are args
        func = self.execute(node.value)
        args = [self.execute(arg) for arg in node.children]

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
            return result

        if func.value_type == "module":
            # Method call on module - func.value is a dict of {name: callable}
            if isinstance(func.value, dict) and len(node.children) > 0:
                # The first child should be the member access with method name
                member_node = node.children[0]
                if member_node.node_type == ASTNodeType.MEMBER_ACCESS:
                    method_name = member_node.value
                    if method_name in func.value:
                        return func.value[method_name](*[a.value for a in args])

        if callable(func.value):
            result = func.value(*[a.value for a in args])
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

        if op == "=":
            right = self.execute(node.children[1])
            lhs = node.children[0]
            if lhs.node_type == ASTNodeType.IDENTIFIER:
                self.env.set(lhs.value, right)
                return right
            if lhs.node_type == ASTNodeType.INDEX:
                container = self.execute(lhs.children[0])
                idx = self.execute(lhs.value)
                if container.value_type == "array" and isinstance(idx.value, int):
                    while len(container.value) <= idx.value:
                        container.value.append(None)
                    container.value[idx.value] = right
                elif container.value_type == "dict":
                    key = idx.value if not isinstance(idx.value, RuntimeValue) else idx.value.value
                    container.value[key] = right
                return right
            if lhs.node_type == ASTNodeType.MEMBER_ACCESS:
                obj = self.execute(lhs.children[0])
                if obj.value_type == "dict" and isinstance(obj.value, dict):
                    obj.value[lhs.value] = right
                return right
            raise InterpreterError(f"Cannot assign to {lhs.node_type}")

        left = self.execute(node.children[0])
        right = self.execute(node.children[1])

        if op == "==":
            return RuntimeValue(left.value == right.value, "bool")
        if op == "+":
            lv, rv = left.value, right.value
            if isinstance(lv, str) or isinstance(rv, str):
                return RuntimeValue(str(lv) + str(rv), "string")
            return RuntimeValue(lv + rv, left.value_type)
        if op == "-":
            return RuntimeValue(left.value - right.value, "number")
        if op == "*":
            return RuntimeValue(left.value * right.value, "number")
        if op == "/":
            return RuntimeValue(left.value / right.value, "number")
        if op == "%":
            return RuntimeValue(left.value % right.value, "number")
        if op == "!=":
            return RuntimeValue(left.value != right.value, "bool")
        if op == "<":
            return RuntimeValue(left.value < right.value, "bool")
        if op == ">":
            return RuntimeValue(left.value > right.value, "bool")
        if op == "<=":
            return RuntimeValue(left.value <= right.value, "bool")
        if op == ">=":
            return RuntimeValue(left.value >= right.value, "bool")
        if op == "&&":
            return RuntimeValue(left.value and right.value, "bool")
        if op == "||":
            return RuntimeValue(left.value or right.value, "bool")

        raise InterpreterError(f"Unknown operator: {op}")

    def execute_unary_op(self, node: ASTNode) -> RuntimeValue:
        """Execute unary operation"""
        operand = self.execute(node.children[0])
        op = node.value

        if op == "!":
            return RuntimeValue(not operand.value, "bool")
        if op == "-":
            return RuntimeValue(-operand.value, "number")

        raise InterpreterError(f"Unknown unary operator: {op}")

    def execute_value(self, node) -> RuntimeValue:
        """Execute a value node"""
        if isinstance(node, ASTNode):
            return self.execute(node)
        return RuntimeValue(node, "any")


def interpret(source: str) -> RuntimeValue:
    """Parse and interpret APOLLO source code"""
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
