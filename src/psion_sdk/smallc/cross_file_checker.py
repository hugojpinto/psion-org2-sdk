"""
Cross-File Extern Type Checker
==============================

This module validates that 'extern' declarations in multi-file C builds
match their actual definitions across translation units.

When building multi-file C projects, extern declarations tell the compiler
that a function or variable is defined elsewhere. However, if the extern
declaration's signature differs from the actual definition, this can cause
subtle runtime bugs that are hard to diagnose.

This module catches such mismatches at compile time by:
1. Collecting all function/variable definitions and extern declarations
2. Comparing extern declarations against their definitions
3. Reporting any type mismatches (return type, parameters, variable type)

Usage
-----
>>> from psion_sdk.smallc.cross_file_checker import validate_extern_signatures
>>> errors, warnings = validate_extern_signatures(asts)
>>> if errors:
...     for err in errors:
...         print(err)

The 'asts' parameter is a list of (filename, ProgramNode) tuples representing
the parsed ASTs of all C files in a multi-file build.

Author: Hugo José Pinto & Contributors
Part of the Psion Organiser II SDK
"""

from dataclasses import dataclass, field
from typing import Optional

from psion_sdk.errors import SourceLocation
from psion_sdk.smallc.ast import (
    ProgramNode,
    FunctionNode,
    VariableDeclaration,
)
from psion_sdk.smallc.types import CType
from psion_sdk.smallc.errors import ExternMismatchError


# =============================================================================
# Data Classes for Collected Declarations
# =============================================================================

@dataclass
class FunctionDefinition:
    """
    Information about a function definition.

    Attributes:
        name: Function name
        return_type: The declared return type
        param_types: List of parameter types
        location: Source location of the definition
        source_file: Filename where the definition appears
    """
    name: str
    return_type: CType
    param_types: list[CType]
    location: SourceLocation
    source_file: str


@dataclass
class FunctionExtern:
    """
    Information about an extern function declaration.

    Attributes:
        name: Function name
        return_type: The declared return type
        param_types: List of parameter types
        location: Source location of the extern declaration
        source_file: Filename where the extern declaration appears
    """
    name: str
    return_type: CType
    param_types: list[CType]
    location: SourceLocation
    source_file: str


@dataclass
class VariableDefinition:
    """
    Information about a variable definition.

    Attributes:
        name: Variable name
        var_type: The declared type
        location: Source location of the definition
        source_file: Filename where the definition appears
    """
    name: str
    var_type: CType
    location: SourceLocation
    source_file: str


@dataclass
class VariableExtern:
    """
    Information about an extern variable declaration.

    Attributes:
        name: Variable name
        var_type: The declared type
        location: Source location of the extern declaration
        source_file: Filename where the extern declaration appears
    """
    name: str
    var_type: CType
    location: SourceLocation
    source_file: str


@dataclass
class CollectedDeclarations:
    """
    Container for all collected definitions and extern declarations.

    Attributes:
        func_definitions: Maps function name -> FunctionDefinition
        func_externs: List of all function extern declarations
        var_definitions: Maps variable name -> VariableDefinition
        var_externs: List of all variable extern declarations
    """
    func_definitions: dict[str, FunctionDefinition] = field(default_factory=dict)
    func_externs: list[FunctionExtern] = field(default_factory=list)
    var_definitions: dict[str, VariableDefinition] = field(default_factory=dict)
    var_externs: list[VariableExtern] = field(default_factory=list)


# =============================================================================
# Collection Functions
# =============================================================================

def collect_declarations(asts: list[tuple[str, ProgramNode]]) -> CollectedDeclarations:
    """
    Collect all function/variable definitions and extern declarations from ASTs.

    Iterates through all declarations in each AST, categorizing them as either
    definitions (actual implementations) or extern declarations (references to
    definitions in other files).

    Args:
        asts: List of (filename, ProgramNode) tuples representing parsed files

    Returns:
        CollectedDeclarations containing all definitions and externs

    Notes:
        - Forward declarations without 'extern' are ignored (they're local)
        - OPL function declarations are ignored (they're runtime bindings)
        - Struct definitions are not checked (they don't have extern)
    """
    result = CollectedDeclarations()

    for filename, program in asts:
        for decl in program.declarations:
            if isinstance(decl, FunctionNode):
                # Skip OPL procedure declarations
                if decl.is_opl:
                    continue

                if decl.is_extern:
                    # Extern function declaration
                    result.func_externs.append(FunctionExtern(
                        name=decl.name,
                        return_type=decl.return_type,
                        param_types=[p.param_type for p in decl.parameters],
                        location=decl.location,
                        source_file=filename,
                    ))
                elif not decl.is_forward_decl:
                    # Actual function definition (has a body)
                    result.func_definitions[decl.name] = FunctionDefinition(
                        name=decl.name,
                        return_type=decl.return_type,
                        param_types=[p.param_type for p in decl.parameters],
                        location=decl.location,
                        source_file=filename,
                    )

            elif isinstance(decl, VariableDeclaration):
                if decl.is_extern:
                    # Extern variable declaration
                    result.var_externs.append(VariableExtern(
                        name=decl.name,
                        var_type=decl.var_type,
                        location=decl.location,
                        source_file=filename,
                    ))
                elif decl.is_global:
                    # Global variable definition
                    result.var_definitions[decl.name] = VariableDefinition(
                        name=decl.name,
                        var_type=decl.var_type,
                        location=decl.location,
                        source_file=filename,
                    )

    return result


# =============================================================================
# Type Matching
# =============================================================================

def types_match(type1: CType, type2: CType) -> bool:
    """
    Check if two types are compatible for extern matching.

    Type matching rules:
    - Base types must match (char vs int vs void)
    - Pointer status must match (pointer vs non-pointer)
    - Pointer depth must match (int* vs int**)
    - Signedness must match (unsigned int vs int)
    - Arrays decay to pointers (char[] and char* are compatible)

    Args:
        type1: First type to compare
        type2: Second type to compare

    Returns:
        True if types are compatible, False otherwise
    """
    # Decay arrays to pointers for comparison
    t1 = type1.decay()
    t2 = type2.decay()

    # Check basic properties
    if t1.base_type != t2.base_type:
        return False

    if t1.is_pointer != t2.is_pointer:
        return False

    if t1.pointer_depth != t2.pointer_depth:
        return False

    if t1.is_unsigned != t2.is_unsigned:
        return False

    # Check struct type name if applicable
    if t1.struct_name != t2.struct_name:
        return False

    return True


def _type_to_str(t: CType) -> str:
    """Format a CType as a readable string for error messages."""
    return str(t)


# =============================================================================
# Validation
# =============================================================================

def validate_extern_signatures(
    asts: list[tuple[str, ProgramNode]],
    warn_undefined: bool = True,
) -> tuple[list[ExternMismatchError], list[str]]:
    """
    Validate that extern declarations match their definitions.

    This function checks all extern declarations in the provided ASTs against
    their actual definitions, reporting any mismatches.

    Args:
        asts: List of (filename, ProgramNode) tuples representing parsed files
        warn_undefined: If True, generate warnings for externs without definitions
                       (these might be runtime functions, so they're warnings not errors)

    Returns:
        Tuple of (errors, warnings) where:
        - errors: List of ExternMismatchError for type mismatches
        - warnings: List of warning strings for undefined externs

    Error Types Detected:
        - Return type mismatch: extern declares different return type
        - Parameter count mismatch: extern declares different number of parameters
        - Parameter type mismatch: extern declares different parameter types
        - Variable type mismatch: extern declares different variable type

    Example:
        >>> errors, warnings = validate_extern_signatures(asts)
        >>> for err in errors:
        ...     print(err)  # Shows detailed mismatch information
    """
    errors: list[ExternMismatchError] = []
    warnings: list[str] = []

    # Collect all declarations
    collected = collect_declarations(asts)

    # Check function externs
    for extern in collected.func_externs:
        definition = collected.func_definitions.get(extern.name)

        if definition is None:
            # No definition found - this might be a runtime function
            if warn_undefined:
                warnings.append(
                    f"{extern.location}: warning: extern function '{extern.name}' "
                    f"has no definition (may be a runtime function)"
                )
            continue

        # Check return type
        if not types_match(extern.return_type, definition.return_type):
            errors.append(ExternMismatchError(
                name=extern.name,
                mismatch_type="return_type",
                extern_location=extern.location,
                definition_location=definition.location,
                extern_info=_type_to_str(extern.return_type),
                definition_info=_type_to_str(definition.return_type),
            ))
            continue  # Don't report param errors if return type is wrong

        # Check parameter count
        if len(extern.param_types) != len(definition.param_types):
            errors.append(ExternMismatchError(
                name=extern.name,
                mismatch_type="param_count",
                extern_location=extern.location,
                definition_location=definition.location,
                extern_info=f"{len(extern.param_types)} parameters",
                definition_info=f"{len(definition.param_types)} parameters",
            ))
            continue  # Don't check individual params if count is wrong

        # Check each parameter type
        for i, (ext_type, def_type) in enumerate(
            zip(extern.param_types, definition.param_types)
        ):
            if not types_match(ext_type, def_type):
                errors.append(ExternMismatchError(
                    name=extern.name,
                    mismatch_type="param_type",
                    extern_location=extern.location,
                    definition_location=definition.location,
                    extern_info=f"parameter {i+1} is {_type_to_str(ext_type)}",
                    definition_info=f"parameter {i+1} is {_type_to_str(def_type)}",
                ))
                break  # Report only the first param mismatch

    # Check variable externs
    for extern in collected.var_externs:
        definition = collected.var_definitions.get(extern.name)

        if definition is None:
            # No definition found
            if warn_undefined:
                warnings.append(
                    f"{extern.location}: warning: extern variable '{extern.name}' "
                    f"has no definition"
                )
            continue

        # Check type
        if not types_match(extern.var_type, definition.var_type):
            errors.append(ExternMismatchError(
                name=extern.name,
                mismatch_type="var_type",
                extern_location=extern.location,
                definition_location=definition.location,
                extern_info=_type_to_str(extern.var_type),
                definition_info=_type_to_str(definition.var_type),
            ))

    return errors, warnings
