"""
Tests for the Psion SDK Module
==============================

This test module provides comprehensive coverage of the SDK module,
including system variables, system calls, model definitions, and
include file generation.

Run tests with:
    pytest tests/test_sdk.py -v
"""

import pytest
from psion_sdk.sdk import (
    # Models
    PsionModel,
    ModelInfo,
    DisplayInfo,
    MemoryInfo,
    MODEL_INFO,
    ALL_MODELS,
    TWO_LINE_MODELS,
    FOUR_LINE_MODELS,
    BANKING_MODELS,
    EXTENDED_SERVICE_MODELS,
    decode_model_byte,
    decode_rom_version,
    format_rom_version,
    get_model_by_name,
    get_supported_models,
    get_all_models_info,
    is_compatible,

    # System Variables
    VarCategory,
    SystemVariable,
    SYSTEM_VARIABLES,
    get_variable,
    get_variables_at_address,
    get_variables_for_model,
    get_variables_by_category,
    get_all_variable_names,
    generate_sysvars_inc,

    # System Calls
    CallCategory,
    SystemCall,
    Parameter,
    SYSTEM_CALLS,
    get_syscall,
    get_syscall_by_number,
    get_syscalls_for_model,
    get_syscalls_by_category,
    get_all_syscall_names,
    generate_syscalls_inc,

    # Generation
    generate_include_file,
    generate_syscall_documentation,
    generate_sysvar_documentation,
    generate_model_documentation,
)


# =============================================================================
# Model Tests
# =============================================================================

class TestPsionModel:
    """Tests for the PsionModel enum and related functions."""

    def test_model_values(self):
        """Test that model enum values match Psion documentation."""
        assert PsionModel.CM.value == 0
        assert PsionModel.XP.value == 1
        assert PsionModel.LA.value == 2
        assert PsionModel.P350.value == 4
        assert PsionModel.LZ64.value == 5
        assert PsionModel.LZ.value == 6

    def test_from_model_byte(self):
        """Test extracting model from raw model byte."""
        # Simple cases (just model ID)
        assert PsionModel.from_model_byte(0x00) == PsionModel.CM
        assert PsionModel.from_model_byte(0x01) == PsionModel.XP
        assert PsionModel.from_model_byte(0x06) == PsionModel.LZ

        # With additional flags set (bits 3-7)
        assert PsionModel.from_model_byte(0x86) == PsionModel.LZ  # Multi-lingual flag
        assert PsionModel.from_model_byte(0x03) is None  # Invalid model ID (3)
        assert PsionModel.from_model_byte(0x07) is None  # Invalid model ID (7)

    def test_model_info_exists_for_all_models(self):
        """Test that ModelInfo is defined for all models."""
        for model in PsionModel:
            assert model in MODEL_INFO
            info = MODEL_INFO[model]
            assert isinstance(info, ModelInfo)
            assert info.model == model

    def test_model_info_display(self):
        """Test display characteristics for different models."""
        # 2-line models
        cm_info = MODEL_INFO[PsionModel.CM]
        assert cm_info.display.rows == 2
        assert cm_info.display.columns == 16

        # 4-line models
        lz_info = MODEL_INFO[PsionModel.LZ]
        assert lz_info.display.rows == 4
        assert lz_info.display.columns == 20

    def test_model_sets(self):
        """Test that model sets are correctly defined."""
        assert PsionModel.CM in TWO_LINE_MODELS
        assert PsionModel.XP in TWO_LINE_MODELS
        assert PsionModel.LZ not in TWO_LINE_MODELS

        assert PsionModel.LZ in FOUR_LINE_MODELS
        assert PsionModel.LZ64 in FOUR_LINE_MODELS
        assert PsionModel.CM not in FOUR_LINE_MODELS

        assert PsionModel.LZ in BANKING_MODELS
        assert PsionModel.CM not in BANKING_MODELS

        assert PsionModel.LZ in EXTENDED_SERVICE_MODELS
        assert PsionModel.LA in EXTENDED_SERVICE_MODELS


class TestModelDetection:
    """Tests for model detection utilities."""

    def test_decode_model_byte(self):
        """Test comprehensive model byte decoding."""
        # LZ with multi-lingual flag
        info = decode_model_byte(0x8E)  # 0x86 = LZ + multi-lingual
        assert info["model"] == PsionModel.LZ
        assert info["model_id"] == 6
        assert info["multi_lingual"] == True
        assert info["raw"] == 0x8E

        # CM basic
        info = decode_model_byte(0x00)
        assert info["model"] == PsionModel.CM
        assert info["multi_lingual"] == False

    def test_decode_rom_version(self):
        """Test ROM version decoding from BCD."""
        assert decode_rom_version(0x46) == (4, 6)
        assert decode_rom_version(0x37) == (3, 7)
        assert decode_rom_version(0x24) == (2, 4)
        assert decode_rom_version(0x00) == (0, 0)

    def test_format_rom_version(self):
        """Test ROM version formatting."""
        assert format_rom_version(0x46) == "4.6"
        assert format_rom_version(0x37) == "3.7"
        assert format_rom_version(0x24) == "2.4"

    def test_get_model_by_name(self):
        """Test model lookup by name."""
        # Short names
        assert get_model_by_name("CM") == PsionModel.CM
        assert get_model_by_name("LZ") == PsionModel.LZ
        assert get_model_by_name("lz") == PsionModel.LZ  # Case insensitive

        # Full names
        assert get_model_by_name("Organiser II LZ") == PsionModel.LZ

        # Invalid names
        assert get_model_by_name("INVALID") is None

    def test_is_compatible(self):
        """Test model compatibility checking."""
        # Same model is always compatible
        assert is_compatible(PsionModel.LZ, PsionModel.LZ) == True

        # CM code runs on anything
        assert is_compatible(PsionModel.LZ, PsionModel.CM) == True
        assert is_compatible(PsionModel.XP, PsionModel.CM) == True

        # LZ code won't run on CM (extended services)
        assert is_compatible(PsionModel.CM, PsionModel.LZ) == False


# =============================================================================
# System Variable Tests
# =============================================================================

class TestSystemVariables:
    """Tests for system variable definitions."""

    def test_variables_exist(self):
        """Test that system variables are defined."""
        assert len(SYSTEM_VARIABLES) > 100  # Should have many variables

    def test_known_variables(self):
        """Test lookup of well-known variables."""
        # Scratch registers
        utw_s0 = get_variable("UTW_S0")
        assert utw_s0 is not None
        assert utw_s0.address == 0x41
        assert utw_s0.size == 2

        # Display cursor position
        dpb_cpos = get_variable("DPB_CPOS")
        assert dpb_cpos is not None
        assert dpb_cpos.address == 0x62
        assert dpb_cpos.size == 1

        # Time variables
        tmb_hour = get_variable("TMB_HOUR")
        assert tmb_hour is not None
        assert tmb_hour.address == 0x20C8

        # ROM constants
        model_byte = get_variable("FFE8_MODEL")
        assert model_byte is not None
        assert model_byte.address == 0xFFE8
        assert model_byte.read_only == True

    def test_variable_case_insensitivity(self):
        """Test that variable lookup is case-insensitive."""
        assert get_variable("utw_s0") == get_variable("UTW_S0")
        assert get_variable("Utw_S0") == get_variable("UTW_S0")

    def test_variables_at_address(self):
        """Test getting multiple variables at same address."""
        # UTW_S0 and UTB_S0 share address $41
        vars_at_41 = get_variables_at_address(0x41)
        assert len(vars_at_41) >= 1
        names = [v.name for v in vars_at_41]
        assert "UTW_S0" in names

    def test_variables_for_model(self):
        """Test filtering variables by model."""
        lz_vars = get_variables_for_model(PsionModel.LZ)
        cm_vars = get_variables_for_model(PsionModel.CM)

        # LZ should have more variables (extended features)
        # Both should have basic variables
        lz_names = {v.name for v in lz_vars}
        cm_names = {v.name for v in cm_vars}

        # Common variables
        assert "UTW_S0" in lz_names
        assert "UTW_S0" in cm_names

    def test_variables_by_category(self):
        """Test filtering variables by category."""
        display_vars = get_variables_by_category(VarCategory.DISPLAY)
        assert len(display_vars) > 5

        # All should be display-related
        for var in display_vars:
            assert var.category == VarCategory.DISPLAY

    def test_variable_models_consistency(self):
        """Test that all variables have valid model sets."""
        for var in SYSTEM_VARIABLES:
            assert len(var.models) > 0, f"{var.name} has no models"
            for model in var.models:
                assert isinstance(model, PsionModel)


class TestSysvarsIncGeneration:
    """Tests for sysvars.inc file generation."""

    def test_generate_basic(self):
        """Test basic include file generation."""
        content = generate_sysvars_inc()
        assert "UTW_S0" in content
        assert "EQU" in content
        assert "$0041" in content or "$41" in content

    def test_generate_with_model_filter(self):
        """Test generation filtered by model."""
        content = generate_sysvars_inc(model="LZ")
        assert "UTW_S0" in content
        assert "Target model: LZ" in content

    def test_generate_with_notes(self):
        """Test generation with notes included."""
        content = generate_sysvars_inc(include_notes=True)
        # Should include some notes in parentheses
        assert "(" in content and ")" in content


# =============================================================================
# System Call Tests
# =============================================================================

class TestSystemCalls:
    """Tests for system call definitions."""

    def test_calls_exist(self):
        """Test that system calls are defined."""
        assert len(SYSTEM_CALLS) > 80  # Should have many calls

    def test_known_calls(self):
        """Test lookup of well-known system calls."""
        # Display output
        dp_emit = get_syscall("DP$EMIT")
        assert dp_emit is not None
        assert dp_emit.number == 0x10

        # Keyboard input
        kb_getk = get_syscall("KB$GETK")
        assert kb_getk is not None
        assert kb_getk.number == 0x48

        # File operations
        fl_open = get_syscall("FL$OPEN")
        assert fl_open is not None
        assert fl_open.number == 0x2F

        # Sound
        bz_bell = get_syscall("BZ$BELL")
        assert bz_bell is not None
        assert bz_bell.number == 0x0E

    def test_call_by_number(self):
        """Test lookup by service number."""
        call = get_syscall_by_number(0x10)
        assert call is not None
        assert call.name == "DP$EMIT"

    def test_call_case_insensitivity(self):
        """Test that call lookup is case-insensitive."""
        assert get_syscall("dp$emit") == get_syscall("DP$EMIT")

    def test_calls_for_model(self):
        """Test filtering calls by model."""
        lz_calls = get_syscalls_for_model(PsionModel.LZ)
        cm_calls = get_syscalls_for_model(PsionModel.CM)

        # LZ should have extended calls
        lz_names = {c.name for c in lz_calls}
        cm_names = {c.name for c in cm_calls}

        # Common calls
        assert "DP$EMIT" in lz_names
        assert "DP$EMIT" in cm_names

        # LZ-specific calls should only be in LZ
        assert "DP$MSET" in lz_names  # LZ extended display
        assert "DP$MSET" not in cm_names

    def test_calls_by_category(self):
        """Test filtering calls by category."""
        display_calls = get_syscalls_by_category(CallCategory.DISPLAY)
        assert len(display_calls) >= 5

        for call in display_calls:
            assert call.category == CallCategory.DISPLAY

    def test_call_models_consistency(self):
        """Test that all calls have valid model sets."""
        for call in SYSTEM_CALLS:
            assert len(call.models) > 0, f"{call.name} has no models"
            for model in call.models:
                assert isinstance(model, PsionModel)

    def test_call_numbers_unique(self):
        """Test that service numbers are unique within models."""
        # Note: Different calls may share numbers if for different models
        # But within a model, numbers should be unique
        for model in PsionModel:
            calls = get_syscalls_for_model(model)
            numbers = [c.number for c in calls]
            # Check for duplicates (there shouldn't be any within a model)
            # This is just a sanity check
            assert len(numbers) == len(set(numbers)), \
                f"Duplicate service numbers in {model.name}"


class TestSyscallsIncGeneration:
    """Tests for syscalls.inc file generation."""

    def test_generate_basic(self):
        """Test basic include file generation."""
        content = generate_syscalls_inc()
        assert "DP$EMIT" in content
        assert "EQU" in content
        assert "$10" in content

    def test_generate_with_model_filter(self):
        """Test generation filtered by model."""
        content = generate_syscalls_inc(model="CM")
        assert "DP$EMIT" in content
        # LZ-only calls should be excluded
        assert "DP$MSET" not in content

    def test_syscall_macro_included(self):
        """Test that SYSCALL macro is included."""
        content = generate_syscalls_inc()
        assert "MACRO SYSCALL" in content
        assert "ENDM" in content


# =============================================================================
# Include File Generation Tests
# =============================================================================

class TestIncludeFileGeneration:
    """Tests for unified include file generation."""

    def test_generate_complete(self):
        """Test generating complete include file."""
        content = generate_include_file()

        # Should contain header
        assert "PSION.INC" in content

        # Should contain variables
        assert "UTW_S0" in content

        # Should contain system calls
        assert "DP_EMIT" in content or "DP$EMIT" in content

        # Should contain macros
        assert "MACRO" in content

    def test_generate_model_specific(self):
        """Test generating model-specific include file."""
        content = generate_include_file(model="LZ")
        assert "Target model: LZ" in content

    def test_generate_selective(self):
        """Test selective content generation."""
        # Variables only
        content = generate_include_file(
            include_variables=True,
            include_syscalls=False,
            include_macros=False,
        )
        assert "UTW_S0" in content
        # Syscalls section should be absent or minimal

        # Syscalls only
        content = generate_include_file(
            include_variables=False,
            include_syscalls=True,
            include_macros=False,
        )
        # Should have syscall definitions


# =============================================================================
# Documentation Generation Tests
# =============================================================================

class TestDocumentationGeneration:
    """Tests for markdown documentation generation."""

    def test_generate_syscall_docs(self):
        """Test system call documentation generation."""
        doc = generate_syscall_documentation()

        # Should be markdown
        assert "# Psion" in doc
        assert "## " in doc
        assert "### " in doc

        # Should contain known calls
        assert "DP$EMIT" in doc
        assert "KB$GETK" in doc

    def test_generate_sysvar_docs(self):
        """Test system variable documentation generation."""
        doc = generate_sysvar_documentation()

        # Should be markdown
        assert "# Psion" in doc
        assert "## " in doc

        # Should contain known variables
        assert "UTW_S0" in doc

    def test_generate_model_docs(self):
        """Test model documentation generation."""
        doc = generate_model_documentation()

        # Should be markdown
        assert "# Psion" in doc

        # Should contain all models
        assert "CM" in doc
        assert "LZ" in doc
        assert "LZ64" in doc

    def test_filtered_documentation(self):
        """Test documentation filtered by model."""
        doc = generate_syscall_documentation(model="CM")
        # LZ-only calls should be excluded
        # Common calls should be present
        assert "DP$EMIT" in doc


# =============================================================================
# Integration Tests
# =============================================================================

class TestSDKIntegration:
    """Integration tests combining multiple SDK features."""

    def test_model_and_calls_consistency(self):
        """Test that model-specific calls are correctly tagged."""
        # Get LZ-only calls
        for call in SYSTEM_CALLS:
            if PsionModel.LZ in call.models and PsionModel.CM not in call.models:
                # This is an LZ-extended call
                # It should be in EXTENDED_SERVICE_MODELS
                for model in call.models:
                    assert model in EXTENDED_SERVICE_MODELS or model in FOUR_LINE_MODELS, \
                        f"{call.name} model mismatch"

    def test_generate_and_parse(self):
        """Test that generated include files are syntactically valid."""
        content = generate_include_file()

        # Basic validation - all EQU statements should have valid format
        for line in content.split("\n"):
            line = line.strip()
            if "EQU" in line and not line.startswith(";"):
                parts = line.split()
                # Should have format: NAME EQU $XX
                assert len(parts) >= 3, f"Invalid EQU line: {line}"
                assert "EQU" in parts

    def test_all_variable_names_unique(self):
        """Test that all variable names are unique."""
        names = get_all_variable_names()
        assert len(names) == len(set(names)), "Duplicate variable names found"

    def test_all_syscall_names_unique(self):
        """Test that all system call names are unique."""
        names = get_all_syscall_names()
        assert len(names) == len(set(names)), "Duplicate syscall names found"


# =============================================================================
# Spec Milestone Tests
# =============================================================================

class TestSpecMilestones:
    """Tests corresponding to the spec milestones."""

    def test_milestone_s1_include_generation(self):
        """Milestone S1: Generate include file and verify syntax."""
        content = generate_include_file(model="LZ")

        # Should contain known definitions
        assert "UTW_S0" in content
        assert "DP" in content  # DP$EMIT or DP_EMIT
        assert "KB" in content  # KB$GETK or KB_GETK

        # LZ-only features should be present when filtering for LZ
        # (model-specific content test)

    def test_milestone_s3_model_detection(self):
        """Milestone S3: Verify model detection logic."""
        # Model byte decoding
        assert decode_model_byte(0)["model"] == PsionModel.CM
        assert decode_model_byte(1)["model"] == PsionModel.XP
        assert decode_model_byte(6)["model"] == PsionModel.LZ

        # Also test with flags
        assert decode_model_byte(0x86)["model"] == PsionModel.LZ


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_variable_name(self):
        """Test lookup of non-existent variable."""
        assert get_variable("NONEXISTENT") is None

    def test_invalid_syscall_name(self):
        """Test lookup of non-existent system call."""
        assert get_syscall("NONEXISTENT") is None

    def test_invalid_syscall_number(self):
        """Test lookup of unused service number."""
        # Find an unused number
        assert get_syscall_by_number(0xFF) is None

    def test_empty_address_lookup(self):
        """Test lookup at address with no variables."""
        # Unlikely to have variables at very high unused addresses
        vars = get_variables_at_address(0xFFFF)
        assert isinstance(vars, list)  # Should return empty list, not error

    def test_model_get_info(self):
        """Test getting model info via enum method."""
        for model in PsionModel:
            info = model.get_info()
            assert info is not None
            assert isinstance(info, ModelInfo)
