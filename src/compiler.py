"""
APOLLO Bytecode Compiler
Compiles AST to executable bytecode with optimizations
"""

from apollo_opcodes import OpCode, CodeObject, OpcodeBuilder
from parser import ASTNodeType
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class CompileUnit:
    """Compilation unit for a module"""
    name: str
    code: CodeObject
    source: str
    constants: List[Any]
    functions: Dict[str, CodeObject]


class Compiler:
    """
    APOLLO Compiler - AST to Bytecode

    Pipeline:
    1. Lexical analysis (lexer.py)
    2. Parsing (parser.py)
    3. AST optimization
    4. Code generation (this module)
    5. Bytecode emission
    """

    def __init__(self):
        self.modules: Dict[str, CompileUnit] = {}
        self.optimizations_enabled = True
        self.constants: List[Any] = []
        self.function_codes: Dict[str, CodeObject] = {}
        self._label_counter = 0  # Unique label counter for nested structures

    def _new_label(self, name: str) -> str:
        """Return a unique label string"""
        label = f"{name}_{self._label_counter}"
        self._label_counter += 1
        return label

    def compile(self, ast_or_source, source: str = "", filename: str = "<apo>") -> CodeObject:
        """Compile AST to bytecode"""
        from lexer import tokenize
        from parser import parse, Parser

        # Handle string or AST
        if isinstance(ast_or_source, str):
            tokens = tokenize(ast_or_source)
            ast = Parser(tokens).parse()
            source = ast_or_source
        else:
            ast = ast_or_source

        builder = OpcodeBuilder()
        self._compile_node(ast, builder, filename)
        builder.add(OpCode.HALT)
        return builder.build(filename)

    def compile_module(self, ast, name: str, source: str = "") -> CompileUnit:
        """Compile entire module"""
        code = self.compile(ast, source, name)
        unit = CompileUnit(
            name=name,
            code=code,
            source=source,
            constants=code.constants,
            functions=self.function_codes.copy()
        )
        self.modules[name] = unit
        return unit

    def _compile_node(self, node, builder, filename: str = "<apollo>"):
        """Compile AST node to bytecode"""

        if node.node_type == ASTNodeType.MODULE:
            for child in node.children:
                self._compile_node(child, builder, filename)

        elif node.node_type == ASTNodeType.IMPORT:
            # Import is handled at runtime - just record the module name
            for mod_name in node.value:
                # Store module reference (VM will resolve it)
                builder.add(OpCode.IMPORT_NAME, mod_name)

        elif node.node_type == ASTNodeType.FUNCTION:
            self._compile_function(node, builder)

        elif node.node_type == ASTNodeType.VARIABLE:
            self._compile_variable(node, builder)

        elif node.node_type == ASTNodeType.IF:
            self._compile_if(node, builder)

        elif node.node_type == ASTNodeType.FOR:
            self._compile_for(node, builder)

        elif node.node_type == ASTNodeType.WHILE:
            self._compile_while(node, builder)

        elif node.node_type == ASTNodeType.RETURN:
            self._compile_return(node, builder)

        elif node.node_type == ASTNodeType.BLOCK:
            for child in node.children:
                self._compile_node(child, builder, filename)

        elif node.node_type == ASTNodeType.EXPRESSION_STMT:
            self._compile_expression_stmt(node, builder)

        elif node.node_type in (ASTNodeType.LITERAL, ASTNodeType.IDENTIFIER,
                                 ASTNodeType.BINARY_OP, ASTNodeType.CALL,
                                 ASTNodeType.MEMBER_ACCESS, ASTNodeType.ARRAY,
                                 ASTNodeType.DICT, ASTNodeType.INDEX,
                                 ASTNodeType.UNARY_OP, ASTNodeType.PIPELINE):
            self._compile_expression(node, builder)

        elif node.node_type in (ASTNodeType.TRY_CATCH, ASTNodeType.PARALLEL,
                                 ASTNodeType.EMIT, ASTNodeType.AWAIT):
            # Best-effort: compile body/expression, ignore control semantics for now
            for child in node.children:
                if child:
                    self._compile_node(child, builder, filename)

    def _compile_function(self, node, builder):
        """Compile function definition"""
        func_name = node.value
        params = node.meta.get("params", [])
        body = node.meta.get("body")

        # Create new code builder for function
        func_builder = OpcodeBuilder()

        # Set up parameters
        for i, param in enumerate(params):
            func_builder.add(OpCode.STORE_VAR, param["name"])

        # Compile body
        self._compile_node(body, func_builder)

        # Ensure return at end
        func_builder.add(OpCode.RETURN)

        # Build function code
        func_code = func_builder.build(func_name)
        self.function_codes[func_name] = func_code

        # Store function in main code
        main_idx = builder.const_index(func_code)
        builder.add(OpCode.LOAD_CONST, main_idx)
        builder.add(OpCode.STORE_GLOBAL, func_name)

    def _compile_variable(self, node, builder):
        """Compile variable declaration"""
        # Compile value
        self._compile_node(node.children[0], builder)
        # Store
        builder.add(OpCode.STORE_VAR, node.value)

    def _compile_if(self, node, builder):
        """Compile if statement"""
        else_lbl = self._new_label("else")
        end_lbl = self._new_label("end")

        # Compile condition
        self._compile_node(node.value, builder)
        builder.jump_if_false(else_lbl)

        # Compile then block
        self._compile_node(node.children[0], builder)
        builder.jump(end_lbl)

        # Compile else block if exists
        builder.label(else_lbl)
        else_block = node.meta.get("else")
        if else_block:
            self._compile_node(else_block, builder)

        builder.label(end_lbl)

    def _compile_for(self, node, builder):
        """Compile for loop using GET_ITER / FOR_ITER"""
        var_name = node.value
        iterable = node.children[0]
        body = node.children[1]

        start_lbl = self._new_label("for_start")
        end_lbl = self._new_label("for_end")

        # Compile iterable and convert to Python iterator
        self._compile_node(iterable, builder)
        builder.add(OpCode.GET_ITER)

        # Loop: FOR_ITER pushes next value or jumps to end
        builder.label(start_lbl)
        builder.jump_for_iter(end_lbl)

        # Store loop variable
        builder.add(OpCode.STORE_VAR, var_name)

        # Compile body
        self._compile_node(body, builder)

        # Jump back to FOR_ITER
        builder.jump(start_lbl)
        builder.label(end_lbl)

    def _compile_while(self, node, builder):
        """Compile while loop"""
        condition = node.value
        body = node.children[0]

        start_lbl = self._new_label("while_start")
        end_lbl = self._new_label("while_end")

        builder.label(start_lbl)
        self._compile_node(condition, builder)
        builder.jump_if_false(end_lbl)
        self._compile_node(body, builder)
        builder.jump(start_lbl)
        builder.label(end_lbl)

    def _compile_return(self, node, builder):
        """Compile return statement"""
        if node.value:
            self._compile_node(node.value, builder)
        else:
            # Push None
            builder.add(OpCode.LOAD_CONST, builder.const_index(None))
        builder.add(OpCode.RETURN)

    def _compile_expression_stmt(self, node, builder):
        """Compile expression statement (discard result)"""
        self._compile_node(node.children[0], builder)
        builder.add(OpCode.POP)

    def _compile_expression(self, node, builder):
        """Compile expression"""
        if node.node_type == ASTNodeType.LITERAL:
            idx = builder.const_index(node.value)
            builder.add(OpCode.LOAD_CONST, idx)

        elif node.node_type == ASTNodeType.IDENTIFIER:
            builder.add(OpCode.LOAD_VAR, node.value)

        elif node.node_type == ASTNodeType.BINARY_OP:
            self._compile_binary_op(node, builder)

        elif node.node_type == ASTNodeType.CALL:
            self._compile_call(node, builder)

        elif node.node_type == ASTNodeType.MEMBER_ACCESS:
            self._compile_member_access(node, builder)

        elif node.node_type == ASTNodeType.ARRAY:
            self._compile_array(node, builder)

        elif node.node_type == ASTNodeType.DICT:
            self._compile_dict(node, builder)

        elif node.node_type == ASTNodeType.INDEX:
            self._compile_index(node, builder)

        elif node.node_type == ASTNodeType.UNARY_OP:
            self._compile_unary_op(node, builder)

        elif node.node_type == ASTNodeType.PIPELINE:
            self._compile_pipeline(node, builder)

    def _compile_binary_op(self, node, builder):
        """Compile binary operation"""
        # Assignment is a special case — always leaves None on stack for EXPRESSION_STMT's POP
        if node.value == "=":
            self._compile_node(node.children[1], builder)  # Compile RHS
            lhs = node.children[0]
            if lhs.node_type == ASTNodeType.IDENTIFIER:
                builder.add(OpCode.STORE_VAR, lhs.value)
            elif lhs.node_type == ASTNodeType.INDEX:
                # Stack: [rhs_value]; need [rhs_value, container, index] for STORE_SUBSCR
                self._compile_node(lhs.children[0], builder)  # container
                self._compile_node(lhs.value, builder)         # index
                builder.add(OpCode.STORE_SUBSCR)
            elif lhs.node_type == ASTNodeType.MEMBER_ACCESS:
                # obj.attr = value  (not fully implemented, treat as no-op store)
                builder.add(OpCode.POP)  # discard value
            # Push None so EXPRESSION_STMT's POP has something to consume
            builder.add(OpCode.LOAD_CONST, builder.const_index(None))
            return

        self._compile_node(node.children[0], builder)
        self._compile_node(node.children[1], builder)

        op_map = {
            "+": OpCode.ADD, "-": OpCode.SUB, "*": OpCode.MUL,
            "/": OpCode.DIV, "%": OpCode.MOD, "==": OpCode.EQ,
            "!=": OpCode.NEQ, "<": OpCode.LT, ">": OpCode.GT,
            "<=": OpCode.LTE, ">=": OpCode.GTE, "&&": OpCode.AND,
            "||": OpCode.OR,
        }
        op = op_map.get(node.value)
        if op:
            builder.add(op)
        else:
            raise ValueError(f"Unknown binary operator: {node.value!r}")

    def _compile_call(self, node, builder):
        """Compile function call"""
        # node.value holds the function/member, node.children holds args
        func = node.value

        # Handle member access specially
        if hasattr(func, 'node_type') and func.node_type == ASTNodeType.MEMBER_ACCESS:
            self._compile_member_call(node, builder, func)
            return

        # Compile function
        self._compile_node(func, builder)

        # Compile arguments
        arg_count = len(node.children)
        for arg in node.children:
            self._compile_node(arg, builder)

        builder.add(OpCode.CALL, arg_count)

    def _compile_member_call(self, node, builder, func_node):
        """Compile method call (obj.method())"""
        obj = func_node.children[0]
        method_name = func_node.value

        # Compile object
        self._compile_node(obj, builder)

        # Compile arguments
        arg_count = len(node.children)
        for arg in node.children:
            self._compile_node(arg, builder)

        # Push method name
        idx = builder.const_index(method_name)
        builder.add(OpCode.LOAD_CONST, idx)

        # Call method
        builder.add(OpCode.CALL_METHOD, arg_count + 1)

    def _compile_member_access(self, node, builder):
        """Compile attribute access"""
        self._compile_node(node.children[0], builder)
        idx = builder.const_index(node.value)
        builder.add(OpCode.LOAD_CONST, idx)
        builder.add(OpCode.LOAD_ATTR)

    def _compile_array(self, node, builder):
        """Compile array literal — elements are in node.value"""
        elements = node.value if isinstance(node.value, list) else node.children
        for elem in elements:
            self._compile_node(elem, builder)
        builder.add(OpCode.BUILD_LIST, len(elements))

    def _compile_dict(self, node, builder):
        """Compile dict literal — pairs are in node.value as [{"key": k, "value": v}]"""
        pairs = node.value if isinstance(node.value, list) else []
        for pair in pairs:
            key_idx = builder.const_index(pair["key"])
            builder.add(OpCode.LOAD_CONST, key_idx)
            self._compile_node(pair["value"], builder)
        builder.add(OpCode.BUILD_DICT, len(pairs))

    def _compile_index(self, node, builder):
        """Compile index access: node.children[0] is container, node.value is index expr"""
        self._compile_node(node.children[0], builder)
        self._compile_node(node.value, builder)
        builder.add(OpCode.SUBSCR)

    def _compile_unary_op(self, node, builder):
        """Compile unary operation"""
        self._compile_node(node.children[0], builder)
        op_map = {
            "-": OpCode.NEG,
            "!": OpCode.NOT,
            "not": OpCode.NOT,
        }
        op = op_map.get(node.value, OpCode.NEG)
        builder.add(op)

    def _compile_pipeline(self, node, builder):
        """Compile pipeline (|>) — pass left as first arg to right"""
        self._compile_node(node.children[0], builder)
        right = node.children[1]
        if right.node_type == ASTNodeType.CALL:
            # Push extra first arg (the piped value) before function call
            # Rewrite: piped_val |> f(a, b) => f(piped_val, a, b)
            self._compile_node(right.value, builder)  # push function
            # piped value is already on stack below function — swap
            builder.add(OpCode.SWAP)
            for arg in right.children:
                self._compile_node(arg, builder)
            builder.add(OpCode.CALL, len(right.children) + 1)
        else:
            self._compile_node(right, builder)
            builder.add(OpCode.CALL, 1)


class Optimizer:
    """
    Bytecode Optimizer

    Implements:
    - Constant folding
    - Dead code elimination
    - Peephole optimization
    """

    def __init__(self):
        self.enabled = True

    def optimize(self, code: CodeObject) -> CodeObject:
        """Apply optimizations to code"""
        if not self.enabled:
            return code

        code = self.constant_folding(code)
        code = self.peephole(code)
        code = self.dead_code_elimination(code)

        return code

    def constant_folding(self, code: CodeObject) -> CodeObject:
        """Fold constant expressions at compile time"""
        new_instructions = []
        i = 0

        while i < len(code.instructions):
            instr = code.instructions[i]

            # Look for LOAD_CONST followed by LOAD_CONST then arithmetic
            if instr.opcode == OpCode.LOAD_CONST:
                if (i + 2 < len(code.instructions) and
                    code.instructions[i + 1].opcode == OpCode.LOAD_CONST and
                    code.instructions[i + 2].opcode in (OpCode.ADD, OpCode.SUB,
                                                         OpCode.MUL, OpCode.DIV)):

                    val1 = code.constants[instr.arg]
                    val2 = code.constants[code.instructions[i + 1].arg]
                    op = code.instructions[i + 2].opcode

                    # Fold
                    if op == OpCode.ADD:
                        result = val1 + val2
                    elif op == OpCode.SUB:
                        result = val1 - val2
                    elif op == OpCode.MUL:
                        result = val1 * val2
                    elif op == OpCode.DIV:
                        result = val1 / val2

                    new_instructions.append(Instruction(OpCode.LOAD_CONST,
                                                        len(code.constants)))
                    code.constants = code.constants + (result,)
                    i += 3
                    continue

            new_instructions.append(instr)
            i += 1

        code.instructions = new_instructions
        return code

    def peephole(self, code: CodeObject) -> CodeObject:
        """Peephole optimization"""
        new_instructions = []

        for i, instr in enumerate(code.instructions):
            # Remove NOP
            if instr.opcode == OpCode.NOP:
                continue

            # Remove PUSH x followed by POP
            if instr.opcode == OpCode.PUSH:
                if (i + 1 < len(code.instructions) and
                    code.instructions[i + 1].opcode == OpCode.POP):
                    continue

            new_instructions.append(instr)

        code.instructions = new_instructions
        return code

    def dead_code_elimination(self, code: CodeObject) -> CodeObject:
        """Remove unreachable code"""
        # Simple: remove code after HALT
        new_instructions = []
        halted = False

        for instr in code.instructions:
            if halted:
                continue
            if instr.opcode == OpCode.HALT:
                halted = True
            new_instructions.append(instr)

        code.instructions = new_instructions
        return code


class Instruction:
    """Minimal instruction class for optimizer"""
    def __init__(self, opcode, arg=None):
        self.opcode = opcode
        self.arg = arg
