"""
Small-C Type System
===================

This module implements the type system for the Small-C compiler.
It defines the data types supported by Small-C and provides utilities
for type checking and type size calculations.

Supported Types
---------------
- char: 8-bit signed integer (-128 to 127)
- unsigned char: 8-bit unsigned integer (0 to 255)
- int: 16-bit signed integer (-32768 to 32767)
- unsigned int: 16-bit unsigned integer (0 to 65535)
- void: no value (for function returns)
- Pointers to any type (char*, int*, etc.)
- struct: Aggregate types containing multiple fields

Type Representation
-------------------
Types are represented as CType objects with the following attributes:
- base_type: The fundamental type (CHAR, INT, VOID)
- is_unsigned: True for unsigned variants
- is_pointer: True for pointer types
- pointer_depth: Number of indirection levels (**)
- array_size: For array types, the element count (0 = not array)
- struct_name: For struct types, the struct's name (None for non-structs)

Size Information (HD6303)
-------------------------
| Type          | Size (bytes) |
|---------------|--------------|
| char          | 1            |
| unsigned char | 1            |
| int           | 2            |
| unsigned int  | 2            |
| pointer       | 2            |
| void          | 0            |
| struct        | varies (sum of field sizes) |

Struct Types
------------
Struct types are identified by the struct_name field. When struct_name is set:
- The type represents a struct (or pointer/array to struct)
- base_type is ignored (can be any value, typically VOID)
- Actual struct size must be looked up from the struct registry in codegen

Example struct types:
- struct Point          : CType(VOID, struct_name="Point")
- struct Point *        : CType(VOID, struct_name="Point", is_pointer=True)
- struct Point arr[5]   : CType(VOID, struct_name="Point", array_size=5)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable


# =============================================================================
# Base Type Enumeration
# =============================================================================

class BaseType(Enum):
    """
    Fundamental C data types supported by Small-C.

    Note: The HD6303 is an 8-bit processor with 16-bit address bus.
    All pointer types are 16-bit regardless of what they point to.
    """
    VOID = auto()       # No value type (for function returns)
    CHAR = auto()       # 8-bit signed/unsigned
    INT = auto()        # 16-bit signed/unsigned

    def __str__(self) -> str:
        """Return the C type name."""
        return self.name.lower()


# =============================================================================
# Type Representation
# =============================================================================

@dataclass(frozen=True)
class CType:
    """
    Represents a C type in the Small-C type system.

    This immutable class represents any type that can appear in a
    Small-C program, including primitives, pointers, arrays, and structs.

    Attributes:
        base_type: The fundamental type (CHAR, INT, VOID)
        is_unsigned: True for unsigned types
        is_pointer: True if this is a pointer type
        pointer_depth: Number of indirection levels (e.g., ** = 2)
        array_size: For arrays, the element count (0 = not array)
        struct_name: For struct types, the name of the struct (None = not a struct)
        struct_size_resolver: Optional callback to resolve struct sizes at runtime.
                             This is set by the code generator to allow size lookups.

    Examples:
        - char             : CType(CHAR, False, False, 0, 0, None)
        - unsigned int     : CType(INT, True, False, 0, 0, None)
        - int *            : CType(INT, False, True, 1, 0, None)
        - char **          : CType(CHAR, False, True, 2, 0, None)
        - int arr[10]      : CType(INT, False, False, 0, 10, None)
        - struct Point     : CType(VOID, struct_name="Point")
        - struct Point *   : CType(VOID, struct_name="Point", is_pointer=True)
        - struct Point[3]  : CType(VOID, struct_name="Point", array_size=3)

    Note:
        For array types, is_pointer is False but array_size > 0.
        When an array decays to a pointer (in expressions), a new
        CType is created with is_pointer=True, pointer_depth=1.

        For struct types, base_type is typically VOID (ignored), and
        struct_name identifies the struct definition. The actual struct
        size must be looked up from the struct registry during code
        generation using struct_size_resolver.
    """
    base_type: BaseType
    is_unsigned: bool = False
    is_pointer: bool = False
    pointer_depth: int = 0
    array_size: int = 0  # 0 = not an array
    struct_name: Optional[str] = None  # None = not a struct type
    # Callback to resolve struct sizes. Set by code generator.
    # Signature: (struct_name: str) -> int
    # This allows the type system to query struct sizes without circular imports.
    struct_size_resolver: Optional[Callable[[str], int]] = field(
        default=None, compare=False, hash=False
    )

    def __post_init__(self):
        """Validate type consistency."""
        # Void cannot be unsigned (but struct types use VOID as placeholder)
        if self.base_type == BaseType.VOID and self.is_unsigned and self.struct_name is None:
            raise ValueError("void cannot be unsigned")
        # If is_pointer, pointer_depth must be >= 1
        if self.is_pointer and self.pointer_depth < 1:
            object.__setattr__(self, "pointer_depth", 1)
        # If not pointer, pointer_depth must be 0
        if not self.is_pointer and self.pointer_depth != 0:
            object.__setattr__(self, "pointer_depth", 0)

    @property
    def is_struct(self) -> bool:
        """
        Return True if this is a struct type (value, not pointer).

        A type is a struct if struct_name is set AND it's not a pointer.
        Struct pointers have is_struct=False, is_struct_pointer=True.
        """
        return self.struct_name is not None and not self.is_pointer

    @property
    def is_struct_pointer(self) -> bool:
        """
        Return True if this is a pointer to a struct.

        This is the case when struct_name is set AND is_pointer is True.
        """
        return self.struct_name is not None and self.is_pointer

    @property
    def is_struct_type(self) -> bool:
        """
        Return True if this type involves a struct (value, pointer, or array).

        Use this to check if struct_name is meaningful for this type.
        """
        return self.struct_name is not None

    @property
    def size(self) -> int:
        """
        Return the size in bytes of this type.

        This is the size of one element, not the total size for arrays.
        For total array size, use total_size property.

        Returns:
            Size in bytes (1 for char, 2 for int/pointers, 0 for void)

        Note:
            For struct types without a size resolver, returns 0.
            The actual struct size must be looked up from the struct registry.
        """
        # Pointers are always 16-bit (2 bytes) on HD6303
        if self.is_pointer:
            return 2

        # Arrays (of non-structs) - the variable itself holds a pointer worth
        # But for struct arrays, we need the struct size
        if self.array_size > 0 and self.struct_name is None:
            return 2

        # Struct types - need to look up actual size
        if self.struct_name is not None:
            if self.struct_size_resolver is not None:
                return self.struct_size_resolver(self.struct_name)
            # No resolver available - return 0 as placeholder
            # Code generator will provide actual size during compilation
            return 0

        if self.base_type == BaseType.VOID:
            return 0
        elif self.base_type == BaseType.CHAR:
            return 1
        elif self.base_type == BaseType.INT:
            return 2

        return 0

    @property
    def element_size(self) -> int:
        """
        Return the size of the element this pointer/array points to.

        For non-pointer types, returns the type's own size.
        For pointers, returns the size of the pointed-to type.
        For arrays, returns the size of each array element.

        For struct pointers/arrays, returns the struct size.
        """
        if self.is_pointer:
            # Create the dereferenced type
            deref = self.dereference()
            return deref.size
        elif self.array_size > 0:
            # Array element size - could be struct
            if self.struct_name is not None:
                # Struct array - element is the struct type
                element_type = CType(
                    BaseType.VOID,
                    struct_name=self.struct_name,
                    struct_size_resolver=self.struct_size_resolver,
                )
                return element_type.size
            else:
                # Primitive array
                return CType(self.base_type, self.is_unsigned).size
        else:
            return self.size

    @property
    def total_size(self) -> int:
        """
        Return the total size in bytes including array elements.

        For arrays, this is element_count * element_size.
        For non-arrays, this equals size.

        For struct arrays, returns array_size * struct_size.
        """
        if self.array_size > 0:
            if self.struct_name is not None:
                # Struct array
                element_type = CType(
                    BaseType.VOID,
                    struct_name=self.struct_name,
                    struct_size_resolver=self.struct_size_resolver,
                )
                return self.array_size * element_type.size
            else:
                # Primitive array
                element_type = CType(self.base_type, self.is_unsigned)
                return self.array_size * element_type.size
        return self.size

    @property
    def is_array(self) -> bool:
        """Return True if this is an array type."""
        return self.array_size > 0

    @property
    def is_void(self) -> bool:
        """Return True if this is the void type."""
        return self.base_type == BaseType.VOID and not self.is_pointer

    @property
    def is_scalar(self) -> bool:
        """
        Return True if this is a scalar (non-aggregate) type.

        Scalars are: char, int, pointers (including struct pointers).
        Non-scalars are: arrays, void, struct values.

        Note: Struct values are aggregates, but struct pointers are scalars.
        """
        return not self.is_void and not self.is_array and not self.is_struct

    @property
    def is_integer(self) -> bool:
        """
        Return True if this is an integer type (char or int).

        Struct types are not integers even if base_type happens to be INT/CHAR.
        """
        return (self.base_type in (BaseType.CHAR, BaseType.INT)
                and not self.is_pointer
                and self.struct_name is None)

    @property
    def is_aggregate(self) -> bool:
        """
        Return True if this is an aggregate (non-scalar) type.

        Aggregates are: arrays and struct values.
        Note: Pointers (including struct pointers) are NOT aggregates.
        """
        return self.is_array or self.is_struct

    def dereference(self) -> "CType":
        """
        Return the type when this pointer is dereferenced.

        For int*, returns int.
        For int**, returns int*.
        For struct Point*, returns struct Point.
        For arrays, returns the element type.

        Raises:
            TypeError: If this is not a pointer or array type
        """
        if self.is_array:
            # Array access yields element type
            if self.struct_name is not None:
                # Struct array - element is struct type
                return CType(
                    BaseType.VOID,
                    struct_name=self.struct_name,
                    struct_size_resolver=self.struct_size_resolver,
                )
            else:
                return CType(self.base_type, self.is_unsigned)
        elif self.is_pointer:
            if self.pointer_depth > 1:
                # Multi-level pointer (e.g., int** -> int*)
                return CType(
                    self.base_type,
                    self.is_unsigned,
                    is_pointer=True,
                    pointer_depth=self.pointer_depth - 1,
                    struct_name=self.struct_name,
                    struct_size_resolver=self.struct_size_resolver,
                )
            else:
                # Single pointer (e.g., int* -> int, struct Point* -> struct Point)
                if self.struct_name is not None:
                    return CType(
                        BaseType.VOID,
                        struct_name=self.struct_name,
                        struct_size_resolver=self.struct_size_resolver,
                    )
                else:
                    return CType(self.base_type, self.is_unsigned)
        else:
            raise TypeError(f"cannot dereference non-pointer type {self}")

    def pointer_to(self) -> "CType":
        """
        Return a pointer type to this type.

        For int, returns int*.
        For int*, returns int**.
        For struct Point, returns struct Point*.
        For struct Point*, returns struct Point**.
        """
        if self.is_array:
            # Array of T becomes pointer to T
            return CType(
                self.base_type,
                self.is_unsigned,
                is_pointer=True,
                pointer_depth=1,
                struct_name=self.struct_name,
                struct_size_resolver=self.struct_size_resolver,
            )
        elif self.is_pointer:
            return CType(
                self.base_type,
                self.is_unsigned,
                is_pointer=True,
                pointer_depth=self.pointer_depth + 1,
                struct_name=self.struct_name,
                struct_size_resolver=self.struct_size_resolver,
            )
        else:
            return CType(
                self.base_type,
                self.is_unsigned,
                is_pointer=True,
                pointer_depth=1,
                struct_name=self.struct_name,
                struct_size_resolver=self.struct_size_resolver,
            )

    def decay(self) -> "CType":
        """
        Return the decayed type (arrays decay to pointers).

        In C, arrays decay to pointers in most expression contexts.
        This method returns the pointer type that the array decays to.
        For non-array types, returns self.

        For struct arrays, decays to pointer to struct.
        """
        if self.is_array:
            return CType(
                self.base_type,
                self.is_unsigned,
                is_pointer=True,
                pointer_depth=1,
                struct_name=self.struct_name,
                struct_size_resolver=self.struct_size_resolver,
            )
        return self

    def is_compatible_with(self, other: "CType") -> bool:
        """
        Check if this type is compatible with another for assignment.

        Type compatibility rules:
        1. Same types are compatible
        2. Signed/unsigned variants of same size are compatible (with warning)
        3. char and int are compatible (implicit promotion)
        4. Pointer types are compatible with each other (with warning)
        5. Integer 0 is compatible with any pointer type (NULL)
        6. Struct types are only compatible with same struct type
        7. Struct pointers follow pointer rules (void* compatible with all)

        Args:
            other: The type to check compatibility with

        Returns:
            True if assignment is allowed (possibly with implicit conversion)
        """
        # Exact match
        if self == other:
            return True

        # Both decayed (handle arrays)
        self_decay = self.decay()
        other_decay = other.decay()

        if self_decay == other_decay:
            return True

        # Struct types - must be exact same struct (no struct assignment anyway)
        if self_decay.is_struct or other_decay.is_struct:
            # Struct values can only be compatible with same struct
            return (self_decay.struct_name == other_decay.struct_name and
                    self_decay.is_struct == other_decay.is_struct)

        # Integer types are compatible with each other
        if self_decay.is_integer and other_decay.is_integer:
            return True

        # Pointer types are loosely compatible (void* with anything)
        if self_decay.is_pointer and other_decay.is_pointer:
            # void* is compatible with any pointer (including struct pointers)
            if (self_decay.base_type == BaseType.VOID and
                    self_decay.struct_name is None):
                return True
            if (other_decay.base_type == BaseType.VOID and
                    other_decay.struct_name is None):
                return True

            # Same struct pointer types are compatible
            if self_decay.struct_name is not None or other_decay.struct_name is not None:
                return self_decay.struct_name == other_decay.struct_name

            # Same base type pointers are compatible
            return self_decay.base_type == other_decay.base_type

        # Integer to pointer (NULL case) - allow int 0 to pointer
        if self_decay.is_pointer and other_decay.is_integer:
            return True

        return False

    def with_size_resolver(self, resolver: Callable[[str], int]) -> "CType":
        """
        Return a copy of this type with a struct size resolver attached.

        This is used by the code generator to provide struct size lookups
        to the type system without creating circular dependencies.

        Args:
            resolver: A function that takes a struct name and returns its size

        Returns:
            A new CType with the resolver attached
        """
        return CType(
            self.base_type,
            self.is_unsigned,
            self.is_pointer,
            self.pointer_depth,
            self.array_size,
            self.struct_name,
            resolver,
        )

    def __str__(self) -> str:
        """Return the C type string representation."""
        parts = []

        # Struct types
        if self.struct_name is not None:
            parts.append(f"struct {self.struct_name}")
        else:
            # Unsigned prefix
            if self.is_unsigned:
                parts.append("unsigned")
            # Base type
            parts.append(str(self.base_type))

        # Pointer stars
        if self.is_pointer:
            parts.append(" " + "*" * self.pointer_depth)

        # Array suffix
        if self.array_size > 0:
            result = " ".join(parts)
            return f"{result}[{self.array_size}]"

        return " ".join(parts)


# =============================================================================
# Predefined Types (for convenience)
# =============================================================================

# Primitive types
TYPE_VOID = CType(BaseType.VOID)
TYPE_CHAR = CType(BaseType.CHAR)
TYPE_UCHAR = CType(BaseType.CHAR, is_unsigned=True)
TYPE_INT = CType(BaseType.INT)
TYPE_UINT = CType(BaseType.INT, is_unsigned=True)

# Common pointer types
TYPE_CHAR_PTR = CType(BaseType.CHAR, is_pointer=True, pointer_depth=1)
TYPE_INT_PTR = CType(BaseType.INT, is_pointer=True, pointer_depth=1)
TYPE_VOID_PTR = CType(BaseType.VOID, is_pointer=True, pointer_depth=1)


# =============================================================================
# Type Parsing Utilities
# =============================================================================

def parse_type_specifiers(specifiers: list[str]) -> tuple[BaseType, bool]:
    """
    Parse a list of type specifier keywords into base type and signedness.

    Args:
        specifiers: List of keywords like ["unsigned", "int"] or ["char"]

    Returns:
        Tuple of (base_type, is_unsigned)

    Raises:
        ValueError: If specifiers are invalid

    Examples:
        ["int"]           -> (INT, False)
        ["unsigned"]      -> (INT, True)  # unsigned alone = unsigned int
        ["unsigned", "char"] -> (CHAR, True)
        ["char"]          -> (CHAR, False)
        ["void"]          -> (VOID, False)
    """
    is_unsigned = False
    base_type = None

    for spec in specifiers:
        spec_lower = spec.lower()

        if spec_lower == "unsigned":
            is_unsigned = True
        elif spec_lower == "signed":
            is_unsigned = False
        elif spec_lower == "char":
            if base_type is not None:
                raise ValueError(f"multiple base types: {base_type} and char")
            base_type = BaseType.CHAR
        elif spec_lower == "int":
            if base_type is not None:
                raise ValueError(f"multiple base types: {base_type} and int")
            base_type = BaseType.INT
        elif spec_lower == "void":
            if base_type is not None:
                raise ValueError(f"multiple base types: {base_type} and void")
            base_type = BaseType.VOID
        else:
            raise ValueError(f"unknown type specifier: {spec}")

    # Default to int if only signedness specified
    if base_type is None:
        base_type = BaseType.INT

    return base_type, is_unsigned


def make_type(
    base: BaseType,
    is_unsigned: bool = False,
    pointer_depth: int = 0,
    array_size: int = 0,
    struct_name: Optional[str] = None,
) -> CType:
    """
    Create a CType from components.

    This is a convenience function for creating CType instances.

    Args:
        base: The base type
        is_unsigned: True for unsigned variants
        pointer_depth: Number of pointer indirections
        array_size: For arrays, the element count
        struct_name: For struct types, the struct name

    Returns:
        A CType representing the specified type
    """
    return CType(
        base_type=base,
        is_unsigned=is_unsigned,
        is_pointer=pointer_depth > 0,
        pointer_depth=pointer_depth,
        array_size=array_size,
        struct_name=struct_name,
    )


def make_struct_type(
    struct_name: str,
    size_resolver: Optional[Callable[[str], int]] = None,
    pointer_depth: int = 0,
    array_size: int = 0,
) -> CType:
    """
    Create a struct type.

    This is a convenience function for creating struct CType instances.
    Struct types use VOID as their base_type (which is ignored).

    Args:
        struct_name: The name of the struct
        size_resolver: Optional callback to compute struct size (used for sizeof)
        pointer_depth: Number of pointer indirections (0 = struct value)
        array_size: For arrays of structs, the element count

    Returns:
        A CType representing the struct type

    Examples:
        make_struct_type("Point")             -> struct Point
        make_struct_type("Point", None, 1)    -> struct Point *
        make_struct_type("Point", None, 0, 5) -> struct Point[5]
        make_struct_type("Point", resolver)   -> struct Point with size resolver
    """
    return CType(
        base_type=BaseType.VOID,  # Placeholder, ignored for structs
        is_unsigned=False,
        is_pointer=pointer_depth > 0,
        pointer_depth=pointer_depth,
        array_size=array_size,
        struct_name=struct_name,
        struct_size_resolver=size_resolver,
    )


# =============================================================================
# Type Promotion Rules
# =============================================================================

def promote_type(type_a: CType, type_b: CType) -> CType:
    """
    Determine the result type when two types are combined in an expression.

    C type promotion rules (simplified for Small-C):
    1. If either type is a pointer, result is that pointer type
    2. If either type is int, result is int
    3. Otherwise result is char
    4. Unsigned wins over signed of same size

    Note: Struct types cannot be combined in expressions (no struct arithmetic).
    This function should not be called with struct operands.

    Args:
        type_a: First operand type
        type_b: Second operand type

    Returns:
        The promoted result type
    """
    # Decay arrays to pointers
    a = type_a.decay()
    b = type_b.decay()

    # Struct values cannot be combined in expressions
    # But struct pointers can participate in pointer arithmetic
    if a.is_struct or b.is_struct:
        # This shouldn't happen - codegen should catch this
        # Return int as fallback
        return TYPE_INT

    # Pointer arithmetic: pointer +/- int = pointer
    if a.is_pointer and not b.is_pointer:
        return a
    if b.is_pointer and not a.is_pointer:
        return b

    # Both pointers (e.g., pointer - pointer = int)
    if a.is_pointer and b.is_pointer:
        return TYPE_INT  # pointer difference is int

    # Integer promotion: int > char
    if a.base_type == BaseType.INT or b.base_type == BaseType.INT:
        is_unsigned = a.is_unsigned or b.is_unsigned
        return CType(BaseType.INT, is_unsigned)

    # Both char: result is char, unsigned if either is unsigned
    is_unsigned = a.is_unsigned or b.is_unsigned
    return CType(BaseType.CHAR, is_unsigned)
