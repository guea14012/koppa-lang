"""
APOLLO Deno Transpiler
Converts APOLLO AST to JavaScript/TypeScript for Deno
"""

from parser import ASTNodeType, parse
from typing import List, Any, Dict


class DenoTranspiler:
    """
    Transpiles APOLLO AST to JavaScript that runs on Deno
    """

    def __init__(self):
        self.indent_level = 0
        self.output = []

    def transpile(self, source: str) -> str:
        """Transpile APOLLO source to Deno/JS source"""
        ast = parse(source)
        self.output = []
        self.indent_level = 0

        # Import runtime
        self._write('import * as apollo from "./deno_runtime.ts";')
        self._write('')

        # Process root-level nodes
        for node in ast.children:
            self._process_node(node)

        # Main entry point (calls fn main() if defined)
        self._write('')
        self._write('if (typeof main === "function") {')
        self._write('  const result = await main(Deno.args);')
        self._write('  if (result !== undefined) console.log(result);')
        self._write('}')

        return "\n".join(self.output)

    def _write(self, text: str):
        indent = "  " * self.indent_level
        self.output.append(f"{indent}{text}")

    def _process_node(self, node):
        """Process an AST node and generate JS code"""
        if node.node_type == ASTNodeType.MODULE:
            for child in node.children:
                self._process_node(child)

        elif node.node_type == ASTNodeType.IMPORT:
            # Import modules - in JS, we just ensure the runtime is used
            # For specific modules, we could map them to deno_runtime exports
            pass

        elif node.node_type == ASTNodeType.FUNCTION:
            self._process_function(node)

        elif node.node_type == ASTNodeType.ASYNC_FUNCTION:
            self._process_function(node, is_async=True)

        elif node.node_type == ASTNodeType.VARIABLE:
            self._process_variable(node)

        elif node.node_type == ASTNodeType.IF:
            self._process_if(node)

        elif node.node_type == ASTNodeType.FOR:
            self._process_for(node)

        elif node.node_type == ASTNodeType.WHILE:
            self._process_while(node)

        elif node.node_type == ASTNodeType.RETURN:
            self._process_return(node)

        elif node.node_type == ASTNodeType.BLOCK:
            self.indent_level += 1
            for child in node.children:
                self._process_node(child)
            self.indent_level -= 1

        elif node.node_type == ASTNodeType.EXPRESSION_STMT:
            expr_code = self._process_expression(node.children[0])
            self._write(f"{expr_code};")

    def _process_function(self, node, is_async=False):
        """Process function declaration"""
        name = node.value
        params = node.meta.get("params", [])
        body = node.meta.get("body")

        param_str = ", ".join([p["name"] for p in params])
        async_kw = "async " if is_async else ""
        
        self._write(f"{async_kw}function {name}({param_str}) {{")
        self._process_node(body)
        self._write("}")

    def _process_variable(self, node):
        """Process variable declaration"""
        name = node.value
        mutability = node.meta.get("mutability", "let")
        
        js_kw = "const" if mutability in ("immutable", "constant") else "let"
        value_code = self._process_expression(node.children[0])
        
        self._write(f"{js_kw} {name} = {value_code};")

    def _process_if(self, node):
        """Process if/else statement"""
        condition = self._process_expression(node.value)
        
        self._write(f"if ({condition}) {{")
        self._process_node(node.children[0])
        
        # Handle elifs (stored in meta)
        elifs = node.meta.get("elif", [])
        for elif_cond, elif_block in elifs:
            cond_code = self._process_expression(elif_cond)
            self._write(f"}} else if ({cond_code}) {{")
            self._process_node(elif_block)
            
        # Handle else (stored in meta)
        else_block = node.meta.get("else")
        if else_block:
            self._write("} else {")
            self._process_node(else_block)
            
        self._write("}")

    def _process_for(self, node):
        """Process for loop"""
        var_name = node.value
        iterable = self._process_expression(node.children[0])
        body = node.children[1]
        
        self._write(f"for (const {var_name} of {iterable}) {{")
        self._process_node(body)
        self._write("}")

    def _process_while(self, node):
        """Process while loop"""
        condition = self._process_expression(node.value)
        body = node.children[0]
        
        self._write(f"while ({condition}) {{")
        self._process_node(body)
        self._write("}")

    def _process_return(self, node):
        """Process return statement"""
        if node.value:
            value = self._process_expression(node.value)
            self._write(f"return {value};")
        else:
            self._write("return;")

    def _process_expression(self, node) -> str:
        """Process an expression node and return JS code as string"""
        if node.node_type == ASTNodeType.LITERAL:
            if isinstance(node.value, str):
                return f'"{node.value}"'
            elif isinstance(node.value, bool):
                return "true" if node.value else "false"
            elif node.value is None:
                return "null"
            return str(node.value)

        elif node.node_type == ASTNodeType.IDENTIFIER:
            # Map known modules to the runtime object
            if node.value in ("log", "scan", "report", "http", "crypto"):
                return f"apollo.{node.value}"
            return node.value

        elif node.node_type == ASTNodeType.BINARY_OP:
            left = self._process_expression(node.children[0])
            right = self._process_expression(node.children[1])
            op = node.value
            
            # Map operators
            if op == "==": op = "==="
            if op == "!=": op = "!=="
            if op == "&&": op = "&&"
            if op == "||": op = "||"
            
            return f"({left} {op} {right})"

        elif node.node_type == ASTNodeType.CALL:
            func = self._process_expression(node.value)
            args = [self._process_expression(arg) for arg in node.children]
            
            # If it's a known async function from our runtime, we should potentially await it
            # For simplicity, we can wrap in await if we're in an async context, or just emit it
            return f"await {func}({', '.join(args)})"

        elif node.node_type == ASTNodeType.MEMBER_ACCESS:
            obj = self._process_expression(node.children[0])
            return f"{obj}.{node.value}"

        elif node.node_type == ASTNodeType.ARRAY:
            elements = [self._process_expression(e) for e in node.value]
            return f"[{', '.join(elements)}]"

        elif node.node_type == ASTNodeType.DICT:
            pairs = []
            for p in node.value:
                val = self._process_expression(p["value"])
                pairs.append(f'{p["key"]}: {val}')
            return f"{{ {', '.join(pairs)} }}"

        elif node.node_type == ASTNodeType.PIPELINE:
            left = self._process_expression(node.children[0])
            right = node.children[1]
            
            # piped_val |> f(a, b) => await f(piped_val, a, b)
            if right.node_type == ASTNodeType.CALL:
                func = self._process_expression(right.value)
                args = [left] + [self._process_expression(arg) for arg in right.children]
                return f"await {func}({', '.join(args)})"
            else:
                # piped_val |> f => await f(piped_val)
                func = self._process_expression(right)
                return f"await {func}({left})"

        elif node.node_type == ASTNodeType.UNARY_OP:
            operand = self._process_expression(node.children[0])
            op = node.value
            if op == "not": op = "!"
            
            # Support for default value operator `|` if used in expression
            # Actually, `|` might be tokenized differently. 
            # In APOLLO, `val | default("foo")` is common.
            
            return f"{op}{operand}"

        return "null"

def transpile(source: str) -> str:
    return DenoTranspiler().transpile(source)

if __name__ == "__main__":
    test_code = '''
fn main() {
    let target = "127.0.0.1"
    let ports = [22, 80, 443]

    log.info("Scanning " + target)

    for port in ports {
        if scan.tcp(target, port) {
            log.info("Port open")
        }
    }

    target |> scan.tcp(80) |> log.info()
}
'''
    print(transpile(test_code))
