"""
APOLLO Bytecode Instruction Set (Opcode Definitions)
Defines all VM operations for the stack-based virtual machine
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Optional


class OpCode(Enum):
    """
    APOLLO Virtual Machine Opcodes

    Stack operations:    PUSH, POP, DUP, SWAP
    Load/Store:          LOAD_CONST, LOAD_VAR, STORE_VAR, LOAD_GLOBAL, STORE_GLOBAL
    Arithmetic:          ADD, SUB, MUL, DIV, MOD, POW
    Comparison:          EQ, NEQ, LT, GT, LTE, GTE
    Logic:               NOT, AND, OR
    Control Flow:        JUMP, JUMP_IF_FALSE, JUMP_IF_TRUE, LOOP_START, LOOP_END
    Functions:           CALL, CALL_METHOD, RETURN, CLOSURE
    Data:               BUILD_LIST, BUILD_DICT, BUILD_TUPLE, SUBSCR
    Import:             IMPORT_FROM, IMPORT_NAME
    Special:            HALT, PRINT, NOP
    """

    # Control flow
    HALT = auto()           # Stop execution
    NOP = auto()            # No operation

    # Stack manipulation
    PUSH = auto()           # Push value onto stack
    POP = auto()            # Pop top value
    DUP = auto()            # Duplicate top of stack
    SWAP = auto()           # Swap top two values

    # Load/Store
    LOAD_CONST = auto()     # Load constant from pool
    LOAD_VAR = auto()       # Load local variable
    STORE_VAR = auto()      # Store local variable
    LOAD_GLOBAL = auto()    # Load global variable
    STORE_GLOBAL = auto()   # Store global variable
    LOAD_FAST = auto()      # Load fast local (function arg)
    STORE_FAST = auto()     # Store fast local

    # Arithmetic
    ADD = auto()            # Addition
    SUB = auto()            # Subtraction
    MUL = auto()            # Multiplication
    DIV = auto()            # Division
    MOD = auto()            # Modulo
    POW = auto()            # Power
    NEG = auto()            # Negate

    # Comparison
    EQ = auto()             # Equal
    NEQ = auto()            # Not equal
    LT = auto()             # Less than
    GT = auto()             # Greater than
    LTE = auto()            # Less than or equal
    GTE = auto()            # Greater than or equal

    # Logic
    NOT = auto()            # Logical not
    AND = auto()            # Logical and
    OR = auto()             # Logical or

    # Control flow
    JUMP = auto()           # Unconditional jump
    JUMP_IF_FALSE = auto()  # Jump if top is false
    JUMP_IF_TRUE = auto()   # Jump if top is true
    LOOP_START = auto()     # Mark loop start
    LOOP_END = auto()       # Jump back if condition
    FOR_ITER = auto()       # Iterator protocol

    # Functions
    CALL = auto()           # Call function
    CALL_METHOD = auto()    # Call method
    RETURN = auto()         # Return from function
    CLOSURE = auto()        # Create closure
    GET_FUNCTION = auto()   # Load function object

    # Data structures
    BUILD_LIST = auto()     # Build list from stack
    BUILD_DICT = auto()     # Build dict from stack
    BUILD_TUPLE = auto()    # Build tuple from stack
    SUBSCR = auto()         # Subscript (index access)
    STORE_SUBSCR = auto()   # Store subscript

    # Attributes
    LOAD_ATTR = auto()      # Load attribute
    STORE_ATTR = auto()     # Store attribute

    # Imports
    IMPORT_NAME = auto()    # Import module
    IMPORT_FROM = auto()    # Import from module

    # Special
    PRINT = auto()          # Print top of stack
    MAKE_CELL = auto()      # Create cell for closure

    # Iteration (GET_ITER added here; FOR_ITER already defined above)
    GET_ITER = auto()       # Convert top of stack to Python iterator

    # Security primitives
    SYSCALL = auto()        # System call
    NATIVE_CALL = auto()    # Native function call


@dataclass
class Instruction:
    """Single bytecode instruction"""
    opcode: OpCode
    arg: Optional[Any] = None
    operand: Optional[int] = None

    def __repr__(self):
        if self.arg is not None:
            return f"{self.opcode.name} {self.arg}"
        if self.operand is not None:
            return f"{self.opcode.name} {self.operand}"
        return self.opcode.name


@dataclass
class CodeObject:
    """Compiled code object (like Python's code object)"""
    name: str
    argcount: int
    locals_count: int
    globals_count: int
    instructions: list
    constants: tuple
    names: tuple
    source: str = ""
    filename: str = "<apollo>"

    def __repr__(self):
        return f"<CodeObject {self.name} at {self.filename}>"


class OpcodeBuilder:
    """Helper for building bytecode sequences"""

    def __init__(self):
        self.instructions = []
        self.constants = []
        self.names = []
        self.labels = {}
        self.fixups = []

    def add(self, opcode: OpCode, arg=None):
        self.instructions.append(Instruction(opcode, arg))
        return self

    def const_index(self, value):
        """Add constant and return index"""
        idx = len(self.constants)
        self.constants.append(value)
        return idx

    def name_index(self, name):
        """Add name and return index"""
        idx = len(self.names)
        self.names.append(name)
        return idx

    def label(self, name):
        """Mark current position with label"""
        self.labels[name] = len(self.instructions)
        return self

    def jump(self, name):
        """Add jump to label (fixup later)"""
        idx = len(self.instructions)
        self.instructions.append(Instruction(OpCode.JUMP, None))
        self.fixups.append((idx, name))
        return self

    def jump_if_false(self, name):
        """Add conditional jump"""
        idx = len(self.instructions)
        self.instructions.append(Instruction(OpCode.JUMP_IF_FALSE, None))
        self.fixups.append((idx, name))
        return self

    def jump_for_iter(self, name):
        """Add FOR_ITER instruction with forward jump"""
        idx = len(self.instructions)
        self.instructions.append(Instruction(OpCode.FOR_ITER, None))
        self.fixups.append((idx, name))
        return self

    def resolve_fixups(self):
        """Resolve forward references, preserving original opcode type"""
        for idx, label in self.fixups:
            target = self.labels.get(label, len(self.instructions))
            orig_opcode = self.instructions[idx].opcode
            self.instructions[idx] = Instruction(orig_opcode, target)
        self.fixups = []

    def build(self, name="<chunk>") -> CodeObject:
        """Build final code object"""
        self.resolve_fixups()
        return CodeObject(
            name=name,
            argcount=0,
            locals_count=10,
            globals_count=10,
            instructions=self.instructions,
            constants=tuple(self.constants),
            names=tuple(self.names)
        )
