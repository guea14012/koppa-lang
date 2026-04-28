"""
KOPPA Language Lexer
Tokenizes KOPPA source code into tokens for parsing
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional
import re


class TokenType(Enum):
    # Literals
    IDENTIFIER = auto()
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()

    # Keywords
    LET = auto()
    VAR = auto()
    CONST = auto()
    FN = auto()
    ASYNC = auto()
    AWAIT = auto()
    RETURN = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    MATCH = auto()
    FOR = auto()
    WHILE = auto()
    IN = auto()
    TRY = auto()
    CATCH = auto()
    THROWS = auto()
    IMPORT = auto()
    EXPORT = auto()
    MODULE = auto()
    EXTERN = auto()
    PARALLEL = auto()
    EMIT = auto()
    DEFAULT = auto()
    THROW = auto()
    BREAK = auto()
    CONTINUE = auto()
    # New keywords
    CLASS = auto()
    SELF = auto()
    NEW = auto()
    IS = auto()
    NOT = auto()
    UNSAFE = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=
    STAR_ASSIGN = auto()    # *=
    SLASH_ASSIGN = auto()   # /=
    PERCENT_ASSIGN = auto() # %=
    PIPE = auto()        # |>
    ARROW = auto()       # ->
    FAT_ARROW = auto()   # =>
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    AND = auto()
    OR = auto()
    QUESTION = auto()    # ? (try operator)
    DOT = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()
    # New operators
    NULL_COALESCE = auto()  # ?:
    OPTIONAL_DOT = auto()   # ?.
    SPREAD = auto()         # ...
    POWER = auto()          # **

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()

    # Byte literal
    BYTES = auto()

    # Bitwise operators
    BAND = auto()    # & (bitwise AND)
    BOR = auto()     # | alone (bitwise OR)
    BXOR = auto()    # ^ (bitwise XOR)
    BNOT = auto()    # ~ (bitwise NOT, unary)
    LSHIFT = auto()  # <<
    RSHIFT = auto()  # >>

    # Special
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    COMMENT = auto()
    EOF = auto()
    ERROR = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    source: str = ""

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"


KEYWORDS = {
    "let": TokenType.LET,
    "var": TokenType.VAR,
    "const": TokenType.CONST,
    "fn": TokenType.FN,
    "async": TokenType.ASYNC,
    "await": TokenType.AWAIT,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "match": TokenType.MATCH,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,
    "in": TokenType.IN,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "throws": TokenType.THROWS,
    "import": TokenType.IMPORT,
    "export": TokenType.EXPORT,
    "module": TokenType.MODULE,
    "extern": TokenType.EXTERN,
    "parallel": TokenType.PARALLEL,
    "emit": TokenType.EMIT,
    "default": TokenType.DEFAULT,
    "throw": TokenType.THROW,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "true": TokenType.BOOLEAN,
    "false": TokenType.BOOLEAN,
    "Ok": TokenType.IDENTIFIER,  # Result types
    "Err": TokenType.IDENTIFIER,
    "Some": TokenType.IDENTIFIER,
    "None": TokenType.IDENTIFIER,
    # New keywords
    "class": TokenType.CLASS,
    "self": TokenType.SELF,
    "new": TokenType.NEW,
    "is": TokenType.IS,
    "not": TokenType.NOT,
    "unsafe": TokenType.UNSAFE,
}


class LexerError(Exception):
    """Exception raised for lexical errors"""
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"Line {line}, Column {column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.indent_stack = [0]

    def peek(self, offset: int = 0) -> Optional[str]:
        """Look at character at current position + offset"""
        idx = self.pos + offset
        if idx >= len(self.source):
            return None
        return self.source[idx]

    def advance(self) -> Optional[str]:
        """Move to next character and return current"""
        if self.pos >= len(self.source):
            return None
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def skip_whitespace(self):
        """Skip horizontal whitespace"""
        while self.peek() in ' \t\r':
            self.advance()

    def skip_comment(self) -> Token:
        """Skip single-line comment"""
        start_line, start_col = self.line, self.column
        self.advance()  # consume #
        value = ""
        while self.peek() and self.peek() != '\n':
            value += self.advance()
        return Token(TokenType.COMMENT, value, start_line, start_col, self.source)

    def skip_block_comment(self) -> Optional[Token]:
        """Skip block comment #{...}#"""
        if self.peek() == '#' and self.peek(1) == '{':
            start_line, start_col = self.line, self.column
            self.advance()  # #
            self.advance()  # {
            value = ""
            while not (self.peek() == '}' and self.peek(1) == '#'):
                if self.peek() is None:
                    raise LexerError("Unterminated block comment", start_line, start_col)
                value += self.advance()
            self.advance()  # }
            self.advance()  # #
            return Token(TokenType.COMMENT, value, start_line, start_col, self.source)
        return None

    def read_string_raw(self, quote: str, start_line: int, start_col: int) -> Token:
        """Read string preserving raw escape sequences for byte literals"""
        if self.peek() == quote and self.peek(1) == quote and self.peek(2) == quote:
            self.advance(); self.advance(); self.advance()
            value = ""
            while not (self.peek() == quote and self.peek(1) == quote and self.peek(2) == quote):
                if self.peek() is None:
                    raise LexerError("Unterminated byte string", start_line, start_col)
                value += self.advance()
            self.advance(); self.advance(); self.advance()
            return Token(TokenType.BYTES, value, start_line, start_col, self.source)
        self.advance()  # consume opening quote
        value = ""
        while self.peek() and self.peek() != quote:
            if self.peek() == '\\':
                self.advance()
                esc = self.advance()
                value += '\\' + (esc or '')
            else:
                value += self.advance()
        if self.peek() is None:
            raise LexerError("Unterminated byte string", start_line, start_col)
        self.advance()  # consume closing quote
        return Token(TokenType.BYTES, value, start_line, start_col, self.source)

    def read_string(self, quote: str) -> Token:
        """Read a string literal, supporting triple-quote strings"""
        start_line, start_col = self.line, self.column

        # Check for triple-quote
        if self.peek(1) == quote and self.peek(2) == quote:
            # Triple-quoted string
            self.advance()  # first quote
            self.advance()  # second quote
            self.advance()  # third quote
            value = ""
            triple = quote * 3
            while True:
                if self.peek() is None:
                    raise LexerError("Unterminated triple-quoted string", start_line, start_col)
                if self.peek() == quote and self.peek(1) == quote and self.peek(2) == quote:
                    self.advance()
                    self.advance()
                    self.advance()
                    break
                value += self.advance()
            return Token(TokenType.STRING, value, start_line, start_col, self.source)

        # Normal single-quoted string
        self.advance()  # consume opening quote
        value = ""
        while self.peek() and self.peek() != quote:
            if self.peek() == '\\':
                self.advance()
                escape = self.advance()
                if escape == 'n':
                    value += '\n'
                elif escape == 't':
                    value += '\t'
                elif escape == 'r':
                    value += '\r'
                elif escape == '\\':
                    value += '\\'
                elif escape == quote:
                    value += quote
                else:
                    value += escape
            else:
                value += self.advance()

        if self.peek() is None:
            raise LexerError("Unterminated string", start_line, start_col)

        self.advance()  # consume closing quote
        return Token(TokenType.STRING, value, start_line, start_col, self.source)

    def read_number(self) -> Token:
        """Read an integer or float, supporting hex (0xFF), binary (0b1010), octal (0o77)"""
        start_line, start_col = self.line, self.column
        value = ""

        # Check for 0x, 0b, 0o prefixes
        if self.peek() == '0' and self.peek(1) in ('x', 'X', 'b', 'B', 'o', 'O'):
            value += self.advance()  # '0'
            prefix = self.advance()  # 'x'/'b'/'o'
            value += prefix
            if prefix in ('x', 'X'):
                # Hexadecimal
                while self.peek() and (self.peek() in '0123456789abcdefABCDEF' or self.peek() == '_'):
                    ch = self.advance()
                    if ch != '_':
                        value += ch
                return Token(TokenType.INTEGER, str(int(value, 16)), start_line, start_col, self.source)
            elif prefix in ('b', 'B'):
                # Binary
                while self.peek() and self.peek() in '01_':
                    ch = self.advance()
                    if ch != '_':
                        value += ch
                return Token(TokenType.INTEGER, str(int(value, 2)), start_line, start_col, self.source)
            elif prefix in ('o', 'O'):
                # Octal
                while self.peek() and self.peek() in '01234567_':
                    ch = self.advance()
                    if ch != '_':
                        value += ch
                return Token(TokenType.INTEGER, str(int(value, 8)), start_line, start_col, self.source)

        # Read integer part
        while self.peek() and self.peek().isdigit():
            value += self.advance()

        # Check for float
        if self.peek() == '.' and self.peek(1) and self.peek(1).isdigit():
            value += self.advance()  # consume .
            while self.peek() and self.peek().isdigit():
                value += self.advance()
            return Token(TokenType.FLOAT, value, start_line, start_col, self.source)

        return Token(TokenType.INTEGER, value, start_line, start_col, self.source)

    def read_identifier(self) -> Token:
        """Read an identifier or keyword"""
        start_line, start_col = self.line, self.column
        value = ""

        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            value += self.advance()

        token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, start_line, start_col, self.source)

    def read_indent(self) -> List[Token]:
        """Handle Python-style indentation"""
        tokens = []
        current_indent = 0

        while self.peek() == ' ':
            current_indent += 1
            self.advance()

        if self.peek() == '\t':
            current_indent += 8  # Treat tab as 8 spaces
            self.advance()

        if self.peek() == '\n':
            # Empty line, just consume
            self.advance()
            return tokens

        if current_indent > self.indent_stack[-1]:
            self.indent_stack.append(current_indent)
            tokens.append(Token(TokenType.INDENT, "", self.line, self.column, self.source))
        elif current_indent < self.indent_stack[-1]:
            while self.indent_stack and current_indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, "", self.line, self.column, self.source))

        return tokens

    def tokenize(self) -> List[Token]:
        """Tokenize the entire source"""
        while self.pos < len(self.source):
            self.skip_whitespace()

            # Check for end of source
            if self.peek() is None:
                break

            # Handle newlines and indentation
            if self.peek() == '\n':
                self.advance()
                indent_tokens = self.read_indent()
                self.tokens.extend(indent_tokens)
                continue

            # Handle comments
            comment = self.skip_block_comment()
            if comment:
                self.tokens.append(comment)
                continue

            if self.peek() == '#':
                self.tokens.append(self.skip_comment())
                continue

            # Handle byte literals b"..." or b'...'
            if self.peek() == 'b' and self.peek(1) in ('"', "'"):
                start_line, start_col = self.line, self.column
                self.advance()  # consume 'b'
                tok = self.read_string_raw(self.peek(), start_line, start_col)
                tok.type = TokenType.BYTES
                self.tokens.append(tok)
                continue

            # Handle strings
            if self.peek() in '"\'':
                self.tokens.append(self.read_string(self.peek()))
                continue

            # Handle numbers
            if self.peek() and self.peek().isdigit():
                self.tokens.append(self.read_number())
                continue

            # Handle identifiers and keywords
            if self.peek() and (self.peek().isalpha() or self.peek() == '_'):
                self.tokens.append(self.read_identifier())
                continue

            # Handle operators and delimiters
            start_line, start_col = self.line, self.column

            # Multi-character operators — check longest first

            # SPREAD: ...
            if self.peek() == '.' and self.peek(1) == '.' and self.peek(2) == '.':
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.SPREAD, "...", start_line, start_col, self.source))
                continue

            if self.peek() == '|':
                if self.peek(1) == '>':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.PIPE, "|>", start_line, start_col, self.source))
                elif self.peek(1) == '|':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.OR, "||", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.BOR, "|", start_line, start_col, self.source))
                continue

            if self.peek() == '=':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.EQ, "==", start_line, start_col, self.source))
                elif self.peek(1) == '>':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.FAT_ARROW, "=>", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col, self.source))
                continue

            if self.peek() == '!':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.NEQ, "!=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.NOT, "!", start_line, start_col, self.source))
                continue

            if self.peek() == '&':
                if self.peek(1) == '&':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.AND, "&&", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.BAND, "&", start_line, start_col, self.source))
                continue

            if self.peek() == '+':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.PLUS, "+", start_line, start_col, self.source))
                continue

            if self.peek() == '-':
                if self.peek(1) == '>':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.ARROW, "->", start_line, start_col, self.source))
                elif self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.MINUS, "-", start_line, start_col, self.source))
                continue

            if self.peek() == '*':
                if self.peek(1) == '*':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.POWER, "**", start_line, start_col, self.source))
                elif self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.STAR_ASSIGN, "*=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.STAR, "*", start_line, start_col, self.source))
                continue

            if self.peek() == '/':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.SLASH_ASSIGN, "/=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.SLASH, "/", start_line, start_col, self.source))
                continue

            if self.peek() == '%':
                if self.peek(1) == '=':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.PERCENT_ASSIGN, "%=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.PERCENT, "%", start_line, start_col, self.source))
                continue

            # ? — check for ?: (null coalescing) and ?. (optional chaining) before bare ?
            if self.peek() == '?':
                if self.peek(1) == ':':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.NULL_COALESCE, "?:", start_line, start_col, self.source))
                elif self.peek(1) == '.':
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(TokenType.OPTIONAL_DOT, "?.", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.QUESTION, "?", start_line, start_col, self.source))
                continue

            if self.peek() == '.':
                self.advance()
                self.tokens.append(Token(TokenType.DOT, ".", start_line, start_col, self.source))
                continue

            if self.peek() == ',':
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ",", start_line, start_col, self.source))
                continue

            if self.peek() == ':':
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ":", start_line, start_col, self.source))
                continue

            if self.peek() == ';':
                self.advance()
                self.tokens.append(Token(TokenType.SEMICOLON, ";", start_line, start_col, self.source))
                continue

            if self.peek() == '(':
                self.advance()
                self.tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col, self.source))
                continue

            if self.peek() == ')':
                self.advance()
                self.tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col, self.source))
                continue

            if self.peek() == '{':
                self.advance()
                self.tokens.append(Token(TokenType.LBRACE, "{", start_line, start_col, self.source))
                continue

            if self.peek() == '}':
                self.advance()
                self.tokens.append(Token(TokenType.RBRACE, "}", start_line, start_col, self.source))
                continue

            if self.peek() == '[':
                self.advance()
                self.tokens.append(Token(TokenType.LBRACKET, "[", start_line, start_col, self.source))
                continue

            if self.peek() == ']':
                self.advance()
                self.tokens.append(Token(TokenType.RBRACKET, "]", start_line, start_col, self.source))
                continue

            if self.peek() == '<':
                if self.peek(1) == '<':
                    self.advance(); self.advance()
                    self.tokens.append(Token(TokenType.LSHIFT, "<<", start_line, start_col, self.source))
                elif self.peek(1) == '=':
                    self.advance(); self.advance()
                    self.tokens.append(Token(TokenType.LTE, "<=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.LT, "<", start_line, start_col, self.source))
                continue

            if self.peek() == '>':
                if self.peek(1) == '>':
                    self.advance(); self.advance()
                    self.tokens.append(Token(TokenType.RSHIFT, ">>", start_line, start_col, self.source))
                elif self.peek(1) == '=':
                    self.advance(); self.advance()
                    self.tokens.append(Token(TokenType.GTE, ">=", start_line, start_col, self.source))
                else:
                    self.advance()
                    self.tokens.append(Token(TokenType.GT, ">", start_line, start_col, self.source))
                continue

            if self.peek() == '^':
                self.advance()
                self.tokens.append(Token(TokenType.BXOR, "^", start_line, start_col, self.source))
                continue

            if self.peek() == '~':
                self.advance()
                self.tokens.append(Token(TokenType.BNOT, "~", start_line, start_col, self.source))
                continue

            # Unknown character
            error_token = Token(TokenType.ERROR, self.advance(), start_line, start_col, self.source)
            self.tokens.append(error_token)

        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column, self.source))

        # Close any open indents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.insert(-1, Token(TokenType.DEDENT, "", self.line, self.column, self.source))

        return self.tokens


def tokenize(source: str) -> List[Token]:
    """Tokenize KOPPA source code"""
    lexer = Lexer(source)
    return lexer.tokenize()


if __name__ == "__main__":
    # Test the lexer
    test_code = '''
import scan, report

fn main(args) {
    let target = "192.168.1.1"
    var port = 445

    if port == 80 {
        http.enumerate(target)
    }

    target
        |> scan.tcp()
        |> report.save("result.txt")
}
'''

    tokens = tokenize(test_code)
    for token in tokens:
        print(token)
