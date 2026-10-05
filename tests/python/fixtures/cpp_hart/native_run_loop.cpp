// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
// SPDX-License-Identifier: BSD-3-Clause-Clear

#include <array>
#include <fstream>
#include <stdexcept>
#include "udb/cfgs/cpp-smoke/hart.hxx"
#include "udb/iss_soc_model.hpp"

using namespace udb;

static void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

int main(int argc, char** argv) {
  require(argc == 2, "generated configuration argument");
  std::ifstream input(argv[1]);
  nlohmann::json json;
  input >> json;
  Config config(json["implemented_extensions"], json["params"]);
  IssSocModel soc(4096, 0);
  CppSmoke_Hart<IssSocModel> hart(0, soc, config);
  constexpr std::array<uint32_t, 15> program = {
      0x00700293,  // addi x5, x0, 7
      0x00928313,  // addi x6, x5, 9
      0x00131393,  // slli x7, x6, 1
      0xfff38413,  // addi x8, x7, -1
      0x00840463,  // beq x8, x8, +8
      0x06300493,  // addi x9, x0, 99 (skipped)
      0x0080056f,  // jal x10, +8
      0x06300493,  // addi x9, x0, 99 (skipped)
      0x02100493,  // addi x9, x0, 33
      0x08000593,  // addi x11, x0, 128
      0xffc00613,  // addi x12, x0, -4
      0x00c5a023,  // sw x12, 0(x11)
      0x0005a683,  // lw x13, 0(x11)
      0x00058703,  // lb x14, 0(x11)
      0x0005c783,  // lbu x15, 0(x11)
  };
  for (size_t index = 0; index < program.size(); ++index)
    soc.write_physical_memory_32(index * 4, program[index]);

  hart.reset(0);
  require(hart.run_n(7) == StopReason::InstLimitReached, "arithmetic/control run limit");
  require(hart.pc() == 36, "control-flow PC");
  require(hart.xreg(5) == 7 && hart.xreg(6) == 16 && hart.xreg(7) == 32 &&
              hart.xreg(8) == 31 && hart.xreg(9) == 33 && hart.xreg(10) == 28,
          "fetched arithmetic, branch and link values");

  require(hart.run_n(6) == StopReason::InstLimitReached, "load/store run limit");
  require(hart.pc() == 60, "memory PC");
  require(soc.read_physical_memory_32(128) == 0xfffffffc, "store semantics");
  require(hart.xreg(13) == 0xfffffffc && hart.xreg(14) == 0xfffffffc &&
              hart.xreg(15) == 0xfc,
          "word and signed/unsigned byte loads");

  auto* scratch = hart.csr("mscratch");
  require(scratch != nullptr, "CSR lookup");
  scratch->hw_write(PossiblyUnknownBits<64>{42_b}, Bits<8>{32});
  hart.execute_instruction(Bits<32>{0x34061873});  // csrrw x16, mscratch, x12
  require(hart.xreg(16) == 42, "CSR read/write old value");
  hart.execute_instruction(Bits<32>{0x3400e8f3});  // csrrsi x17, mscratch, 1
  require(hart.xreg(17) == 0xfffffffc, "CSR immediate set old value");
  hart.execute_instruction(Bits<32>{0x34003973});  // csrrc x18, mscratch, x0
  require(hart.xreg(18) == 0xfffffffd &&
              scratch->hw_read(Bits<8>{32}).get() == 0xfffffffd,
          "CSR zero-mask read preserves value");
  // Native HartBase initializes this counter, but neither retained run loop increments it.
  require(hart.num_insts_exec() == 0, "retained native instruction-counter behavior");
  return 0;
}
