"""
Small-C Abstract Syntax Tree (AST) Definitions
===============================================

This module defines the AST node types used by the Small-C parser.
The AST represents the hierarchical structure of a C program after
parsing, ready for semantic analysis and code generation.

Node Hierarchy
--------------
ASTNode (base)
├── ProgramNode - root node containing all declarations
├── Declarations
│   ├── FunctionNode - function definition
│   ├── VariableDeclaration - global or local variable
│   └── ParameterNode - function parameter
├── Statements
│   ├── BlockStatement - compound statement { ... }
│   ├── IfStatement - if/else statement
│   ├── WhileStatement - while loop
│   ├── ForStatement - for loop
│   ├── DoWhileStatement - do-while loop
│   ├── SwitchStatement - switch statement
│   ├── CaseClause - case/default in switch
│   ├── ReturnStatement - return statement
│   ├── BreakStatement - break statement
│   ├── ContinueStatement - continue statement
│   ├── GotoStatement - goto statement
│   ├── LabelStatement - label for goto
│   └── ExpressionStatement - expression as statement
└── Expressions
    ├── BinaryExpression - binary operators
    ├── UnaryExpression - unary operators
    ├── AssignmentExpression - assignment (=, +=, etc.)
    ├── TernaryExpression - ternary operator (?:)
    ├── CallExpression - function call
    ├── ArraySubscript - array indexing [n]
    ├── IdentifierExpression - variable reference
    ├── NumberLiteral - integer constant
    ├── StringLiteral - string constant
    └── CastExpression - type cast

Design Notes
------------
- All nodes are dataclasses for clean representation
- Each node stores its source location for error reporting
- Expression nodes store their computed type after type checking
- The AST is immutable after construction (frozen=True)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Union

from psion_sdk.errors import SourceLocation
from psion_sdk.smallc.types import CType


# =============================================================================
# AST Node Base Classes
# =============================================================================

@dataclass
class ASTNode:
    """
    Base class for all AST nodes.

    Every node in the AST inherits from this class, which provides
    common functionality like source location tracking for error
    reporting.

    Attributes:
        location: Source location where this node appears
    """
    location: SourceLocation

    def __repr__(self) -> str:
        """Default representation showing node type."""
        return f"{self.__class__.__name__}@{self.location.line}:{self.location.column}"


@dataclass
class Expression(ASTNode):
    """
    Base class for all expression nodes.

    Expressions are AST nodes that evaluate to a value. After type
    checking, each expression has a resolved_type that indicates
    the type of value it produces.

    Attributes:
        location: Source location
        resolved_type: The type of this expression (set during type checking)
    """
    resolved_type: Optional[CType] = field(default=None, compare=False)


@dataclass
class Statement(ASTNode):
    """
    Base class for all statement nodes.

    Statements are AST nodes that represent actions but don't
    produce a value.
    """
    pass


@dataclass
class Declaration(ASTNode):
    """
    Base class for all declaration nodes.

    Declarations introduce new names (variables, functions, etc.)
    into the program.
    """
    pass


# =============================================================================
# Program Root Node
# =============================================================================

@dataclass
class ProgramNode(ASTNode):
    """
    Root node of the AST representing a complete C program.

    Contains all top-level declarations (global variables and functions).

    Attributes:
        declarations: List of global declarations (functions and variables)
    """
    declarations: list[Declaration] = field(default_factory=list)


# =============================================================================
# Declaration Nodes
# =============================================================================

@dataclass
class ParameterNode(Declaration):
    """
    Function parameter declaration.

    Attributes:
        name: Parameter name
        param_type: The C type of the parameter
    """
    name: str = ""
    param_type: CType = field(default=None)


@dataclass
class VariableDeclaration(Declaration):
    """
    Variable declaration (global or local).

    Represents declarations like:
        int x;
        int y = 10;
        char buf[100];
        int *ptr;

    Attributes:
        name: Variable name
        var_type: The C type (including pointer/array info)
        initializer: Optional initialization expression
        is_global: True for global variables, False for local
    """
    name: str = ""
    var_type: CType = field(default=None)
    initializer: Optional[Expression] = None
    is_global: bool = False


@dataclass
class FunctionNode(Declaration):
    """
    Function definition.

    Represents a complete function including parameters and body.

    Attributes:
        name: Function name
        return_type: The return type
        parameters: List of parameter declarations
        body: The function body (block statement)
        is_forward_decl: True if this is just a forward declaration
    """
    name: str = ""
    return_type: CType = field(default=None)
    parameters: list[ParameterNode] = field(default_factory=list)
    body: Optional["BlockStatement"] = None
    is_forward_decl: bool = False


# =============================================================================
# Statement Nodes
# =============================================================================

@dataclass
class BlockStatement(Statement):
    """
    Block/compound statement enclosed in braces.

    Contains a list of declarations (local variables) and statements.

    Attributes:
        declarations: Local variable declarations at start of block
        statements: Statements in the block
    """
    declarations: list[VariableDeclaration] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)


@dataclass
class ExpressionStatement(Statement):
    """
    Expression used as a statement (followed by semicolon).

    Common for function calls and assignments:
        printf("hello");
        x = 5;

    Attributes:
        expression: The expression
    """
    expression: Expression = None


@dataclass
class IfStatement(Statement):
    """
    If statement with optional else clause.

    Attributes:
        condition: The condition expression
        then_branch: Statement executed if condition is true
        else_branch: Optional statement executed if condition is false
    """
    condition: Expression = None
    then_branch: Statement = None
    else_branch: Optional[Statement] = None


@dataclass
class WhileStatement(Statement):
    """
    While loop statement.

    Attributes:
        condition: Loop condition
        body: Loop body statement
    """
    condition: Expression = None
    body: Statement = None


@dataclass
class ForStatement(Statement):
    """
    For loop statement.

    Attributes:
        initializer: Optional initialization expression or declaration
        condition: Optional loop condition (defaults to true)
        update: Optional update expression
        body: Loop body statement
    """
    initializer: Optional[Union[Expression, VariableDeclaration]] = None
    condition: Optional[Expression] = None
    update: Optional[Expression] = None
    body: Statement = None


@dataclass
class DoWhileStatement(Statement):
    """
    Do-while loop statement.

    Attributes:
        body: Loop body statement
        condition: Loop condition (checked after body)
    """
    body: Statement = None
    condition: Expression = None


@dataclass
class CaseClause(Statement):
    """
    Case or default clause in a switch statement.

    Attributes:
        value: Case value expression (None for default)
        statements: Statements in this case
        is_default: True if this is the default case
    """
    value: Optional[Expression] = None
    statements: list[Statement] = field(default_factory=list)
    is_default: bool = False


@dataclass
class SwitchStatement(Statement):
    """
    Switch statement.

    Attributes:
        expression: The switch expression
        cases: List of case clauses
    """
    expression: Expression = None
    cases: list[CaseClause] = field(default_factory=list)


@dataclass
class ReturnStatement(Statement):
    """
    Return statement.

    Attributes:
        value: Optional return value expression
    """
    value: Optional[Expression] = None


@dataclass
class BreakStatement(Statement):
    """Break statement for exiting loops and switches."""
    pass


@dataclass
class ContinueStatement(Statement):
    """Continue statement for skipping to next loop iteration."""
    pass


@dataclass
class GotoStatement(Statement):
    """
    Goto statement (limited support).

    Attributes:
        label: Target label name
    """
    label: str = ""


@dataclass
class LabelStatement(Statement):
    """
    Label for goto targets.

    Attributes:
        name: Label name
        statement: The labeled statement
    """
    name: str = ""
    statement: Statement = None


# =============================================================================
# Expression Nodes
# =============================================================================

class BinaryOperator(Enum):
    """Binary operator types."""
    # Arithmetic
    ADD = auto()        # +
    SUBTRACT = auto()   # -
    MULTIPLY = auto()   # *
    DIVIDE = auto()     # /
    MODULO = auto()     # %

    # Comparison
    EQUAL = auto()      # ==
    NOT_EQUAL = auto()  # !=
    LESS = auto()       # <
    GREATER = auto()    # >
    LESS_EQ = auto()    # <=
    GREATER_EQ = auto() # >=

    # Logical
    LOGICAL_AND = auto()  # &&
    LOGICAL_OR = auto()   # ||

    # Bitwise
    BITWISE_AND = auto()  # &
    BITWISE_OR = auto()   # |
    BITWISE_XOR = auto()  # ^
    LEFT_SHIFT = auto()   # <<
    RIGHT_SHIFT = auto()  # >>


class UnaryOperator(Enum):
    """Unary operator types."""
    NEGATE = auto()     # -x
    POSITIVE = auto()   # +x (no-op)
    LOGICAL_NOT = auto() # !x
    BITWISE_NOT = auto() # ~x
    DEREFERENCE = auto() # *ptr
    ADDRESS_OF = auto()  # &var
    PRE_INCREMENT = auto()  # ++x
    PRE_DECREMENT = auto()  # --x
    POST_INCREMENT = auto() # x++
    POST_DECREMENT = auto() # x--


class AssignmentOperator(Enum):
    """Assignment operator types."""
    ASSIGN = auto()        # =
    ADD_ASSIGN = auto()    # +=
    SUB_ASSIGN = auto()    # -=
    MUL_ASSIGN = auto()    # *=
    DIV_ASSIGN = auto()    # /=
    MOD_ASSIGN = auto()    # %=
    AND_ASSIGN = auto()    # &=
    OR_ASSIGN = auto()     # |=
    XOR_ASSIGN = auto()    # ^=
    LSHIFT_ASSIGN = auto() # <<=
    RSHIFT_ASSIGN = auto() # >>=


@dataclass
class BinaryExpression(Expression):
    """
    Binary operation expression (a op b).

    Attributes:
        operator: The binary operator
        left: Left operand expression
        right: Right operand expression
    """
    operator: BinaryOperator = None
    left: Expression = None
    right: Expression = None


@dataclass
class UnaryExpression(Expression):
    """
    Unary operation expression (op x or x op).

    Attributes:
        operator: The unary operator
        operand: The operand expression
    """
    operator: UnaryOperator = None
    operand: Expression = None


@dataclass
class AssignmentExpression(Expression):
    """
    Assignment expression (lvalue = rvalue).

    Attributes:
        operator: The assignment operator (=, +=, etc.)
        target: The assignment target (lvalue)
        value: The value to assign
    """
    operator: AssignmentOperator = None
    target: Expression = None
    value: Expression = None


@dataclass
class TernaryExpression(Expression):
    """
    Ternary conditional expression (cond ? then : else).

    Attributes:
        condition: The condition expression
        then_expr: Expression if condition is true
        else_expr: Expression if condition is false
    """
    condition: Expression = None
    then_expr: Expression = None
    else_expr: Expression = None


@dataclass
class CallExpression(Expression):
    """
    Function call expression.

    Attributes:
        function_name: Name of the function to call
        arguments: List of argument expressions
    """
    function_name: str = ""
    arguments: list[Expression] = field(default_factory=list)


@dataclass
class ArraySubscript(Expression):
    """
    Array subscript expression (array[index]).

    Attributes:
        array: The array expression
        index: The index expression
    """
    array: Expression = None
    index: Expression = None


@dataclass
class IdentifierExpression(Expression):
    """
    Variable reference expression.

    Attributes:
        name: The variable name
    """
    name: str = ""


@dataclass
class NumberLiteral(Expression):
    """
    Integer literal expression.

    Attributes:
        value: The integer value
    """
    value: int = 0


@dataclass
class CharLiteral(Expression):
    """
    Character literal expression.

    Attributes:
        value: The character value (as integer)
    """
    value: int = 0


@dataclass
class StringLiteral(Expression):
    """
    String literal expression.

    Attributes:
        value: The string value
        label: Generated label for the string in assembly (set during codegen)
    """
    value: str = ""
    label: Optional[str] = field(default=None, compare=False)


@dataclass
class CastExpression(Expression):
    """
    Type cast expression (type)expr.

    Attributes:
        target_type: The type to cast to
        expression: The expression to cast
    """
    target_type: CType = None
    expression: Expression = None


@dataclass
class SizeofExpression(Expression):
    """
    Sizeof expression sizeof(type) or sizeof(expr).

    Attributes:
        target_type: Type to get size of (if sizeof(type))
        expression: Expression to get size of (if sizeof(expr))
    """
    target_type: Optional[CType] = None
    expression: Optional[Expression] = None


# =============================================================================
# AST Visitor Pattern
# =============================================================================

class ASTVisitor:
    """
    Base class for AST visitors.

    Provides a visitor pattern for traversing the AST. Subclasses
    override visit_* methods for specific node types they care about.

    Usage:
        class MyVisitor(ASTVisitor):
            def visit_FunctionNode(self, node):
                # Handle function definitions
                pass

        visitor = MyVisitor()
        visitor.visit(program)
    """

    def visit(self, node: ASTNode) -> any:
        """
        Visit a node by dispatching to the appropriate method.

        Args:
            node: The AST node to visit

        Returns:
            The result of the visit method (varies by node type)
        """
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode) -> None:
        """
        Default visit method for unhandled node types.

        Visits all children of the node.
        """
        # Visit child nodes based on their fields
        for field_name, field_value in node.__dict__.items():
            if isinstance(field_value, ASTNode):
                self.visit(field_value)
            elif isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, ASTNode):
                        self.visit(item)

    # Specific visit methods that subclasses can override
    def visit_ProgramNode(self, node: ProgramNode): return self.generic_visit(node)
    def visit_FunctionNode(self, node: FunctionNode): return self.generic_visit(node)
    def visit_VariableDeclaration(self, node: VariableDeclaration): return self.generic_visit(node)
    def visit_ParameterNode(self, node: ParameterNode): return self.generic_visit(node)
    def visit_BlockStatement(self, node: BlockStatement): return self.generic_visit(node)
    def visit_ExpressionStatement(self, node: ExpressionStatement): return self.generic_visit(node)
    def visit_IfStatement(self, node: IfStatement): return self.generic_visit(node)
    def visit_WhileStatement(self, node: WhileStatement): return self.generic_visit(node)
    def visit_ForStatement(self, node: ForStatement): return self.generic_visit(node)
    def visit_DoWhileStatement(self, node: DoWhileStatement): return self.generic_visit(node)
    def visit_SwitchStatement(self, node: SwitchStatement): return self.generic_visit(node)
    def visit_CaseClause(self, node: CaseClause): return self.generic_visit(node)
    def visit_ReturnStatement(self, node: ReturnStatement): return self.generic_visit(node)
    def visit_BreakStatement(self, node: BreakStatement): return self.generic_visit(node)
    def visit_ContinueStatement(self, node: ContinueStatement): return self.generic_visit(node)
    def visit_GotoStatement(self, node: GotoStatement): return self.generic_visit(node)
    def visit_LabelStatement(self, node: LabelStatement): return self.generic_visit(node)
    def visit_BinaryExpression(self, node: BinaryExpression): return self.generic_visit(node)
    def visit_UnaryExpression(self, node: UnaryExpression): return self.generic_visit(node)
    def visit_AssignmentExpression(self, node: AssignmentExpression): return self.generic_visit(node)
    def visit_TernaryExpression(self, node: TernaryExpression): return self.generic_visit(node)
    def visit_CallExpression(self, node: CallExpression): return self.generic_visit(node)
    def visit_ArraySubscript(self, node: ArraySubscript): return self.generic_visit(node)
    def visit_IdentifierExpression(self, node: IdentifierExpression): return self.generic_visit(node)
    def visit_NumberLiteral(self, node: NumberLiteral): return self.generic_visit(node)
    def visit_CharLiteral(self, node: CharLiteral): return self.generic_visit(node)
    def visit_StringLiteral(self, node: StringLiteral): return self.generic_visit(node)
    def visit_CastExpression(self, node: CastExpression): return self.generic_visit(node)
    def visit_SizeofExpression(self, node: SizeofExpression): return self.generic_visit(node)


# =============================================================================
# AST Pretty Printer
# =============================================================================

class ASTPrinter(ASTVisitor):
    """
    Pretty printer for AST debugging.

    Produces a human-readable representation of the AST structure.

    Usage:
        printer = ASTPrinter()
        output = printer.print(ast)
        print(output)
    """

    def __init__(self):
        self.output: list[str] = []
        self.indent_level = 0

    def print(self, node: ASTNode) -> str:
        """Print the AST and return as string."""
        self.output = []
        self.indent_level = 0
        self.visit(node)
        return "\n".join(self.output)

    def _emit(self, text: str) -> None:
        """Emit a line with current indentation."""
        indent = "  " * self.indent_level
        self.output.append(f"{indent}{text}")

    def _indent(self) -> None:
        """Increase indentation level."""
        self.indent_level += 1

    def _dedent(self) -> None:
        """Decrease indentation level."""
        self.indent_level = max(0, self.indent_level - 1)

    def visit_ProgramNode(self, node: ProgramNode):
        self._emit("Program")
        self._indent()
        for decl in node.declarations:
            self.visit(decl)
        self._dedent()

    def visit_FunctionNode(self, node: FunctionNode):
        params = ", ".join(f"{p.param_type} {p.name}" for p in node.parameters)
        self._emit(f"Function: {node.return_type} {node.name}({params})")
        if node.body:
            self._indent()
            self.visit(node.body)
            self._dedent()

    def visit_VariableDeclaration(self, node: VariableDeclaration):
        scope = "global" if node.is_global else "local"
        init = f" = {self._expr_str(node.initializer)}" if node.initializer else ""
        self._emit(f"Variable ({scope}): {node.var_type} {node.name}{init}")

    def visit_BlockStatement(self, node: BlockStatement):
        self._emit("Block")
        self._indent()
        for decl in node.declarations:
            self.visit(decl)
        for stmt in node.statements:
            self.visit(stmt)
        self._dedent()

    def visit_IfStatement(self, node: IfStatement):
        self._emit(f"If ({self._expr_str(node.condition)})")
        self._indent()
        self._emit("Then:")
        self._indent()
        self.visit(node.then_branch)
        self._dedent()
        if node.else_branch:
            self._emit("Else:")
            self._indent()
            self.visit(node.else_branch)
            self._dedent()
        self._dedent()

    def visit_WhileStatement(self, node: WhileStatement):
        self._emit(f"While ({self._expr_str(node.condition)})")
        self._indent()
        self.visit(node.body)
        self._dedent()

    def visit_ForStatement(self, node: ForStatement):
        init = self._expr_str(node.initializer) if node.initializer else ""
        cond = self._expr_str(node.condition) if node.condition else ""
        update = self._expr_str(node.update) if node.update else ""
        self._emit(f"For ({init}; {cond}; {update})")
        self._indent()
        self.visit(node.body)
        self._dedent()

    def visit_ReturnStatement(self, node: ReturnStatement):
        if node.value:
            self._emit(f"Return {self._expr_str(node.value)}")
        else:
            self._emit("Return")

    def visit_BreakStatement(self, node: BreakStatement):
        self._emit("Break")

    def visit_ContinueStatement(self, node: ContinueStatement):
        self._emit("Continue")

    def visit_ExpressionStatement(self, node: ExpressionStatement):
        self._emit(f"Expr: {self._expr_str(node.expression)}")

    def _expr_str(self, expr: Expression) -> str:
        """Convert expression to string representation."""
        if expr is None:
            return ""
        if isinstance(expr, NumberLiteral):
            return str(expr.value)
        if isinstance(expr, CharLiteral):
            return f"'{chr(expr.value)}'"
        if isinstance(expr, StringLiteral):
            return f'"{expr.value}"'
        if isinstance(expr, IdentifierExpression):
            return expr.name
        if isinstance(expr, BinaryExpression):
            op_str = {
                BinaryOperator.ADD: "+",
                BinaryOperator.SUBTRACT: "-",
                BinaryOperator.MULTIPLY: "*",
                BinaryOperator.DIVIDE: "/",
                BinaryOperator.MODULO: "%",
                BinaryOperator.EQUAL: "==",
                BinaryOperator.NOT_EQUAL: "!=",
                BinaryOperator.LESS: "<",
                BinaryOperator.GREATER: ">",
                BinaryOperator.LESS_EQ: "<=",
                BinaryOperator.GREATER_EQ: ">=",
                BinaryOperator.LOGICAL_AND: "&&",
                BinaryOperator.LOGICAL_OR: "||",
                BinaryOperator.BITWISE_AND: "&",
                BinaryOperator.BITWISE_OR: "|",
                BinaryOperator.BITWISE_XOR: "^",
                BinaryOperator.LEFT_SHIFT: "<<",
                BinaryOperator.RIGHT_SHIFT: ">>",
            }.get(expr.operator, "?")
            return f"({self._expr_str(expr.left)} {op_str} {self._expr_str(expr.right)})"
        if isinstance(expr, UnaryExpression):
            op_str = {
                UnaryOperator.NEGATE: "-",
                UnaryOperator.POSITIVE: "+",
                UnaryOperator.LOGICAL_NOT: "!",
                UnaryOperator.BITWISE_NOT: "~",
                UnaryOperator.DEREFERENCE: "*",
                UnaryOperator.ADDRESS_OF: "&",
                UnaryOperator.PRE_INCREMENT: "++",
                UnaryOperator.PRE_DECREMENT: "--",
                UnaryOperator.POST_INCREMENT: "++",
                UnaryOperator.POST_DECREMENT: "--",
            }.get(expr.operator, "?")
            if expr.operator in (UnaryOperator.POST_INCREMENT, UnaryOperator.POST_DECREMENT):
                return f"({self._expr_str(expr.operand)}{op_str})"
            return f"({op_str}{self._expr_str(expr.operand)})"
        if isinstance(expr, AssignmentExpression):
            op_str = {
                AssignmentOperator.ASSIGN: "=",
                AssignmentOperator.ADD_ASSIGN: "+=",
                AssignmentOperator.SUB_ASSIGN: "-=",
                AssignmentOperator.MUL_ASSIGN: "*=",
                AssignmentOperator.DIV_ASSIGN: "/=",
                AssignmentOperator.MOD_ASSIGN: "%=",
                AssignmentOperator.AND_ASSIGN: "&=",
                AssignmentOperator.OR_ASSIGN: "|=",
                AssignmentOperator.XOR_ASSIGN: "^=",
                AssignmentOperator.LSHIFT_ASSIGN: "<<=",
                AssignmentOperator.RSHIFT_ASSIGN: ">>=",
            }.get(expr.operator, "=")
            return f"({self._expr_str(expr.target)} {op_str} {self._expr_str(expr.value)})"
        if isinstance(expr, CallExpression):
            args = ", ".join(self._expr_str(a) for a in expr.arguments)
            return f"{expr.function_name}({args})"
        if isinstance(expr, ArraySubscript):
            return f"{self._expr_str(expr.array)}[{self._expr_str(expr.index)}]"
        if isinstance(expr, TernaryExpression):
            return f"({self._expr_str(expr.condition)} ? {self._expr_str(expr.then_expr)} : {self._expr_str(expr.else_expr)})"
        if isinstance(expr, VariableDeclaration):
            return f"{expr.var_type} {expr.name}"
        return f"<{type(expr).__name__}>"
