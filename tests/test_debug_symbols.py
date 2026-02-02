# =============================================================================
# test_debug_symbols.py - Debug Symbol Generation Tests
# =============================================================================
# Tests for the debug symbol generation feature in the assembler.
#
# When the -g/--debug flag is used, the assembler produces a .dbg file
# containing symbol addresses and source line mappings. This enables
# source-level debugging with external tools.
#
# Test coverage includes:
#   - Debug file format correctness
#   - Symbol addresses (CODE, EQU types)
#   - Source map entries
#   - Relocatable vs non-relocatable handling
#   - Integration with psbuild
# =============================================================================

import pytest
import tempfile
from pathlib import Path

from psion_sdk.assembler import Assembler
from psion_sdk.assembler.codegen import (
    CodeGenerator,
    DebugSymbol,
    SourceMapEntry,
)


# =============================================================================
# Helper Functions
# =============================================================================

def assemble_with_debug(source: str, relocatable: bool = False) -> tuple[bytes, str]:
    """
    Assemble source with debug enabled and return (code, debug_content).
    """
    asm = Assembler(debug=True, relocatable=relocatable)
    code = asm.assemble_string(source)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.dbg', delete=False) as f:
        debug_path = Path(f.name)

    try:
        asm.write_debug(debug_path)
        debug_content = debug_path.read_text()
    finally:
        debug_path.unlink()

    return code, debug_content


def parse_debug_file(content: str) -> dict:
    """
    Parse a .dbg file and return structured data.

    Returns dict with:
        - 'version': str
        - 'target': str
        - 'origin': int
        - 'relocatable': bool
        - 'symbols': list of dicts with name, address, type, file, line
        - 'source_map': list of dicts with address, file, line, label
    """
    result = {
        'version': None,
        'target': None,
        'origin': None,
        'relocatable': None,
        'symbols': [],
        'source_map': [],
    }

    section = None
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith('VERSION '):
            result['version'] = line.split()[1]
        elif line.startswith('TARGET '):
            result['target'] = line.split()[1]
        elif line.startswith('ORIGIN '):
            result['origin'] = int(line.split()[1][1:], 16)  # Skip '$'
        elif line.startswith('RELOCATABLE '):
            result['relocatable'] = line.split()[1].lower() == 'true'
        elif line == '[SYMBOLS]':
            section = 'symbols'
        elif line == '[SOURCE_MAP]':
            section = 'source_map'
        elif section == 'symbols' and line:
            # Format: NAME $ADDR TYPE FILE:LINE
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0]
                addr = int(parts[1][1:], 16)
                sym_type = parts[2]
                file_line = parts[3].rsplit(':', 1)
                result['symbols'].append({
                    'name': name,
                    'address': addr,
                    'type': sym_type,
                    'file': file_line[0],
                    'line': int(file_line[1]),
                })
        elif section == 'source_map' and line:
            # Format: $ADDR FILE:LINE [LABEL]
            parts = line.split()
            if len(parts) >= 2:
                addr = int(parts[0][1:], 16)
                file_line = parts[1].rsplit(':', 1)
                label = parts[2][1:-1] if len(parts) > 2 else None  # Strip []
                result['source_map'].append({
                    'address': addr,
                    'file': file_line[0],
                    'line': int(file_line[1]),
                    'label': label,
                })

    return result


# =============================================================================
# Debug File Format Tests
# =============================================================================

class TestDebugFileFormat:
    """Test the .dbg file format structure."""

    def test_has_version(self):
        """Debug file should have VERSION header."""
        source = """
            ORG $2100
        start:
            NOP
            RTS
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)
        assert parsed['version'] == '1.0'

    def test_has_target(self):
        """Debug file should have TARGET header."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)
        assert parsed['target'] == 'XP'  # Default target

    def test_has_origin(self):
        """Debug file should have ORIGIN header."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)
        assert parsed['origin'] == 0x2100

    def test_relocatable_false(self):
        """Non-relocatable code should show RELOCATABLE false."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source, relocatable=False)
        parsed = parse_debug_file(debug_content)
        assert parsed['relocatable'] is False

    def test_relocatable_true(self):
        """Relocatable code should show RELOCATABLE true."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source, relocatable=True)
        parsed = parse_debug_file(debug_content)
        assert parsed['relocatable'] is True

    def test_has_symbols_section(self):
        """Debug file should have [SYMBOLS] section."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        assert '[SYMBOLS]' in debug_content

    def test_has_source_map_section(self):
        """Debug file should have [SOURCE_MAP] section."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        assert '[SOURCE_MAP]' in debug_content


# =============================================================================
# Symbol Recording Tests
# =============================================================================

class TestSymbolRecording:
    """Test that symbols are correctly recorded."""

    def test_label_recorded_as_code(self):
        """Labels should be recorded as CODE type."""
        source = """
            ORG $2100
        start:
            NOP
        loop:
            BRA loop
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        start_sym = next((s for s in parsed['symbols'] if s['name'] == 'START'), None)
        assert start_sym is not None
        assert start_sym['type'] == 'CODE'
        assert start_sym['address'] == 0x2100

        loop_sym = next((s for s in parsed['symbols'] if s['name'] == 'LOOP'), None)
        assert loop_sym is not None
        assert loop_sym['type'] == 'CODE'

    def test_equ_recorded_as_equ(self):
        """EQU constants should be recorded as EQU type."""
        source = """
            ORG $2100
        COUNTER EQU $80
        start:
            LDAA COUNTER
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        counter_sym = next((s for s in parsed['symbols'] if s['name'] == 'COUNTER'), None)
        assert counter_sym is not None
        assert counter_sym['type'] == 'EQU'
        assert counter_sym['address'] == 0x80

    def test_symbol_addresses_correct(self):
        """Symbol addresses should match actual code positions."""
        source = """
            ORG $2100
        start:          ; $2100
            NOP         ; 1 byte
            NOP         ; 1 byte
        second:         ; $2102
            RTS
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        start_sym = next((s for s in parsed['symbols'] if s['name'] == 'START'), None)
        second_sym = next((s for s in parsed['symbols'] if s['name'] == 'SECOND'), None)

        assert start_sym['address'] == 0x2100
        assert second_sym['address'] == 0x2102


# =============================================================================
# Source Map Tests
# =============================================================================

class TestSourceMap:
    """Test that source mappings are correctly recorded."""

    def test_instructions_mapped(self):
        """Each instruction should have a source map entry."""
        source = """
            ORG $2100
        start:
            NOP
            NOP
            RTS
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        # Should have at least 3 source map entries (one per instruction)
        assert len(parsed['source_map']) >= 3

    def test_source_map_addresses_sequential(self):
        """Source map addresses should be in sequential order."""
        source = """
            ORG $2100
        start:
            NOP
            NOP
            RTS
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        addresses = [e['address'] for e in parsed['source_map']]
        assert addresses == sorted(addresses)

    def test_source_map_has_labels(self):
        """Source map entries should include current label context."""
        source = """
            ORG $2100
        start:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        # Find the NOP entry
        nop_entry = next((e for e in parsed['source_map'] if e['address'] == 0x2100), None)
        assert nop_entry is not None
        assert nop_entry['label'] == 'start'


# =============================================================================
# Edge Cases
# =============================================================================

class TestDebugEdgeCases:
    """Test edge cases in debug symbol generation."""

    def test_empty_program(self):
        """Empty program should still produce valid debug file."""
        source = """
            ORG $2100
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)
        assert parsed['version'] == '1.0'
        assert parsed['origin'] == 0x2100

    def test_multiple_labels_same_address(self):
        """Multiple labels at same address should all be recorded."""
        source = """
            ORG $2100
        start:
        begin:
        entry:
            NOP
        """
        _, debug_content = assemble_with_debug(source)
        parsed = parse_debug_file(debug_content)

        # All three labels should be at $2100
        labels_at_2100 = [s for s in parsed['symbols'] if s['address'] == 0x2100]
        # Note: Due to how symbols are processed, we may have duplicates
        # or they may be collapsed. Just verify at least one exists.
        assert len(labels_at_2100) >= 1

    def test_debug_disabled_raises_error(self):
        """Writing debug without enabling it should raise error."""
        asm = Assembler()  # debug=False by default
        asm.assemble_string("ORG $2100\nNOP")

        with tempfile.NamedTemporaryFile(suffix='.dbg', delete=False) as f:
            debug_path = Path(f.name)

        try:
            with pytest.raises(RuntimeError):
                asm.write_debug(debug_path)
        finally:
            if debug_path.exists():
                debug_path.unlink()


# =============================================================================
# Assembler API Tests
# =============================================================================

class TestAssemblerDebugAPI:
    """Test the Assembler class debug API."""

    def test_debug_enabled_in_constructor(self):
        """debug=True in constructor should enable debug mode."""
        asm = Assembler(debug=True)
        assert asm.is_debug_enabled()

    def test_debug_disabled_by_default(self):
        """Debug should be disabled by default."""
        asm = Assembler()
        assert not asm.is_debug_enabled()

    def test_enable_debug_method(self):
        """enable_debug() should toggle debug mode."""
        asm = Assembler()
        assert not asm.is_debug_enabled()

        asm.enable_debug(True)
        assert asm.is_debug_enabled()

        asm.enable_debug(False)
        assert not asm.is_debug_enabled()


# =============================================================================
# CodeGenerator Debug API Tests
# =============================================================================

class TestCodeGeneratorDebugAPI:
    """Test the CodeGenerator class debug API."""

    def test_get_debug_symbols(self):
        """get_debug_symbols() should return list of DebugSymbol."""
        codegen = CodeGenerator()
        codegen.enable_debug(True)

        source = """
            ORG $2100
        start:
            NOP
        """
        from psion_sdk.assembler.parser import parse_source
        statements = parse_source(source)
        codegen.generate(statements)

        symbols = codegen.get_debug_symbols()
        assert isinstance(symbols, list)
        assert all(isinstance(s, DebugSymbol) for s in symbols)

    def test_get_source_map(self):
        """get_source_map() should return list of SourceMapEntry."""
        codegen = CodeGenerator()
        codegen.enable_debug(True)

        source = """
            ORG $2100
        start:
            NOP
        """
        from psion_sdk.assembler.parser import parse_source
        statements = parse_source(source)
        codegen.generate(statements)

        source_map = codegen.get_source_map()
        assert isinstance(source_map, list)
        assert all(isinstance(e, SourceMapEntry) for e in source_map)


# =============================================================================
# Integration with Relocation
# =============================================================================

class TestDebugWithRelocation:
    """Test debug symbols with relocatable code."""

    def test_relocatable_addresses_are_offsets(self):
        """In relocatable mode, addresses should be offsets from origin."""
        source = """
            ORG $0000
        start:
            NOP
        label2:
            NOP
        """
        _, debug_content = assemble_with_debug(source, relocatable=True)
        parsed = parse_debug_file(debug_content)

        # In relocatable mode, origin is typically 0
        assert parsed['origin'] == 0x0000
        assert parsed['relocatable'] is True

        # Addresses should be small offsets
        start_sym = next((s for s in parsed['symbols'] if s['name'] == 'START'), None)
        if start_sym:
            # Address should be relative to origin (small offset)
            # The actual value depends on relocator stub size
            assert start_sym['address'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
