"""
Psion Small-C Compiler
======================

This module implements a Small-C compiler targeting the HD6303 processor
for the Psion Organiser II series of vintage handheld computers.

Small-C is a subset of the C programming language suitable for 8-bit
microprocessors. This implementation provides:

- A lexer (tokenizer) for C source code
- A recursive descent parser producing an AST
- A code generator emitting HD6303 assembly
- A preprocessor for #define and #include directives
- A runtime library with Psion-specific functions

Pipeline
--------
The compilation process follows this pipeline:

    C Source → Preprocessor → Lexer → Parser → AST → Code Generator → Assembly

The generated assembly can then be assembled using psasm and packaged
using psopk for deployment to the Psion device.

Usage
-----
>>> from psion_sdk.smallc import compile_c
>>> source = '''
... void main() {
...     cls();
...     print("Hello!");
... }
... '''
>>> asm_output = compile_c(source)
>>> print(asm_output)  # HD6303 assembly code

Language Subset
---------------
Supported features:
- Data types: char, int, unsigned variants, pointers
- Operators: arithmetic, relational, logical, bitwise, assignment
- Control flow: if/else, while, for, do-while, switch/case, break, continue, return
- Functions: definitions, calls, local variables, parameters

Not supported (Phase 1):
- float, double, long (16-bit maximum)
- struct, union, typedef
- Multi-dimensional arrays
- Function pointers

Memory Model
------------
- 16-bit integers (big-endian on HD6303)
- Stack-based local variables
- Frame pointer via X register
- Return values in A (8-bit) or D (16-bit) registers

References
----------
- Original Small-C by Ron Cain (1980)
- HD6303 Technical Reference Manual
- Psion Organiser II Technical Manual

Author: Hugo José Pinto & Contributors
"""

# =============================================================================
# Version Information
# =============================================================================

__version__ = "1.0.0"
__author__ = "Hugo José Pinto & Contributors"

# =============================================================================
# Public API Imports
# =============================================================================

from psion_sdk.smallc.compiler import SmallCCompiler, compile_c, CompilerOptions
from psion_sdk.smallc.errors import (
    SmallCError,
    CSyntaxError,
    CSemanticError,
    CTypeError,
    UndeclaredIdentifierError,
    DuplicateDeclarationError,
    CPreprocessorError,
)
from psion_sdk.smallc.lexer import CLexer, CTokenType, CToken
from psion_sdk.smallc.parser import CParser
from psion_sdk.smallc.codegen import CodeGenerator
from psion_sdk.smallc.ast import (
    ASTNode,
    ProgramNode,
    FunctionNode,
    VariableDeclaration,
    ParameterNode,
    BlockStatement,
    IfStatement,
    WhileStatement,
    ForStatement,
    DoWhileStatement,
    SwitchStatement,
    ReturnStatement,
    BreakStatement,
    ContinueStatement,
    ExpressionStatement,
    BinaryExpression,
    UnaryExpression,
    CallExpression,
    IdentifierExpression,
    NumberLiteral,
    StringLiteral,
    ArraySubscript,
    AssignmentExpression,
)

# =============================================================================
# Convenience Functions
# =============================================================================

__all__ = [
    # Version
    "__version__",
    # Main API
    "SmallCCompiler",
    "compile_c",
    "CompilerOptions",
    # Errors
    "SmallCError",
    "CSyntaxError",
    "CSemanticError",
    "CTypeError",
    "UndeclaredIdentifierError",
    "DuplicateDeclarationError",
    "CPreprocessorError",
    # Lexer
    "CLexer",
    "CTokenType",
    "CToken",
    # Parser
    "CParser",
    # Code Generator
    "CodeGenerator",
    # AST Nodes
    "ASTNode",
    "ProgramNode",
    "FunctionNode",
    "VariableDeclaration",
    "ParameterNode",
    "BlockStatement",
    "IfStatement",
    "WhileStatement",
    "ForStatement",
    "DoWhileStatement",
    "SwitchStatement",
    "ReturnStatement",
    "BreakStatement",
    "ContinueStatement",
    "ExpressionStatement",
    "BinaryExpression",
    "UnaryExpression",
    "CallExpression",
    "IdentifierExpression",
    "NumberLiteral",
    "StringLiteral",
    "ArraySubscript",
    "AssignmentExpression",
]
