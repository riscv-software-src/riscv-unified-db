# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import re
import subprocess

import pytest

from udb.idl import parse
from udb.idl.passes import DecodeEncoding, DecodeGenerator, to_option_adoc
from udb.idl.symbols import SymbolTable, Var
from udb.idl.types import BOOL_TYPE


@pytest.mark.parametrize("operator", ["&&", "||"])
def test_option_branch_conditions_are_complements_for_every_boolean_input(operator):
    text = to_option_adoc(parse(f"(a {operator} b) ? 1 : 2", "expression"))
    conditions = re.findall(r'\[when,"([^"]+)"\]', text)
    assert len(conditions) == 2
    for a in (False, True):
        for b in (False, True):
            table = SymbolTable()
            table.add("a", Var("a", BOOL_TYPE, a))
            table.add("b", Var("b", BOOL_TYPE, b))
            expected = a and b if operator == "&&" else a or b
            assert parse(conditions[0], "expression").value(table) == expected
            assert parse(conditions[1], "expression").value(table) == (not expected)


def test_compound_cpp_implementation_condition_cannot_bypass_opcode_guard(tmp_path):
    instructions = (
        DecodeEncoding("special", "1---", implemented_condition="feature_a || feature_b"),
        DecodeEncoding("other", "-0--"),
    )
    generated = DecodeGenerator(instruction_class=lambda name: name + "_inst").generate(
        instructions, 64
    )
    source = (
        r"""
        #include <cstdint>
        #include <iostream>
        #include <memory>
        struct Bits {
          std::uint64_t value = 0;
          template<int Hi, int Lo> Bits extract() const {
            return {(value >> Lo) & ((1ULL << (Hi - Lo + 1)) - 1)};
          }
          std::uint64_t get() const { return value; }
          friend Bits operator&(Bits a, Bits b) { return {a.value & b.value}; }
          friend bool operator==(Bits a, Bits b) { return a.value == b.value; }
        };
        Bits operator""_b(const char* text) {
          std::uint64_t value = 0;
          for (; *text; ++text)
            if (*text == '0' || *text == '1') value = (value << 1) | (*text - '0');
          return {value};
        }
        template<int Xlen, class SocType> struct special_inst {
          template<class Hart> special_inst(Hart* hart, Bits, Bits) { hart->chosen = 1; }
        };
        template<int Xlen, class SocType> struct other_inst {
          template<class Hart> other_inst(Hart* hart, Bits, Bits) { hart->chosen = 2; }
        };
        struct Hart {
          Bits encoding, pc;
          int chosen = 0;
          bool feature_a, feature_b;
          alignas(16) char storage[64];
          void* inst = storage;
          template<class SocType> bool decode() {
    """
        + generated
        + r"""
            return false;
          }
        };
        int main() {
          for (int value = 0; value < 16; ++value)
            for (int a = 0; a < 2; ++a)
              for (int b = 0; b < 2; ++b) {
                Hart hart{};
                hart.encoding.value = value;
                hart.feature_a = a;
                hart.feature_b = b;
                hart.decode<int>();
                int expected = (value & 8) && (a || b) ? 1 : !(value & 4) ? 2 : 0;
                if (hart.chosen != expected) {
                  std::cerr << value << "," << a << "," << b << ": "
                            << hart.chosen << " != " << expected << "\n";
                  return 1;
                }
              }
        }
    """
    )
    cpp = tmp_path / "guards.cpp"
    binary = tmp_path / "guards"
    cpp.write_text(source)
    subprocess.run(
        ["c++", "-std=c++20", str(cpp), "-o", str(binary)], check=True, capture_output=True
    )
    result = subprocess.run([str(binary)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
