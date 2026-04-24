"""
APOLLO Language Parser
Builds an Abstract Syntax Tree (AST) from tokens
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum, auto
from lexer import Token, TokenType, tokenize


class ASTNodeType(Enum):
    # Declarations
    MODULE = auto()
    FUNCTION = auto()
    ASYNC_FUNCTION = auto()
    VARIABLE = auto()
    CONSTANT = auto()
    IMPORT = auto()
    EXPORT = auto()
    EXTERN = auto()

    # Control Flow
    IF = auto()
    MATCH = auto()
    FOR = auto()
    WHILE = auto()
    RETURN = auto()
    AWAIT = auto()
    PARALLEL = auto()
    EMIT = auto()

    # Expressions
    IDENTIFIER = auto()
    LITERAL = auto()
    BINARY_OP = auto()
    UNARY_OP = auto()
    PIPELINE = auto()
    CALL = auto()
    MEMBER_ACCESS = auto()
    INDEX = auto()
    LAMBDA = auto()
    ARRAY = auto()
    DICT = auto()
    RANGE = auto()

    # Types
    RESULT = auto()
    OPTION = auto()
    STREAM = auto()

    # Statements
    EXPRESSION_STMT = auto()
    BLOCK = auto()
    TRY_CATCH = auto()
    THROW = auto()


@dataclass
class ASTNode:
    node_type: ASTNodeType
    value: Any = None
    children: List['ASTNode'] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"ASTNode({self.node_type.name}, {self.value!r})"


@dataclass
class Span:
    """Track source location for error reporting"""
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class ParseError(Exception):
    """Exception raised for syntax errors"""
    def __init__(self, message: str, token: Token):
        super().__init__(f"Line {token.line}, Column {token.column}: {message}")
        self.token = token


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0] if tokens else None

    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look at token at current position + offset"""
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return None
        return self.tokens[idx]

    def advance(self) -> Optional[Token]:
        """Move to next token and return current"""
        token = self.current_token
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type, raise error if not found"""
        if self.current_token and self.current_token.type == token_type:
            return self.advance()
        raise ParseError(
            f"Expected {token_type.name}, got {self.current_token.type.name if self.current_token else 'EOF'}",
            self.current_token or self.tokens[-1]
        )

    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types"""
        return self.current_token and self.current_token.type in token_types

    def skip(self, *token_types: TokenType):
        """Skip tokens of given types"""
        while self.match(*token_types):
            self.advance()

    def parse(self) -> ASTNode:
        """Parse the entire token stream into an AST"""
        return self.parse_module()

    def parse_module(self) -> ASTNode:
        """Parse a module (file)"""
        node = ASTNode(ASTNodeType.MODULE)
        statements = []

        while self.current_token and not self.match(TokenType.EOF):
            if self.match(TokenType.COMMENT, TokenType.INDENT, TokenType.DEDENT, TokenType.NEWLINE):
                self.advance()
                continue

            if self.match(TokenType.IMPORT):
                statements.append(self.parse_import())
            elif self.match(TokenType.EXPORT):
                statements.append(self.parse_export())
            elif self.match(TokenType.FN, TokenType.ASYNC):
                statements.append(self.parse_function())
            elif self.match(TokenType.EXTERN):
                statements.append(self.parse_extern())
            elif self.match(TokenType.MODULE):
                statements.append(self.parse_module_decl())
            elif self.match(TokenType.LET, TokenType.VAR, TokenType.CONST):
                statements.append(self.parse_variable())
            else:
                statements.append(self.parse_statement())

        node.children = statements
        return node

    def parse_import(self) -> ASTNode:
        """Parse import statement"""
        token = self.advance()  # consume 'import'
        imports = []

        while self.current_token and not self.match(TokenType.NEWLINE, TokenType.EOF):
            if self.match(TokenType.IDENTIFIER):
                path = self.advance().value
                imports.append(path)
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break

        return ASTNode(ASTNodeType.IMPORT, imports)

    def parse_export(self) -> ASTNode:
        """Parse export statement"""
        token = self.advance()  # consume 'export'
        return ASTNode(ASTNodeType.EXPORT, self.parse_expression())

    def parse_extern(self) -> ASTNode:
        """Parse extern block for FFI"""
        token = self.advance()  # consume 'extern'
        target = None

        if self.match(TokenType.IDENTIFIER):
            target = self.advance().value

        self.expect(TokenType.LBRACE)
        functions = []

        while self.current_token and not self.match(TokenType.RBRACE, TokenType.EOF):
            if self.match(TokenType.IDENTIFIER):
                functions.append(self.advance().value)
            self.skip(TokenType.COMMA, TokenType.NEWLINE)

        self.expect(TokenType.RBRACE)
        return ASTNode(ASTNodeType.EXTERN, {"target": target, "functions": functions})

    def parse_module_decl(self) -> ASTNode:
        """Parse module declaration"""
        token = self.advance()  # consume 'module'
        name = self.expect(TokenType.IDENTIFIER).value

        self.expect(TokenType.LBRACE)
        body = []

        while self.current_token and not self.match(TokenType.RBRACE, TokenType.EOF):
            body.append(self.parse_statement())

        self.expect(TokenType.RBRACE)
        return ASTNode(ASTNodeType.MODULE, name, body)

    def parse_function(self) -> ASTNode:
        """Parse function declaration"""
        is_async = bool(self.match(TokenType.ASYNC))
        if is_async:
            self.advance()

        self.expect(TokenType.FN)
        name = self.expect(TokenType.IDENTIFIER).value

        # Parse parameters
        self.expect(TokenType.LPAREN)
        params = []

        while self.current_token and not self.match(TokenType.RPAREN, TokenType.EOF):
            if self.match(TokenType.IDENTIFIER):
                param_name = self.advance().value
                param_type = None

                if self.match(TokenType.COLON):
                    self.advance()
                    if self.match(TokenType.IDENTIFIER):
                        param_type = self.advance().value

                params.append({"name": param_name, "type": param_type})

            self.skip(TokenType.COMMA)

        self.expect(TokenType.RPAREN)

        # Parse return type
        return_type = None
        if self.match(TokenType.ARROW):
            self.advance()
            return_type = self.parse_type_annotation()

        # Parse body
        body = self.parse_block()

        node_type = ASTNodeType.ASYNC_FUNCTION if is_async else ASTNodeType.FUNCTION
        return ASTNode(
            node_type,
            name,
            [],
            {"params": params, "return_type": return_type, "body": body}
        )

    def parse_type_annotation(self) -> ASTNode:
        """Parse type annotation like Result<T, E> or Stream<Finding>"""
        if self.match(TokenType.IDENTIFIER):
            base_type = self.advance().value

            if self.match(TokenType.LT):
                self.advance()
                type_params = []

                while self.current_token and not self.match(TokenType.GT, TokenType.EOF):
                    type_params.append(self.parse_type_annotation())
                    self.skip(TokenType.COMMA)

                self.expect(TokenType.GT)
                return ASTNode(ASTNodeType.IDENTIFIER, base_type, type_params)

            return ASTNode(ASTNodeType.IDENTIFIER, base_type)

        return ASTNode(ASTNodeType.IDENTIFIER, "unknown")

    def parse_variable(self) -> ASTNode:
        """Parse variable declaration"""
        if self.match(TokenType.LET):
            mutability = "immutable"
        elif self.match(TokenType.VAR):
            mutability = "mutable"
        elif self.match(TokenType.CONST):
            mutability = "constant"
        else:
            raise ParseError("Expected variable declaration", self.current_token)

        self.advance()
        name = self.expect(TokenType.IDENTIFIER).value

        var_type = None
        if self.match(TokenType.COLON):
            self.advance()
            var_type = self.parse_type_annotation()

        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()

        return ASTNode(
            ASTNodeType.VARIABLE,
            name,
            [value],
            {"mutability": mutability, "type": var_type}
        )

    def parse_block(self) -> ASTNode:
        """Parse a block of statements"""
        if self.match(TokenType.LBRACE):
            self.advance()
        elif self.match(TokenType.INDENT):
            self.advance()
        else:
            # Single expression
            return ASTNode(ASTNodeType.BLOCK, [self.parse_expression()])

        statements = []
        while self.current_token and not self.match(TokenType.RBRACE, TokenType.EOF):
            if self.match(TokenType.DEDENT, TokenType.INDENT, TokenType.NEWLINE, TokenType.COMMENT):
                self.advance()
                continue
            statements.append(self.parse_statement())

        if self.match(TokenType.RBRACE):
            self.advance()
        if self.match(TokenType.DEDENT):
            self.advance()

        return ASTNode(ASTNodeType.BLOCK, None, statements)

    def parse_statement(self) -> ASTNode:
        """Parse a single statement"""
        if self.match(TokenType.LET, TokenType.VAR, TokenType.CONST):
            return self.parse_variable()

        if self.match(TokenType.IF):
            return self.parse_if()

        if self.match(TokenType.MATCH):
            return self.parse_match()

        if self.match(TokenType.FOR):
            return self.parse_for()

        if self.match(TokenType.WHILE):
            return self.parse_while()

        if self.match(TokenType.RETURN):
            return self.parse_return()

        if self.match(TokenType.AWAIT):
            return self.parse_await()

        if self.match(TokenType.PARALLEL):
            return self.parse_parallel()

        if self.match(TokenType.EMIT):
            return self.parse_emit()

        if self.match(TokenType.TRY):
            return self.parse_try_catch()

        if self.match(TokenType.THROW):
            return self.parse_throw()

        if self.match(TokenType.FN):
            return self.parse_function()

        # Expression statement
        expr = self.parse_expression()
        return ASTNode(ASTNodeType.EXPRESSION_STMT, None, [expr])

    def parse_if(self) -> ASTNode:
        """Parse if/elif/else statement"""
        self.expect(TokenType.IF)
        condition = self.parse_expression()
        then_block = self.parse_block()

        elif_blocks = []
        else_block = None

        while self.match(TokenType.ELIF):
            self.advance()
            elif_condition = self.parse_expression()
            elif_block = self.parse_block()
            elif_blocks.append((elif_condition, elif_block))

        if self.match(TokenType.ELSE):
            self.advance()
            else_block = self.parse_block()

        return ASTNode(
            ASTNodeType.IF,
            condition,
            [then_block] + [b for _, b in elif_blocks] + ([else_block] if else_block else []),
            {"elif": elif_blocks, "else": else_block}
        )

    def parse_match(self) -> ASTNode:
        """Parse match expression (pattern matching)"""
        self.expect(TokenType.MATCH)
        subject = self.parse_expression()

        self.expect(TokenType.LBRACE)
        arms = []

        while self.current_token and not self.match(TokenType.RBRACE, TokenType.EOF):
            self.skip(TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.COMMENT)
            if self.match(TokenType.RBRACE, TokenType.EOF):
                break
            pattern = self.parse_pattern()
            self.expect(TokenType.FAT_ARROW)
            result = self.parse_expression()
            arms.append({"pattern": pattern, "result": result})
            self.skip(TokenType.COMMA, TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT)

        self.expect(TokenType.RBRACE)
        return ASTNode(ASTNodeType.MATCH, subject, arms)

    def parse_pattern(self) -> ASTNode:
        """Parse match pattern"""
        if self.match(TokenType.IDENTIFIER):
            return ASTNode(ASTNodeType.IDENTIFIER, self.advance().value)

        if self.match(TokenType.STRING, TokenType.INTEGER, TokenType.FLOAT, TokenType.BOOLEAN):
            tok = self.advance()
            if tok.type == TokenType.INTEGER:
                return ASTNode(ASTNodeType.LITERAL, int(tok.value))
            if tok.type == TokenType.FLOAT:
                return ASTNode(ASTNodeType.LITERAL, float(tok.value))
            if tok.type == TokenType.BOOLEAN:
                return ASTNode(ASTNodeType.LITERAL, tok.value == "true")
            return ASTNode(ASTNodeType.LITERAL, tok.value)

        if self.match(TokenType.OR):  # _ wildcard
            self.advance()
            return ASTNode(ASTNodeType.IDENTIFIER, "_")

        # Default: expression as pattern
        return self.parse_expression()

    def parse_for(self) -> ASTNode:
        """Parse for loop"""
        self.expect(TokenType.FOR)
        var_name = self.expect(TokenType.IDENTIFIER).value

        self.expect(TokenType.IN)
        iterable = self.parse_expression()
        body = self.parse_block()

        return ASTNode(
            ASTNodeType.FOR,
            var_name,
            [iterable, body],
            {"iterable": iterable}
        )

    def parse_while(self) -> ASTNode:
        """Parse while loop"""
        self.expect(TokenType.WHILE)
        condition = self.parse_expression()
        body = self.parse_block()

        return ASTNode(ASTNodeType.WHILE, condition, [body])

    def parse_return(self) -> ASTNode:
        """Parse return statement"""
        self.expect(TokenType.RETURN)

        if self.current_token and not self.match(TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF, TokenType.SEMICOLON):
            value = self.parse_expression()
            return ASTNode(ASTNodeType.RETURN, value)

        return ASTNode(ASTNodeType.RETURN, None)

    def parse_await(self) -> ASTNode:
        """Parse await expression"""
        self.expect(TokenType.AWAIT)
        expr = self.parse_expression()
        return ASTNode(ASTNodeType.AWAIT, expr)

    def parse_parallel(self) -> ASTNode:
        """Parse parallel block"""
        self.expect(TokenType.PARALLEL)
        body = self.parse_block()
        return ASTNode(ASTNodeType.PARALLEL, body)

    def parse_emit(self) -> ASTNode:
        """Parse emit statement (for streams)"""
        self.expect(TokenType.EMIT)
        expr = self.parse_expression()
        return ASTNode(ASTNodeType.EMIT, expr)

    def parse_try_catch(self) -> ASTNode:
        """Parse try/catch block"""
        self.expect(TokenType.TRY)
        try_block = self.parse_block()

        catch_var = None
        catch_block = None

        if self.match(TokenType.CATCH):
            self.advance()
            if self.match(TokenType.LPAREN):
                self.advance()
                catch_var = self.expect(TokenType.IDENTIFIER).value
                self.expect(TokenType.RPAREN)
            catch_block = self.parse_block()

        return ASTNode(
            ASTNodeType.TRY_CATCH,
            try_block,
            [catch_block] if catch_block else [],
            {"catch_var": catch_var}
        )

    def parse_throw(self) -> ASTNode:
        """Parse throw statement"""
        self.expect(TokenType.THROW)
        expr = self.parse_expression()
        return ASTNode(ASTNodeType.THROW, expr)

    def parse_expression(self) -> ASTNode:
        """Parse expression with precedence"""
        return self.parse_pipeline()

    def parse_pipeline(self) -> ASTNode:
        """Parse pipeline expression (|> operator)"""
        expr = self.parse_assignment()

        while self.match(TokenType.PIPE):
            self.advance()
            next_expr = self.parse_assignment()

            # Lambda handling for pipeline
            if next_expr.node_type == ASTNodeType.CALL:
                expr = ASTNode(ASTNodeType.PIPELINE, None, [expr, next_expr])
            else:
                expr = ASTNode(ASTNodeType.PIPELINE, None, [expr, next_expr])

        return expr

    def parse_assignment(self) -> ASTNode:
        """Parse assignment expression"""
        expr = self.parse_or()

        if self.match(TokenType.ASSIGN):
            self.advance()
            value = self.parse_assignment()
            return ASTNode(ASTNodeType.BINARY_OP, "=", [expr, value])

        return expr

    def parse_or(self) -> ASTNode:
        """Parse logical OR"""
        expr = self.parse_and()

        while self.match(TokenType.OR):
            self.advance()
            right = self.parse_and()
            expr = ASTNode(ASTNodeType.BINARY_OP, "||", [expr, right])

        return expr

    def parse_and(self) -> ASTNode:
        """Parse logical AND"""
        expr = self.parse_equality()

        while self.match(TokenType.AND):
            self.advance()
            right = self.parse_equality()
            expr = ASTNode(ASTNodeType.BINARY_OP, "&&", [expr, right])

        return expr

    def parse_equality(self) -> ASTNode:
        """Parse equality operators"""
        expr = self.parse_comparison()

        while self.match(TokenType.EQ, TokenType.NEQ):
            op = self.advance().value
            right = self.parse_comparison()
            expr = ASTNode(ASTNodeType.BINARY_OP, op, [expr, right])

        return expr

    def parse_comparison(self) -> ASTNode:
        """Parse comparison operators"""
        expr = self.parse_additive()

        while self.match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE):
            op = self.advance().value
            right = self.parse_additive()
            expr = ASTNode(ASTNodeType.BINARY_OP, op, [expr, right])

        return expr

    def parse_additive(self) -> ASTNode:
        """Parse additive operators"""
        expr = self.parse_multiplicative()

        while self.match(TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_multiplicative()
            expr = ASTNode(ASTNodeType.BINARY_OP, op, [expr, right])

        return expr

    def parse_multiplicative(self) -> ASTNode:
        """Parse multiplicative operators"""
        expr = self.parse_unary()

        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self.advance().value
            right = self.parse_unary()
            expr = ASTNode(ASTNodeType.BINARY_OP, op, [expr, right])

        return expr

    def parse_unary(self) -> ASTNode:
        """Parse unary operators"""
        if self.match(TokenType.NOT, TokenType.MINUS):
            op = self.advance().value
            operand = self.parse_unary()
            return ASTNode(ASTNodeType.UNARY_OP, op, [operand])

        if self.match(TokenType.QUESTION):
            self.advance()
            operand = self.parse_unary()
            return ASTNode(ASTNodeType.UNARY_OP, "?", [operand])

        return self.parse_postfix()

    def parse_postfix(self) -> ASTNode:
        """Parse postfix operators (call, member access, index)"""
        expr = self.parse_primary()

        while True:
            if self.match(TokenType.LPAREN):
                self.advance()
                args = []

                while self.current_token and not self.match(TokenType.RPAREN, TokenType.EOF):
                    args.append(self.parse_expression())
                    self.skip(TokenType.COMMA)

                self.expect(TokenType.RPAREN)
                expr = ASTNode(ASTNodeType.CALL, expr, args)

            elif self.match(TokenType.DOT):
                self.advance()
                member = self.expect(TokenType.IDENTIFIER).value
                expr = ASTNode(ASTNodeType.MEMBER_ACCESS, member, [expr])

            elif self.match(TokenType.LBRACKET):
                self.advance()
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = ASTNode(ASTNodeType.INDEX, index, [expr])

            elif self.match(TokenType.ARROW):
                # Lambda
                self.advance()
                body = self.parse_expression()
                expr = ASTNode(ASTNodeType.LAMBDA, None, [expr, body])

            else:
                break

        return expr

    def parse_primary(self) -> ASTNode:
        """Parse primary expressions"""
        if self.match(TokenType.IDENTIFIER):
            return ASTNode(ASTNodeType.IDENTIFIER, self.advance().value)

        if self.match(TokenType.STRING):
            return ASTNode(ASTNodeType.LITERAL, self.advance().value, [], {"type": "string"})

        if self.match(TokenType.INTEGER):
            return ASTNode(ASTNodeType.LITERAL, int(self.advance().value), [], {"type": "integer"})

        if self.match(TokenType.FLOAT):
            return ASTNode(ASTNodeType.LITERAL, float(self.advance().value), [], {"type": "float"})

        if self.match(TokenType.BOOLEAN):
            return ASTNode(ASTNodeType.LITERAL, self.advance().value == "true", [], {"type": "boolean"})

        if self.match(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        if self.match(TokenType.LBRACKET):
            return self.parse_array()

        if self.match(TokenType.LBRACE):
            return self.parse_dict()

        if self.match(TokenType.FN):
            return self.parse_lambda()

        # Range operator (..)
        if False:  # Handled in parse_range
            pass

        raise ParseError(f"Unexpected token: {self.current_token}", self.current_token)

    def parse_array(self) -> ASTNode:
        """Parse array literal (single or multi-line)"""
        self.expect(TokenType.LBRACKET)
        elements = []

        while self.current_token and not self.match(TokenType.RBRACKET, TokenType.EOF):
            self.skip(TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT)
            if self.match(TokenType.RBRACKET):
                break
            elements.append(self.parse_expression())
            self.skip(TokenType.COMMA, TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT)

        self.expect(TokenType.RBRACKET)
        return ASTNode(ASTNodeType.ARRAY, elements)

    def parse_dict(self) -> ASTNode:
        """Parse dictionary/object literal (single or multi-line)"""
        self.expect(TokenType.LBRACE)
        pairs = []

        while self.current_token and not self.match(TokenType.RBRACE, TokenType.EOF):
            self.skip(TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT)
            if self.match(TokenType.RBRACE):
                break
            if not self.match(TokenType.IDENTIFIER):
                break
            key = self.advance().value
            self.expect(TokenType.COLON)
            value = self.parse_expression()
            pairs.append({"key": key, "value": value})
            self.skip(TokenType.COMMA, TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT)

        self.expect(TokenType.RBRACE)
        return ASTNode(ASTNodeType.DICT, pairs)

    def parse_lambda(self) -> ASTNode:
        """Parse lambda expression"""
        self.expect(TokenType.FN)

        params = []
        if self.match(TokenType.LPAREN):
            self.advance()
            while self.current_token and not self.match(TokenType.RPAREN, TokenType.EOF):
                params.append(self.expect(TokenType.IDENTIFIER).value)
                self.skip(TokenType.COMMA)
            self.expect(TokenType.RPAREN)

        self.expect(TokenType.ARROW)
        body = self.parse_expression()

        return ASTNode(ASTNodeType.LAMBDA, None, [], {"params": params, "body": body})

    def parse_range(self) -> ASTNode:
        """Parse range expression (e.g., 0..100)"""
        start = self.parse_primary()

        if self.match(TokenType.DOT):
            if self.peek(1) and self.peek(1).type == TokenType.DOT:
                self.advance()
                self.advance()
                end = self.parse_primary()
                return ASTNode(ASTNodeType.RANGE, None, [start, end])

        return start


def parse(source: str) -> ASTNode:
    """Parse APOLLO source code into an AST"""
    tokens = tokenize(source)
    parser = Parser(tokens)
    return parser.parse()


if __name__ == "__main__":
    # Test the parser
    test_code = '''
import scan, report

fn main(args) {
    let target = "192.168.1.1"
    var port = 445

    if port == 80 {
        http.enumerate(target)
    }

    target |> scan.tcp() |> report.save("result.txt")
}
'''

    ast = parse(test_code)
    print(ast)
