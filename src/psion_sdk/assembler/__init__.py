"""
HD6303 Assembler for Psion Organiser II
========================================

This module provides a complete assembler for the HD6303 microprocessor,
targeting the Psion Organiser II series of handheld computers.

The assembler converts HD6303 assembly source code into Psion-compatible
object code format (.ob3), which can then be packaged into OPK files
for transfer to the device.

Main Components
---------------
- **Assembler**: Main assembler class that orchestrates the assembly process
- **Lexer**: Tokenizes assembly source into tokens
- **Parser**: Parses tokens into statements (instructions, directives, labels)
- **PeepholeOptimizer**: Applies safe optimizations to instruction sequences
- **CodeGenerator**: Generates object code from parsed statements
- **ExpressionEvaluator**: Evaluates arithmetic expressions

Assembly Process
----------------
The assembler uses a three-stage pipeline:

1. **Parsing (Lexer + Parser)**:
   - Tokenize source into lexical tokens
   - Parse tokens into statements (instructions, directives, labels)
   - Build abstract syntax tree (AST)

2. **Optimization (PeepholeOptimizer)** (optional, enabled by default):
   - Apply safe peephole optimizations (e.g., LDAA #0 → CLRA)
   - Eliminate redundant instruction sequences (e.g., PSHA/PULA pairs)
   - Remove unreachable code after unconditional branches

3. **Code Generation (CodeGenerator)** (two-pass):
   - Pass 1: Symbol collection, address calculation, branch relaxation
   - Pass 2: Generate object code, resolve forward references

Example Usage
-------------
>>> from psion_sdk.assembler import Assembler
>>> asm = Assembler()
>>> asm.assemble_string('''
...     ORG $8000
... start:
...     LDAA #$41    ; Load 'A'
...     JSR print
...     RTS
... print:
...     NOP
...     RTS
... ''')
>>> code = asm.get_code()
>>> asm.write_ob3("hello.ob3")

Supported Features
------------------
- Full HD6303 instruction set (including HD6303-specific instructions)
- All addressing modes (inherent, immediate, direct, extended, indexed, relative)
- Labels (global and local)
- Constants (EQU, SET)
- Data directives (FCB, FDB, FCC, RMB, FILL)
- Include files (INCLUDE)
- Macros (MACRO/ENDM)
- Conditional assembly (#IF, #IFDEF, #IFNDEF, #ELSE, #ENDIF)
- Expressions with full operator support
- Peephole optimization (optional, enabled by default)
- Listing file generation
- Symbol table output
"""

from psion_sdk.assembler.assembler import Assembler, assemble, assemble_file
from psion_sdk.assembler.lexer import Lexer, Token, TokenType
from psion_sdk.assembler.parser import Parser, Statement, Instruction, Directive, LabelDef
from psion_sdk.assembler.optimizer import (
    PeepholeOptimizer,
    OptimizationStats,
    optimize_statements,
)
from psion_sdk.assembler.codegen import CodeGenerator
from psion_sdk.cpu import (
    AddressingMode,
    InstructionInfo,
    OPCODE_TABLE,
    MNEMONICS,
    BRANCH_INSTRUCTIONS,
)
from psion_sdk.assembler.expressions import ExpressionEvaluator

__all__ = [
    # Main class and functions
    "Assembler",
    "assemble",
    "assemble_file",
    # Lexer
    "Lexer",
    "Token",
    "TokenType",
    # Parser
    "Parser",
    "Statement",
    "Instruction",
    "Directive",
    "LabelDef",
    # Optimizer
    "PeepholeOptimizer",
    "OptimizationStats",
    "optimize_statements",
    # Code generator
    "CodeGenerator",
    # Opcodes
    "AddressingMode",
    "InstructionInfo",
    "OPCODE_TABLE",
    "MNEMONICS",
    "BRANCH_INSTRUCTIONS",
    # Expressions
    "ExpressionEvaluator",
]
