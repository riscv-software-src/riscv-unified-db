# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import subprocess

import pytest

from udb.idl.passes import (
    DecodeEncoding,
    DecodeGenerator,
    DecodeNodeKind,
    DecodeVariable,
    build_decode_tree,
    decode_variable_allowed_condition,
    extract_decode_variable,
)


def test_tree_matches_linear_reference_for_all_small_encodings():
    instructions = (
        DecodeEncoding("a", "00--11"),
        DecodeEncoding("b", "01--11"),
        DecodeEncoding("c", "1---01"),
    )
    tree = build_decode_tree(instructions)
    assert tree.kind == DecodeNodeKind.SELECT
    for encoding in range(64):
        expected = next((item for item in instructions if item.matches(encoding)), None)
        assert tree.decode(encoding) == expected
    child = tree.children[0]
    assert child.mask() == 3
    assert child.mask_overlap(range(1, 3))
    assert child.lowest_non_opcode_bit() == 2


def test_split_decode_variables_exclusions_hint_priority_and_implementation():
    variable = DecodeVariable("xs1", (range(4, 6), range(1, 3)), (0, 1, 2, 3))
    parent = DecodeEncoding("parent", "------1")
    hint = DecodeEncoding("hint", "------1", (variable,), hint_of="parent")
    tree = build_decode_tree((parent, hint))
    for encoding in range(128):
        expected = hint if hint.matches(encoding) else parent if parent.matches(encoding) else None
        assert tree.decode(encoding) == expected
        assert tree.decode(encoding, implemented=lambda inst: inst.name != "hint") == (
            parent if parent.matches(encoding) else None
        )
    assert extract_decode_variable(variable, "encoding") == (
        "(encoding.extract<2, 1>() | (encoding.extract<5, 4>().template widening_sll<2>()))"
    )


def test_variable_opcode_mix_terminates_and_keeps_residual_guards():
    instructions = (DecodeEncoding("a", "-1-"), DecodeEncoding("b", "0--"))
    tree = build_decode_tree(instructions)
    assert tree.kind == DecodeNodeKind.ENDPOINT
    for encoding in range(8):
        assert tree.decode(encoding) == next(
            (item for item in instructions if item.matches(encoding)), None
        )
    assert build_decode_tree(()).decode(0) is None


def test_cpp_generator_keeps_hint_exclusions_optional_guards_and_class_names():
    parent = DecodeEncoding("parent", "---1")
    hint = DecodeEncoding(
        "hint",
        "---1",
        (DecodeVariable("idx", (range(1, 3),), (0, 2, 3)),),
        hint_of="parent",
        implemented_condition="implemented_Q_(ExtensionName::Hint)",
    )
    cpp = DecodeGenerator(instruction_class=lambda name: f"{name}_inst").generate(
        (parent, hint), 64
    )
    assert cpp.index("hint_inst<64") < cpp.index("parent_inst<64")
    assert "implemented_Q_(ExtensionName::Hint)" in cpp
    assert "== 1_b" in cpp
    assert "std::construct_at(" in cpp
    assert cpp.count("return true;") == 2
    assert (
        decode_variable_allowed_condition(DecodeVariable("all", (range(2),), (0, 1, 2, 3)), "e")
        == "false"
    )
    assert decode_variable_allowed_condition(DecodeVariable("none", (range(1000),)), "e") == "true"


@pytest.mark.parametrize(
    "instructions",
    [
        (DecodeEncoding("a", "0"), DecodeEncoding("a", "1")),
        (DecodeEncoding("a", "0", hint_of="b"), DecodeEncoding("b", "0", hint_of="a")),
    ],
)
def test_invalid_decode_inputs_raise_clean_errors(instructions):
    with pytest.raises(ValueError):
        build_decode_tree(instructions)


def test_emitted_cpp_compiles_with_split_fields_hints_and_optional_guards():
    parent = DecodeEncoding("parent", "-----1")
    hint = DecodeEncoding(
        "hint",
        "-----1",
        (DecodeVariable("idx", (range(3, 5), range(1, 2)), (0, 2)),),
        hint_of="parent",
        implemented_condition="implemented_Q_(ExtensionName::Hint)",
    )
    generated = DecodeGenerator(instruction_class=lambda name: name + "_inst").generate(
        (parent, hint), 64
    )
    source = (
        r"""
        #include <memory>
        #include <cstdint>
        struct Bits {
          std::uint64_t value = 0;
          template<int Hi, int Lo> Bits extract() const { return {value >> Lo}; }
          template<int Shift> Bits widening_sll() const { return {value << Shift}; }
          std::uint64_t get() const { return value; }
          friend Bits operator&(Bits a, Bits b) { return {a.value & b.value}; }
          friend Bits operator|(Bits a, Bits b) { return {a.value | b.value}; }
          friend bool operator==(Bits a, Bits b) { return a.value == b.value; }
          friend bool operator!=(Bits a, Bits b) { return a.value != b.value; }
        };
        Bits operator""_b(const char*) { return {}; }
        enum class ExtensionName { Hint };
        bool implemented_Q_(ExtensionName) { return true; }
        template<int Xlen, class SocType> struct parent_inst {
          template<class Hart> parent_inst(Hart*, Bits, Bits) {}
        };
        template<int Xlen, class SocType> struct hint_inst {
          template<class Hart> hint_inst(Hart*, Bits, Bits) {}
        };
        struct Hart {
          Bits encoding, pc;
          void* inst;
          template<class SocType> bool decode() {
        """
        + generated
        + r"""
            return false;
          }
        };
        int main() { Hart hart{}; return hart.decode<int>(); }
    """
    )
    result = subprocess.run(
        ["c++", "-x", "c++", "-std=c++20", "-fsyntax-only", "-"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
